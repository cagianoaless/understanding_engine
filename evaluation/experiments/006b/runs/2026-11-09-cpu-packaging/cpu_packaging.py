"""Official CPU-only packaging comparison. Metadata/HEAD only; no payloads.

Reuse the frozen Linux tag, sidecar, dependency-edge and license audit helpers.
Only torch/torchvision/torchaudio are sourced from the official CPU index.
All previous public-version constraints remain; constraints do not force unused
CUDA dependencies into the newly resolved graph.
"""

import argparse
import copy
import email.parser
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import time
import urllib.parse
import urllib.request

from packaging.utils import parse_wheel_filename
from packaging.version import Version


HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "2026-11-09-linux-preflight"
OLD = runpy.run_path(str(PREVIOUS / "audit.py"))
INVENTORY = runpy.run_path(str(PREVIOUS / "inventory.py"))
BASELINE = json.loads((PREVIOUS / "dependencies.json").read_text())
PRIOR = {r["name"]: r for r in BASELINE["records"]}
FAMILY = {"torch", "torchvision", "torchaudio"}
CPU_HOSTS = {"download.pytorch.org", "download-r2.pytorch.org"}
POLICY = json.loads((HERE / "policy.json").read_text())


def cpu_url_allowed(url, method="GET"):
    p = urllib.parse.urlsplit(url)
    return (method in {"GET", "HEAD"} and p.scheme == "https" and p.hostname in CPU_HOSTS and not p.username and not p.password
            and p.path.startswith("/whl/cpu/")
            and (method == "HEAD" or p.path.endswith(("/", ".whl.metadata"))))


class CPUClient(OLD["MetadataClient"]):
    def get(self, url, accept="application/json"):
        if OLD["permitted_url"](url):
            return super().get(url, accept)
        return self.cpu_request(url)[0]

    def cpu_request(self, url, method="GET"):
        if not cpu_url_allowed(url, method):
            raise ValueError("CPU wheel bodies are not authorized")

        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not cpu_url_allowed(newurl, req.get_method()):
                    raise ValueError("Unapproved CPU-source redirect")
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        with self.upstream_slots:
            request = urllib.request.Request(url, method=method, headers={"Accept-Encoding": "gzip"})
            with urllib.request.build_opener(Redirect()).open(request, timeout=25) as response:
                wire = response.read(2_000_001) if method == "GET" else b""
                if len(wire) > 2_000_000:
                    raise ValueError("CPU metadata response too large")
                content = (gzip.GzipFile(fileobj=io.BytesIO(wire)).read(4_000_001)
                           if response.headers.get("Content-Encoding") == "gzip" else wire)
                if len(content) > 4_000_000:
                    raise ValueError("Expanded CPU metadata response too large")
                headers = {"content_length": response.headers.get("Content-Length"),
                           "last_modified": response.headers.get("Last-Modified")}
            with self.lock:
                self.wire_bytes += len(wire)
                self.decoded_bytes += len(content)
                if max(self.wire_bytes, self.decoded_bytes) > self.total_limit:
                    raise ValueError("Bounded metadata budget exceeded")
                digest = hashlib.sha256(content).hexdigest()
                path = self.directory / (digest + ".metadata")
                if method == "GET" and not path.exists():
                    path.write_bytes(content)
                self.records.append({"url": url, "method": method, "wire_body_bytes": len(wire),
                                     "decoded_bytes": len(content), "sha256": digest, **headers})
            return content, headers


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


