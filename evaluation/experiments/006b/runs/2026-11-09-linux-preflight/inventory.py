"""Inspect public metadata only; never acquire wheels or model weights."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import email.parser
import hashlib
import json
from pathlib import Path
import re
import runpy
import urllib.parse
import urllib.request

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename


AUDIT = runpy.run_path(str(Path(__file__).with_name("audit.py")))
ORIGINAL = AUDIT["ORIGINAL"]
REVISION = AUDIT["REVISION"]


def model_url_allowed(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname != "huggingface.co" or p.username or p.password:
        return False
    if p.path == "/api/models/docling-project/docling-layout-heron/revision/" + REVISION:
        return True
    prefix = "/docling-project/docling-layout-heron/resolve/" + REVISION + "/"
    cache = "/api/resolve-cache/models/docling-project/docling-layout-heron/" + REVISION + "/"
    return ((p.path.startswith(prefix) or p.path.startswith(cache))
            and p.path.rsplit("/", 1)[-1] in {"README.md", "config.json", "preprocessor_config.json"})


def inspect_model(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((ORIGINAL / "model-inventory.json").read_text())
    records = []

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not model_url_allowed(newurl):
                raise ValueError("Forbidden model redirect; weight URLs are never allowed")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    def get(url, filename):
        if not model_url_allowed(url):
            raise ValueError("Only pinned model metadata and model-card files are allowed")
        with urllib.request.build_opener(Redirect()).open(url, timeout=25) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Model metadata response exceeds bound")
        (output / filename).write_bytes(raw)
        records.append({"url": url, "body_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "external_file": filename})
        return raw

    api_url = "https://huggingface.co/api/models/docling-project/docling-layout-heron/revision/" + REVISION + "?blobs=true"
    api = json.loads(get(api_url, "model-api.json"))
    siblings = {item["rfilename"]: item for item in api["siblings"]}
    files = []
    for old in baseline["model_files"]:
        item = siblings.get(old["filename"], {})
        row = dict(old)
        row["downloaded_this_stage"] = False
        if old["role"] == "weights":
            lfs = item.get("lfs", {})
            row["live_lfs_sha256"] = lfs.get("sha256") or lfs.get("oid")
            row["live_bytes"] = lfs.get("size") or item.get("size")
            row["metadata_matches"] = row["live_lfs_sha256"] == old["sha256"] and row["live_bytes"] == old["bytes"]
            row["content_verified"] = False
        else:
            raw = get(old["url"], old["filename"])
            row["downloaded_this_stage"] = True
            row["metadata_matches"] = hashlib.sha256(raw).hexdigest() == old["sha256"] and len(raw) == old["bytes"]
        files.append(row)
    result = {"schema_version": "006b.linux-model-audit.1", "revision": REVISION,
              "live_api_revision": api.get("sha"), "files": files,
              "pinned_identity_status": "PASS" if api.get("sha") == REVISION and all(f["metadata_matches"] for f in files) else "FAIL",
              "declared_license": api.get("cardData", {}).get("license"),
              "license_clearance": "UNKNOWN", "weights_content_verified": False,
              "required_inference_payload_bytes": baseline["inference_download_bytes"],
              "weight_payload_bytes_acquired": 0, "metadata_body_bytes": sum(r["body_bytes"] for r in records),
              "requests": records}
    (output / "model.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def closure_errors(records):
    """Independently audit active Requires-Dist edges, extras and version pins."""
    by_name = {r["name"]: r for r in records}
    extras = {"docling": {""}}
    env = default_environment()
    env.update(implementation_name="cpython", implementation_version="3.11.13", os_name="posix",
               platform_machine="aarch64", platform_python_implementation="CPython",
               platform_release="6.8.0-117-generic", platform_system="Linux", platform_version="",
               python_full_version="3.11.13", python_version="3.11", sys_platform="linux")
    errors = set()
    for _ in range(len(records) + 1):
        changed = False
        for name, active_extras in list(extras.items()):
            if name not in by_name:
                errors.add("Missing active package: " + name)
                continue
            record = by_name[name]
            if record["requires_python"] and not SpecifierSet(record["requires_python"]).contains("3.11.13"):
                errors.add("Python version rejected: " + name)
            for text in record["requires_dist"]:
                requirement = Requirement(text)
                if requirement.marker and not any(requirement.marker.evaluate(dict(env, extra=e)) for e in active_extras):
                    continue
                target = canonicalize_name(requirement.name)
                if target not in by_name:
                    errors.add("Missing dependency: " + name + " -> " + str(requirement))
                    continue
                if requirement.url or not requirement.specifier.contains(by_name[target]["version"], prereleases=True):
                    errors.add("Unsatisfied dependency: " + name + " -> " + str(requirement))
                new = {""} | set(requirement.extras)
                previous = extras.setdefault(target, set())
                if not new <= previous:
                    previous.update(new)
                    changed = True
        if not changed:
            break
    return sorted(errors), {name: sorted(values) for name, values in sorted(extras.items())}


def inspect_dependencies(resolution_file, output):
    resolution_file, output = Path(resolution_file), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    resolution = json.loads(resolution_file.read_text())
    observed = resolution["observed_sidecars"]
    pins = {}
    if resolution["complete"]:
        for line in resolution_file.with_name("requirements.lock").read_text().splitlines():
            match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]*\])?==([^\s\\]+)", line)
            if match:
                pins[canonicalize_name(match[1])] = match[2]
    else:
        # These are partial candidate observations, never a substitute lock.
        pins = {r["name"]: r["version"] for r in observed}
    chosen = []
    for name, version in sorted(pins.items()):
        options = [r for r in observed if r["name"] == name and r["version"] == version]
        if not options:
            raise ValueError("Resolved pin has no observed wheel METADATA: " + name)
        chosen.append(min(options, key=lambda r: (AUDIT["wheel_rank"](r["wheel_filename"]), r["wheel_filename"])))
    client = AUDIT["MetadataClient"](output / "metadata")

    def inspect(row):
        url = "https://pypi.org/pypi/" + row["name"] + "/" + row["version"] + "/json"
        raw = client.get(url)
        data = json.loads(raw)
        wheel = next(f for f in data["urls"] if f["filename"] == row["wheel_filename"])
        original = row["artifact"]
        if original.get("hashes", {}).get("sha256") != wheel["digests"].get("sha256"):
            raise ValueError("Index/version artifact hash mismatch")
        sidecar = (resolution_file.parent / "metadata" / (row["metadata_sha256"] + ".metadata")).read_bytes()
        metadata = email.parser.BytesParser().parsebytes(sidecar)
        declaration = AUDIT["declared_license"](data["info"])
        legacy = declaration.pop("legacy_declaration")
        declaration["legacy_declaration_excerpt"] = legacy[:100] if legacy else None
        declaration["wheel_license_expression"] = metadata.get("License-Expression")
        declaration["wheel_license_excerpt"] = (metadata.get("License") or "")[:100] or None
        return {"name": row["name"], "version": row["version"],
                "selection_status": "resolved" if resolution["complete"] else "partial_observed_candidate_not_locked",
                "requires_dist": row["requires_dist"], "requires_python": row["requires_python"],
                "metadata_url": url, "metadata_sha256": hashlib.sha256(raw).hexdigest(),
                "wheel_metadata_url": row["metadata_url"], "wheel_metadata_sha256": row["metadata_sha256"],
                "selected_wheel": {"filename": wheel["filename"], "url": wheel["url"],
                                   "bytes": wheel["size"], "sha256": wheel["digests"].get("sha256"),
                                   "hash_status": "present" if wheel["digests"].get("sha256") else "MISSING",
                                   "upload_time": wheel["upload_time_iso_8601"],
                                   "tags": sorted(str(t) for t in parse_wheel_filename(wheel["filename"])[3]),
                                   "target_compatible": AUDIT["wheel_rank"](wheel["filename"]) is not None},
                "license": declaration, "unpacked_bytes": None}

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(inspect, chosen))
    errors, extras = closure_errors(records) if resolution["complete"] else (["Resolver did not complete"], {})
    complete = resolution["complete"] and not errors and bool(records)
    result = {"schema_version": "006b.linux-dependencies.1", "target": resolution["target"],
              "cutoff": resolution["cutoff"], "index_policy": resolution["index_policy"],
              "root_requirement": "docling==2.148.0", "complete": complete,
              "package_count": len(records), "closure_errors": errors, "activated_extras": extras,
              "selected_compressed_wheel_bytes": sum(r["selected_wheel"]["bytes"] for r in records),
              "unpacked_installed_bytes": None, "records": records,
              "metadata_wire_body_bytes": client.wire_bytes, "metadata_decoded_bytes": client.decoded_bytes,
              "metadata_requests": client.records, "wheel_payload_bytes_acquired": 0}
    (output / "dependencies.json").write_text(json.dumps(result, indent=2) + "\n")
    if complete:
        lines = ["# Linux aarch64 / CPython 3.11, metadata-resolved; NOT an installation authorization."]
        lines += [r["name"] + "==" + r["version"] + " --hash=sha256:" + r["selected_wheel"]["sha256"] for r in records]
        (output / "requirements.candidate.lock").write_text("\n".join(lines) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resolution")
    args = parser.parse_args()
    result = inspect_dependencies(args.resolution, args.output) if args.resolution else inspect_model(args.output)
    print(json.dumps({key: result[key] for key in ["complete", "package_count", "selected_compressed_wheel_bytes", "pinned_identity_status", "metadata_body_bytes", "metadata_wire_body_bytes"] if key in result}))
