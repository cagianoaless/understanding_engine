"""Bounded, sequential acquisition of the PR13 allowlist; ZIP inspection only.

Never install, fully extract or import downloaded code. All payloads and raw
notices stay in one fresh directory outside every Git root. No retries, redirects,
alternate sources, source builds, model requests or cache cleanup are supported.
"""

import argparse
import email.parser
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile


HERE = Path(__file__).resolve().parent
PROPOSAL = HERE.parent / "2026-11-09-cpu-packaging/archive-audit-proposal.json"
PROPOSAL_SHA256 = "81c9a936575a8376acb835c2d33949b81719e96dfbc1cf009b41cfae5026ff5e"
HOST_RESERVE = 20 * 1024 ** 3
STORAGE_CAP = 4 * 1024 ** 3
WORK_ALLOWANCE = 64 * 1024 ** 2
NOTICE_TOTAL = 32 * 1024 ** 2
NOTICE_SINGLE = 2 * 1024 ** 2
CHUNK = 1024 ** 2


def dump(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def load_allowlist():
    assert hashlib.sha256(PROPOSAL.read_bytes()).hexdigest() == PROPOSAL_SHA256
    proposal = json.loads(PROPOSAL.read_text())
    rows = proposal["artifacts"]
    assert len(rows) == 103 and sum(r["bytes"] for r in rows) == 379580121
    assert len({r["filename"] for r in rows}) == len(rows)
    for row in rows:
        p = urllib.parse.urlsplit(row["url"])
        assert p.scheme == "https" and not p.username and not p.password and not p.query and not p.fragment
        assert p.hostname in {"files.pythonhosted.org", "download.pytorch.org", "download-r2.pytorch.org"}
        assert urllib.parse.unquote(p.path.rsplit("/", 1)[-1]) == row["filename"]
        assert Path(row["filename"]).name == row["filename"] and row["filename"].endswith(".whl")
        assert row["bytes"] > 0 and re.fullmatch("[0-9a-f]{64}", row["sha256"])
        assert not row["name"].startswith(("nvidia-", "cuda-")) and row["name"] != "triton"
        if row["name"] in {"torch", "torchvision"}:
            assert row["version"].endswith("+cpu") and p.path.startswith("/whl/cpu/")
        else:
            assert p.hostname == "files.pythonhosted.org"
    return rows


def allocation_snapshot(roots):
    """Read only registered roots; de-duplicate real files by device/inode."""
    seen, sizes = set(), {}
    for label, value in roots.items():
        root = Path(value)
        allocated = logical = files = 0
        links = 0
        if root.exists():
            if root.is_symlink() or not root.is_dir():
                raise ValueError("Registered root changed directory identity: " + label)
            for parent, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()]
                for name in names:
                    s = (Path(parent) / name).lstat()
                    if stat.S_ISLNK(s.st_mode):
                        links += 1
                    if stat.S_ISREG(s.st_mode) and (s.st_dev, s.st_ino) not in seen:
                        seen.add((s.st_dev, s.st_ino))
                        allocated += s.st_blocks * 512
                        logical += s.st_size
                        files += 1
        sizes[label] = {"allocated_bytes": allocated, "logical_bytes": logical,
                        "regular_files": files, "symlinks_not_followed": links,
                        "exists": root.exists()}
    data = os.statvfs("/System/Volumes/Data")
    return {"host_available_bytes": data.f_bavail * data.f_frsize,
            "allocated_bytes": sum(r["allocated_bytes"] for r in sizes.values()),
            "roots": sizes}


def check_limits(snapshot, pending_bytes=0):
    if snapshot["host_available_bytes"] - pending_bytes < HOST_RESERVE:
        raise ValueError("STOP: host free-space reserve")
    if snapshot["allocated_bytes"] + pending_bytes + WORK_ALLOWANCE > STORAGE_CAP:
        raise ValueError("STOP: inclusive allocated storage plus work allowance")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("STOP: redirect is outside the exact URL authorization")