class CPUGateway(OLD["Gateway"]):
    def index(self, name, origin):
        if name not in FAMILY:
            return super().index(name, origin)
        if name in self.indices:
            return self.indices[name]
        url = "https://download.pytorch.org/whl/cpu/" + name + "/"
        parser = Links()
        parser.feed(self.client.get(url).decode())
        files = []
        for attrs in parser.links:
            link = urllib.parse.urljoin(url, attrs.get("href", ""))
            filename = urllib.parse.unquote(urllib.parse.urlsplit(link).path.rsplit("/", 1)[-1])
            if not filename.endswith(".whl"):
                continue
            try:
                parsed = parse_wheel_filename(filename)
                rank = OLD["wheel_rank"](filename)
            except ValueError:
                continue
            if rank is None or (name in PRIOR and parsed[1].public != Version(PRIOR[name]["version"]).public):
                continue
            upstream = link.split("#", 1)[0]
            if not cpu_url_allowed(upstream, "HEAD"):
                raise ValueError("CPU index links to unapproved artifact origin")
            digest = urllib.parse.parse_qs(urllib.parse.urlsplit(link).fragment).get("sha256", [None])[0]
            if not digest:
                raise ValueError("Official CPU artifact lacks SHA-256")
            md = attrs.get("data-core-metadata") or attrs.get("data-dist-info-metadata")
            md_hash = {"sha256": md.split("=", 1)[1]} if md and md.startswith("sha256=") else True
            original = {"filename": filename, "url": upstream, "hashes": {"sha256": digest},
                        "core-metadata": md_hash, "yanked": "data-yanked" in attrs}
            if attrs.get("data-requires-python"):
                original["requires-python"] = attrs["data-requires-python"]
            if attrs.get("data-upload-time"):
                original["upload-time"] = attrs["data-upload-time"]
            key = hashlib.sha256(upstream.encode()).hexdigest()
            path = "/files/" + key + "/" + filename
            self.files[path] = {"origin": original, "url": upstream}
            files.append(dict(original, url=origin + path))
        encoded = json.dumps({"meta": {"api-version": "1.0"}, "name": name, "files": files}).encode()
        self.indices[name] = encoded
        return encoded


