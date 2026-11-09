"""Linux cp311 metadata audit: no wheel/model payloads, builds or installation.

PyPI index URLs are rewritten through a loopback-only gateway. A resolver wheel
or sdist request is refused locally and stops resolution before upstream access.
Only public index JSON, PEP 658 sidecars and version metadata may be retrieved.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import email.parser
import gzip
import io
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import runpy
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import Version


EXPERIMENT = Path(__file__).resolve().parents[2]
ORIGINAL = EXPERIMENT.parent / "006"
GATES = runpy.run_path(str(EXPERIMENT / "gates.py"))
LIMITS = runpy.run_path(str(ORIGINAL / "preflight.py"))["LIMITS"]
CUTOFF = json.loads((ORIGINAL / "dependencies.json").read_text())["cutoff"]
REVISION = "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
PLATFORMS = ["manylinux_2_%d_aarch64" % n for n in range(39, 16, -1)]
PLATFORMS += ["manylinux2014_aarch64", "linux_aarch64"]
TAGS = list(cpython_tags((3, 11), abis=["cp311"], platforms=PLATFORMS))
TAGS += list(compatible_tags((3, 11), interpreter="cp311", platforms=PLATFORMS))
TAG_ORDER = {tag: i for i, tag in enumerate(TAGS)}


def wheel_rank(filename):
    """Explicit target tags: never packaging.tags.sys_tags() on the Mac."""
    tags = parse_wheel_filename(filename)[3]
    return min((TAG_ORDER[t] for t in tags if t in TAG_ORDER), default=None)


def permitted_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    if parsed.hostname == "pypi.org":
        return parsed.path.startswith(("/simple/", "/pypi/"))
    if parsed.hostname == "files.pythonhosted.org":
        return parsed.path.endswith(".whl.metadata")
    return False


def declared_license(info):
    expression = info.get("license_expression") or ""
    legacy = info.get("license") or ""
    classifiers = [c for c in info.get("classifiers", []) if c.startswith("License ::")]
    from packaging.licenses import canonicalize_license_expression
    try:
        canonical = canonicalize_license_expression(expression) if expression else None
    except ValueError:
        canonical = None
    return {"expression": expression or None, "canonical_expression": canonical,
            "legacy_declaration": legacy or None, "classifiers": classifiers,
            "declared_expression_status": "PASS" if canonical and "LicenseRef-" not in canonical else "UNKNOWN",
            "custom_license_reference_unresolved": bool(canonical and "LicenseRef-" in canonical),
            "full_clearance": "UNKNOWN",
            "basis": "Version-specific publisher metadata; wheel license files and bundled notices not acquired"}


class MetadataClient:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.lock = threading.Lock()
        self.records = []
        self.wire_bytes = 0
        self.decoded_bytes = 0
        self.total_limit = 256 * 1024 ** 2
        self.upstream_slots = threading.BoundedSemaphore(4)
        self.transport_retries = []

    def get(self, url, accept="application/json"):
        if not permitted_url(url):
            raise ValueError("Forbidden upstream URL: wheel payloads are never authorized")
        with self.upstream_slots:
            for attempt in range(2):
                try:
                    return self._get(url, accept)
                except urllib.error.HTTPError:
                    raise
                except (urllib.error.URLError, ConnectionResetError) as error:
                    if attempt:
                        raise
                    with self.lock:
                        self.transport_retries.append({"url": url, "error": str(error), "retry": 1})
                    time.sleep(0.2)

    def _get(self, url, accept):
        request = urllib.request.Request(url, headers={"Accept": accept, "Accept-Encoding": "gzip"})
        started = time.monotonic()
        class GuardedRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not permitted_url(newurl):
                    raise ValueError("Forbidden redirect rejected before upstream access")
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(GuardedRedirect())
        with opener.open(request, timeout=25) as response:
            if not permitted_url(response.url):
                raise ValueError("Unexpected metadata redirect")
            chunks = []
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                with self.lock:
                    self.wire_bytes += len(chunk)
                    if self.wire_bytes > self.total_limit:
                        raise ValueError("Bounded metadata transfer limit exceeded")
                chunks.append(chunk)
                if sum(map(len, chunks)) > 16 * 1024 ** 2:
                    raise ValueError("Metadata response too large")
            wire = b"".join(chunks)
            content = (gzip.GzipFile(fileobj=io.BytesIO(wire)).read(40 * 1024 ** 2 + 1)
                       if response.headers.get("Content-Encoding") == "gzip" else wire)
            if len(content) > 40 * 1024 ** 2:
                raise ValueError("Expanded metadata response too large")
        digest = hashlib.sha256(content).hexdigest()
        with self.lock:
            self.decoded_bytes += len(content)
            if self.decoded_bytes > self.total_limit:
                raise ValueError("Expanded metadata total exceeds audit bound")
            path = self.directory / (digest + ".metadata")
            if not path.exists():
                path.write_bytes(content)
            self.records.append({"url": url, "wire_body_bytes": len(wire), "decoded_bytes": len(content),
                                 "sha256": digest, "external_file": path.name,
                                 "elapsed_seconds": time.monotonic() - started})
        return content


class Gateway:
    def __init__(self, client):
        self.client = client
        self.files = {}
        self.indices = {}
        self.sidecars = {}
        self.blocked = []
        self.errors = []
        self.invalid_index_filenames = []
        self.client_cancellations = []
        self.stop = threading.Event()
        self.lock = threading.Lock()

    def index(self, name, origin):
        with self.lock:
            if name in self.indices:
                return self.indices[name]
        data = json.loads(self.client.get("https://pypi.org/simple/" + name + "/",
                                         "application/vnd.pypi.simple.v1+json"))
        files = []
        for record in data["files"]:
            filename = record["filename"]
            if not filename.endswith(".whl"):
                continue
            try:
                rank = wheel_rank(filename)
            except InvalidWheelFilename:
                self.invalid_index_filenames.append({"project": name, "filename": filename})
                continue
            if rank is None:
                continue
            original = dict(record)
            upstream = record["url"].split("#", 1)[0]
            if not upstream.startswith("https://files.pythonhosted.org/"):
                raise ValueError("Unexpected artifact origin")
            key = hashlib.sha256(upstream.encode()).hexdigest()
            path = "/files/" + key + "/" + filename
            with self.lock:
                self.files[path] = {"origin": original, "url": upstream}
            record = dict(record)
            record["url"] = origin + path
            # If not advertised, attempt the sidecar first; a missing sidecar
            # still cannot authorize fallback to any bytes of the wheel.
            record["core-metadata"] = record.get("core-metadata") or record.get("dist-info-metadata") or True
            record["dist-info-metadata"] = record["core-metadata"]
            files.append(record)
        filtered = dict(data, files=files)
        encoded = json.dumps(filtered).encode()
        with self.lock:
            self.indices[name] = encoded
        return encoded

    def sidecar(self, path):
        artifact = path[:-len(".metadata")]
        with self.lock:
            item = self.files[artifact]
        raw = self.client.get(item["url"] + ".metadata", "application/octet-stream")
        expected = item["origin"].get("core-metadata") or item["origin"].get("dist-info-metadata")
        if isinstance(expected, dict) and expected.get("sha256"):
            if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("Sidecar hash mismatch")
        metadata = email.parser.BytesParser().parsebytes(raw)
        if not metadata.get("Name") or not metadata.get("Version"):
            raise ValueError("Malformed wheel metadata")
        for dependency in metadata.get_all("Requires-Dist", []):
            if Requirement(dependency).url:
                raise ValueError("Direct-URL dependency requires independent authorization")
        record = {"name": canonicalize_name(metadata["Name"]), "version": metadata["Version"],
                  "wheel_filename": item["origin"]["filename"], "metadata_sha256": hashlib.sha256(raw).hexdigest(),
                  "metadata_url": item["url"] + ".metadata", "requires_dist": metadata.get_all("Requires-Dist", []),
                  "requires_python": metadata.get("Requires-Python"), "artifact": item["origin"]}
        with self.lock:
            self.sidecars[artifact] = record
        return raw

    def handler(self):
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_error(self, *args, **kwargs):
                try:
                    return super().send_error(*args, **kwargs)
                except (BrokenPipeError, ConnectionResetError):
                    return None

            def do_GET(self):
                try:
                    if self.path.startswith("/simple/"):
                        name = self.path[len("/simple/"):].strip("/")
                        if not re.fullmatch(r"[a-z0-9-]+", name):
                            self.send_error(404)
                            return
                        raw = gateway.index(name, "http://127.0.0.1:%d" % self.server.server_port)
                        content_type = "application/vnd.pypi.simple.v1+json"
                    elif self.path.endswith(".whl.metadata"):
                        raw = gateway.sidecar(self.path)
                        content_type = "application/octet-stream"
                    else:
                        gateway.blocked.append({"path": self.path, "reason": "Artifact body/range access refused locally"})
                        gateway.stop.set()
                        self.send_error(403, "Metadata-only preflight; artifact download forbidden")
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    gateway.client_cancellations.append(self.path)
                except urllib.error.HTTPError as error:
                    gateway.errors.append({"path": self.path, "http_status": error.code})
                    self.send_error(error.code)
                except (ValueError, KeyError, OSError) as error:
                    gateway.errors.append({"path": self.path, "error": str(error)})
                    gateway.stop.set()
                    self.send_error(502)

        return Handler

    def serve(self):
        class JoinedServer(ThreadingHTTPServer):
            daemon_threads = False
            block_on_close = True

        server = JoinedServer(("127.0.0.1", 0), self.handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


def resolve(output, python, uv):
    output = Path(output).resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[5]):
        raise ValueError("Raw output must be outside Git")
    output.mkdir(parents=True, exist_ok=False)
    client = MetadataClient(output / "metadata")
    gateway = Gateway(client)
    server = gateway.serve()
    requirement = output / "requirements.in"
    requirement.write_text("docling==2.148.0\n")
    argv = [uv, "--no-config", "--cache-dir", str(output / "resolver-cache"), "pip", "compile",
            str(requirement), "--python", python, "--python-version", "3.11.13",
            "--python-platform", "aarch64-manylinux_2_39", "--only-binary", ":all:",
            "--generate-hashes", "--default-index", "http://127.0.0.1:%d/simple" % server.server_port,
            "--exclude-newer", CUTOFF, "--output-file", str(output / "requirements.lock"),
            "--no-python-downloads", "--keyring-provider", "disabled"]
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("UV_", "PIP_")):
            del env[key]
    env["NO_PROXY"] = "127.0.0.1,localhost"
    start = time.monotonic()
    stop_reason = None
    with (output / "resolve.stdout.log").open("x") as out, (output / "resolve.stderr.log").open("x") as err:
        process = subprocess.Popen(argv, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL, start_new_session=True)
        while process.poll() is None:
            if gateway.stop.is_set() or time.monotonic() - start > 300:
                stop_reason = "metadata_guard" if gateway.stop.is_set() else "resolver_timeout"
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            time.sleep(0.05)
    server.shutdown()
    server.server_close()
    result = {"schema_version": "006b.linux-resolution.1", "argv": argv,
              "exit_code": process.returncode, "stop_reason": stop_reason,
              "elapsed_seconds": time.monotonic() - start, "cutoff": CUTOFF,
              "target": "CPython 3.11.13 / Linux aarch64 / glibc 2.39",
              "index_policy": "PyPI, as Experiment 006; no CPU-index substitution or dependency overrides",
              "blocked_artifact_requests": gateway.blocked, "gateway_errors": gateway.errors,
              "invalid_index_filenames": gateway.invalid_index_filenames,
              "client_cancellations": gateway.client_cancellations,
              "wheel_payload_bytes": 0, "model_weight_bytes": 0, "source_builds": 0,
              "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "complete": process.returncode == 0 and stop_reason is None and not gateway.blocked,
              "metadata_wire_body_bytes": client.wire_bytes, "metadata_decoded_bytes": client.decoded_bytes,
              "metadata_transport_retries": client.transport_retries,
              "metadata_requests": client.records,
              "observed_sidecars": list(gateway.sidecars.values())}
    (output / "resolution.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    result = resolve(args.output, args.python, args.uv)
    print(json.dumps({key: result[key] for key in ["complete", "exit_code", "stop_reason", "metadata_wire_body_bytes", "blocked_artifact_requests"]}))
    raise SystemExit(0 if result["complete"] else 3)