def notice_file(name):
    p = PurePosixPath(name)
    if p.suffix.lower() in {".py", ".pyi", ".so", ".dll", ".dylib", ".a", ".exe", ".c", ".h"}:
        return False
    return (bool(re.search(r"licen[cs]e|copying|notice|copyright|third[_-]party", p.name, re.I))
            or any(part.lower() in {"licenses", "licences", "license_files"} for part in p.parts[:-1]))


def text_signatures(text):
    """Evidence pointers, never automatic license compatibility clearance."""
    t = " ".join(text.lower().split())
    patterns = {
        "MIT_grant": "permission is hereby granted, free of charge",
        "BSD_redistribution": "redistribution and use in source and binary forms",
        "Apache_license": "apache license",
        "ISC_grant": "permission to use, copy, modify, and/or distribute",
        "MPL": "mozilla public license",
        "Python_Software_Foundation": "python software foundation license",
        "Boost": "boost software license",
        "Zlib": "the origin of this software must not be misrepresented",
        "LGPL_mention": "lesser general public license",
        "GPL_mention": "gnu general public license",
        "AGPL_mention": "affero general public license",
        "noncommercial_mention": "non-commercial",
        "LicenseRef_mention": "licenseref-",
    }
    return [label for label, phrase in patterns.items() if phrase in t]


def inspect_zip(path, row, notice_directory, remaining_notice_bytes):
    notices, entries, assets = [], [], []
    work_used = 0
    metadata = None
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 200000:
            raise ValueError("ZIP entry-count guard")
        seen = set()
        for info in infos:
            name = info.filename
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or name in seen:
                raise ValueError("Unsafe or duplicate ZIP member")
            seen.add(name)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or info.flag_bits & 1:
                raise ValueError("Unexpected ZIP symlink/encryption")
            if info.is_dir():
                continue
            entries.append({"path": name, "uncompressed_bytes": info.file_size,
                            "compressed_bytes": info.compress_size, "crc32": "%08x" % info.CRC})
            if name.endswith((".onnx", ".pt", ".pth", ".safetensors", ".ckpt")):
                assets.append({"path": name, "bytes": info.file_size,
                               "status": "filename-based bundled-asset candidate; not executed"})
            if len(p.parts) == 2 and name.endswith(".dist-info/METADATA"):
                if metadata is not None:
                    raise ValueError("Multiple root wheel METADATA files")
                if info.file_size > NOTICE_SINGLE:
                    raise ValueError("Oversize wheel METADATA")
                data = archive.read(info)
                metadata = email.parser.BytesParser().parsebytes(data)
            if not notice_file(name):
                continue
            entry = {"path": name, "uncompressed_bytes": info.file_size}
            if info.file_size > NOTICE_SINGLE or info.file_size > remaining_notice_bytes - work_used:
                entry.update(status="UNREAD_BOUNDED_LIMIT", sha256=None, signatures=[])
            else:
                data = archive.read(info)
                digest = hashlib.sha256(data).hexdigest()
                dest = notice_directory / (digest + ".txt")
                if not dest.exists():
                    with dest.open("xb") as stream:
                        stream.write(data)
                work_used += len(data)
                entry.update(status="READ_CRC_CHECKED", sha256=digest,
                             text_utf8_decodable=True, signatures=[])
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = data.decode("utf-8", errors="replace")
                    entry["text_utf8_decodable"] = False
                entry["signatures"] = text_signatures(text)
            notices.append(entry)
    if metadata is None:
        raise ValueError("Wheel METADATA missing")
    norm = lambda s: re.sub(r"[-_.]+", "-", s).lower()
    if norm(metadata["Name"]) != row["name"] or metadata["Version"] != row["version"]:
        raise ValueError("Wheel identity differs from the exact allowlist")
    return {"name": row["name"], "version": row["version"], "filename": row["filename"],
            "file_count": len(entries), "zip_uncompressed_logical_bytes": sum(i["uncompressed_bytes"] for i in entries),
            "estimated_4KiB_rounded_file_bytes": sum(math.ceil(i["uncompressed_bytes"] / 4096) * 4096 for i in entries),
            "zip_compressed_member_bytes": sum(i["compressed_bytes"] for i in entries),
            "notices": notices, "notice_bytes_read": work_used, "bundled_asset_candidates": assets,
            "metadata_license_expression": metadata.get("License-Expression"),
            "metadata_license_files": metadata.get_all("License-File", []),
            "entries": entries}, work_used