def resolve(output, python, uv):
    output = Path(output).resolve()
    if subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=output.parent,
                      capture_output=True).returncode == 0:
        raise ValueError("Raw evidence must be outside all Git roots")
    output.mkdir(parents=True, exist_ok=False)
    assert POLICY["download_cap_bytes"] is None
    assert POLICY["installed_cache_cap_bytes"] == 4 * 1024 ** 3
    requirement, constraints = output / "requirements.in", output / "constraints.in"
    requirement.write_text("docling==2.148.0\n")
    constraints.write_text("\n".join(r["name"] + "==" + Version(r["version"]).public
                                    for r in BASELINE["records"]) + "\n")
    client = CPUClient(output / "metadata")
    gateway = CPUGateway(client)
    server = gateway.serve()
    argv = [uv, "--no-config", "--cache-dir", str(output / "resolver-cache"), "pip", "compile",
            str(requirement), "--constraints", str(constraints), "--python", python,
            "--python-version", "3.11.13", "--python-platform", "aarch64-manylinux_2_39",
            "--only-binary", ":all:", "--generate-hashes", "--exclude-newer", OLD["CUTOFF"],
            "--default-index", "http://127.0.0.1:%d/simple" % server.server_port,
            "--output-file", str(output / "requirements.lock"), "--no-python-downloads",
            "--keyring-provider", "disabled"]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UV_", "PIP_"))}
    env["NO_PROXY"] = "127.0.0.1,localhost"
    start, stopped = time.monotonic(), None
    with (output / "resolve.stdout.log").open("x") as out, (output / "resolve.stderr.log").open("x") as err:
        process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            if gateway.stop.is_set() or time.monotonic() - start > 300:
                stopped = "metadata_guard" if gateway.stop.is_set() else "timeout"
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            if os.statvfs(output).f_bavail * os.statvfs(output).f_frsize < POLICY["host_free_reserve_bytes"]:
                stopped = "host_reserve"
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
                break
            time.sleep(0.1)
    server.shutdown()
    server.server_close()
    result = {"schema_version": "006b.cpu-resolution.1", "argv": argv, "exit_code": process.returncode,
              "stop_reason": stopped, "elapsed_seconds": time.monotonic() - start,
              "complete": process.returncode == 0 and stopped is None and not gateway.blocked,
              "policy": POLICY, "constraints": constraints.read_text(), "cutoff": OLD["CUTOFF"],
              "observed_sidecars": list(gateway.sidecars.values()), "metadata_requests": client.records,
              "metadata_wire_body_bytes": client.wire_bytes, "metadata_decoded_bytes": client.decoded_bytes,
              "blocked_artifact_requests": gateway.blocked, "errors": gateway.errors,
              "wheel_payload_bytes": 0, "model_weight_bytes": 0,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / "resolution.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def inventory(resolution_file, output):
    resolution_file, output = Path(resolution_file), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    data = json.loads(resolution_file.read_text())
    if not data["complete"]:
        raise ValueError("Do not invent a complete inventory from an incomplete solve")
    import re
    pins = {}
    for line in resolution_file.with_name("requirements.lock").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", line)
        if m:
            pins[m[1]] = m[2]
    client = CPUClient(output / "metadata")
    records = []
    for name, version in sorted(pins.items()):
        options = [r for r in data["observed_sidecars"] if r["name"] == name and r["version"] == version]
        row = min(options, key=lambda r: OLD["wheel_rank"](r["wheel_filename"]))
        if name not in FAMILY:
            prior = PRIOR[name]
            assert prior["version"] == version and prior["selected_wheel"]["filename"] == row["wheel_filename"]
            assert prior["selected_wheel"]["sha256"] == row["artifact"]["hashes"]["sha256"]
            assert prior["wheel_metadata_sha256"] == row["metadata_sha256"]
            record = copy.deepcopy(prior)
            record["provenance_recheck"] = "Fresh PyPI index artifact hash and wheel sidecar hash match PR12; immutable declaration snapshot reused"
        else:
            raw = (resolution_file.parent / "metadata" / (row["metadata_sha256"] + ".metadata")).read_bytes()
            metadata = email.parser.BytesParser().parsebytes(raw)
            _, head = client.cpu_request(row["artifact"]["url"], "HEAD")
            declaration = OLD["declared_license"]({"license_expression": metadata.get("License-Expression"),
                "license": metadata.get("License"), "classifiers": metadata.get_all("Classifier", [])})
            legacy = declaration.pop("legacy_declaration")
            declaration["legacy_declaration_excerpt"] = legacy[:100] if legacy else None
            record = {"name": name, "version": version, "requires_dist": row["requires_dist"],
                      "requires_python": row["requires_python"], "license": declaration,
                      "wheel_metadata_url": row["metadata_url"], "wheel_metadata_sha256": row["metadata_sha256"],
                      "selected_wheel": {"filename": row["wheel_filename"], "url": row["artifact"]["url"],
                        "bytes": int(head["content_length"]), "sha256": row["artifact"]["hashes"]["sha256"],
                        "tags": sorted(str(t) for t in parse_wheel_filename(row["wheel_filename"])[3]),
                        "target_compatible": OLD["wheel_rank"](row["wheel_filename"]) is not None,
                        "upload_time": row["artifact"].get("upload-time"), "size_source": "Official server HTTP HEAD"},
                      "unpacked_bytes": None, "provenance_recheck": "Official CPU index hash + verified METADATA sidecar + HEAD size; payload not acquired"}
        records.append(record)
    errors, extras = INVENTORY["closure_errors"](records)
    if errors:
        raise ValueError("Incomplete CPU dependency graph: " + repr(errors))
    result = {"schema_version": "006b.cpu-dependencies.1", "complete": True, "package_count": len(records),
              "records": records, "closure_errors": errors, "activated_extras": extras,
              "expected_compressed_wheel_bytes": sum(r["selected_wheel"]["bytes"] for r in records),
              "unpacked_bytes": None, "metadata_requests": client.records,
              "metadata_wire_body_bytes": client.wire_bytes, "wheel_payload_bytes": 0,
              "prior_declarations_reused_only_when_wheel_and_sidecar_hashes_match": True}
    (output / "dependencies.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "requirements.cpu.lock").write_text("# Metadata-resolved CPU artifacts; not installation authorization.\n" +
        "\n".join(r["name"] + "==" + r["version"] + " --hash=sha256:" + r["selected_wheel"]["sha256"] for r in records) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--resolution")
    p.add_argument("--python")
    p.add_argument("--uv", default="uv")
    args = p.parse_args()
    r = inventory(args.resolution, args.output) if args.resolution else resolve(args.output, args.python, args.uv)
    print(json.dumps({k: r[k] for k in ["complete", "exit_code", "stop_reason", "package_count", "expected_compressed_wheel_bytes", "blocked_artifact_requests"] if k in r}))
    raise SystemExit(0 if r["complete"] else 3)