def run(raw, roots_file, continue_inspection=False):
    if Path(raw).is_symlink():
        raise ValueError("Raw directory must not be a symlink")
    raw = Path(raw).resolve(strict=True)
    if subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=raw, capture_output=True).returncode == 0:
        raise ValueError("Raw evidence is inside a Git checkout")
    if raw.is_symlink() or raw.stat().st_uid != os.getuid():
        raise ValueError("Unexpected raw directory identity/ownership")
    rows = load_allowlist()
    prior = json.loads((raw/"audit.json").read_text()) if continue_inspection else None
    if prior:
        if prior["outcome"] != "STOPPED" or prior["error"] != "ValueError: Wheel identity differs from the exact allowlist":
            raise ValueError("Continuation only permits the recorded inspector identity failure")
        prefix = prior["journal"]
        if not all(r["verified"] for r in prefix):
            raise ValueError("No failed download may be retried by this continuation")
        if any((raw/"archives").glob("*.part")):
            raise ValueError("Partial payload prevents continuation")
    else:
        prefix = []
    roots = json.loads(Path(roots_file).read_text())
    assert roots["$ARCHIVE_RAW"] == str(raw)
    assert len({str(Path(p).resolve()) for p in roots.values()}) == len(roots)
    archives, notices = raw / "archives", raw / "notices"
    archives.mkdir(exist_ok=bool(prior))
    notices.mkdir(exist_ok=bool(prior))
    journal, results, snapshots, wire = [], [], [], prior["downloaded_http_body_bytes"] if prior else 0
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    started = time.monotonic()
    outcome, error = "COMPLETE", None

    def guard(pending=0, label="check"):
        sample = allocation_snapshot(roots)
        sample["elapsed_seconds"] = time.monotonic() - started
        sample["label"] = label
        snapshots.append(sample)
        check_limits(sample, pending)
        if time.monotonic() - started > 1200:
            raise ValueError("STOP: overall acquisition timeout")
        return sample

    try:
        initial = guard(label="initial")
        for index, row in enumerate(rows):
            guard(0 if index < len(prefix) else row["bytes"], "before:" + row["name"])
            partial = archives / (row["filename"] + ".part")
            final = archives / row["filename"]
            if index < len(prefix):
                previous = prefix[index]
                if previous["name"] != row["name"] or previous["url"] != row["url"] or partial.exists():
                    raise ValueError("Verified prefix differs from the allowlist")
                digest = hashlib.sha256()
                with final.open("rb") as stream:
                    for data in iter(lambda:stream.read(CHUNK),b""):
                        digest.update(data)
                if final.stat().st_size != row["bytes"] or digest.hexdigest() != row["sha256"]:
                    raise ValueError("Retained prefix archive changed; no redownload authorized by continuation")
                journal.append(dict(previous, acquired_in_stage="initial"))
                inspected, used = inspect_zip(final,row,notices,NOTICE_TOTAL-sum(r["notice_bytes_read"] for r in results))
                existing = raw/(row["name"]+".zip.json")
                if existing.exists():
                    if json.loads(existing.read_text()) != inspected:
                        dump(raw/(row["name"]+".continuation.zip.json"),inspected)
                else:
                    dump(existing,inspected)
                results.append({k:v for k,v in inspected.items() if k!="entries"})
                guard(label="reinspected:"+row["name"])
                continue
            if partial.exists() or final.exists():
                raise ValueError("Archive destination is not fresh")
            request = urllib.request.Request(row["url"], headers={"Accept-Encoding": "identity",
                "User-Agent": "understanding-engine-006b-archive-audit"})
            entry = {"name": row["name"], "version": row["version"], "url": row["url"],
                     "expected_bytes": row["bytes"], "expected_sha256": row["sha256"],
                     "method": "GET", "bytes_received": 0, "verified": False,
                     "acquired_in_stage":"continuation" if prior else "initial"}
            journal.append(entry)
            digest = hashlib.sha256()
            with opener.open(request, timeout=30) as response:
                entry.update(status=response.status, final_url=response.geturl(),
                             header_content_length=response.headers.get("Content-Length"))
                if response.status != 200 or response.geturl() != row["url"]:
                    raise ValueError("Unexpected HTTP status/source URL")
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise ValueError("Unexpected HTTP content encoding")
                if entry["header_content_length"] is not None and int(entry["header_content_length"]) != row["bytes"]:
                    raise ValueError("Unexpected advertised payload length")
                with partial.open("xb") as stream:
                    while True:
                        guard(min(CHUNK, row["bytes"] - entry["bytes_received"] + 1), "stream:" + row["name"])
                        data = response.read(min(CHUNK, row["bytes"] - entry["bytes_received"] + 1))
                        wire += len(data)
                        entry["bytes_received"] += len(data)
                        if entry["bytes_received"] > row["bytes"]:
                            raise ValueError("Payload exceeded authorized length")
                        if not data:
                            break
                        digest.update(data)
                        stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            entry["actual_sha256"] = digest.hexdigest()
            if entry["bytes_received"] != row["bytes"] or digest.hexdigest() != row["sha256"]:
                raise ValueError("Payload length/SHA-256 mismatch")
            partial.rename(final)
            entry["verified"] = True
            inspected, used = inspect_zip(final, row, notices, NOTICE_TOTAL - sum(r["notice_bytes_read"] for r in results))
            dump(raw / (row["name"] + ".zip.json"), inspected)
            results.append({k:v for k,v in inspected.items() if k != "entries"})
            guard(label="after:" + row["name"])
            print(json.dumps({"name":row["name"],"verified_bytes":row["bytes"],
                              "uncompressed":inspected["zip_uncompressed_logical_bytes"],
                              "completed":len(results)}), flush=True)
    except Exception as exc:
        outcome, error = "STOPPED", type(exc).__name__ + ": " + str(exc)
    final_sample = allocation_snapshot(roots)
    snapshots.append(dict(final_sample, label="final", elapsed_seconds=time.monotonic()-started))
    result = {"schema_version":"006b.cpu-archive-audit.1","outcome":outcome,"error":error,
              "proposal_sha256":PROPOSAL_SHA256,"expected_count":103,"verified_count":sum(r["verified"] for r in journal),
              "downloaded_http_body_bytes":wire,"expected_http_body_bytes":379580121,
              "zip_uncompressed_logical_bytes":sum(r["zip_uncompressed_logical_bytes"] for r in results),
              "estimated_4KiB_rounded_file_bytes":sum(r["estimated_4KiB_rounded_file_bytes"] for r in results),
              "notice_bytes_read":sum(r["notice_bytes_read"] for r in results),
              "elapsed_seconds":time.monotonic()-started,"journal":journal,"packages":results,
              "initial_storage":prior["initial_storage"] if prior else snapshots[0],"final_storage":snapshots[-1],
              "max_sampled_allocated_bytes":max([r["allocated_bytes"] for r in snapshots]+([prior["max_sampled_allocated_bytes"]] if prior else [])),
              "min_sampled_host_available_bytes":min([r["host_available_bytes"] for r in snapshots]+([prior["min_sampled_host_available_bytes"]] if prior else [])),
              "resource_check_count":len(snapshots)+(prior["resource_check_count"] if prior else 0),"candidate_installed":False,"neural_imports_or_inference":False,
              "model_requests":0,"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    result["inspection_continuation"] = bool(prior)
    result["prior_run_source_sha256"] = prior["source_sha256"] if prior else None
    result["prior_run_preserved"] = "audit.json" if prior else None
    dump(raw/("continuation-audit.json" if prior else "audit.json"), result)
    dump(raw/("continuation-resource-samples.json" if prior else "resource-samples.json"), snapshots)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--storage-roots", required=True)
    parser.add_argument("--continue-inspection-fix", action="store_true")
    args = parser.parse_args()
    result = run(args.raw, args.storage_roots, args.continue_inspection_fix)
    print(json.dumps({k:result[k] for k in ["outcome","error","verified_count","downloaded_http_body_bytes",
                     "zip_uncompressed_logical_bytes","max_sampled_allocated_bytes","min_sampled_host_available_bytes"]}))
    raise SystemExit(0 if result["outcome"] == "COMPLETE" else 3)
