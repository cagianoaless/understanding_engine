"""Offline policy and metadata-gateway regressions, not inference evidence."""

import json
from pathlib import Path
import runpy

import pytest


MODULE = Path(__file__).resolve().parents[1] / "evaluation/experiments/006b/runs/2026-11-09-cpu-packaging/cpu_packaging.py"
cpu = runpy.run_path(str(MODULE))


def test_download_ceiling_withdrawal_is_not_a_storage_limit_change():
    assert cpu["POLICY"]["download_cap_bytes"] is None
    assert cpu["OLD"]["LIMITS"]["new_download_bytes"] == 2 * 1024 ** 3
    assert cpu["POLICY"]["installed_cache_cap_bytes"] == 4 * 1024 ** 3
    assert cpu["POLICY"]["host_free_reserve_bytes"] == 20 * 1024 ** 3
    assert not cpu["POLICY"]["wheel_acquisition_authorized"]
    assert not cpu["POLICY"]["inference_authorized"]


@pytest.mark.parametrize("host", ["download.pytorch.org", "download-r2.pytorch.org"])
def test_cpu_wheel_can_be_sized_but_not_downloaded(host):
    url = "https://" + host + "/whl/cpu/torch-2.15.0%2Bcpu-cp311-cp311-manylinux_2_28_aarch64.whl"
    assert cpu["cpu_url_allowed"](url, "HEAD")
    assert not cpu["cpu_url_allowed"](url, "GET")
    assert cpu["cpu_url_allowed"](url + ".metadata", "GET")
    assert not cpu["cpu_url_allowed"](url + ".metadata", "DELETE")


@pytest.mark.parametrize("url", [
    "https://download.pytorch.org/whl/cu130/a.whl.metadata",
    "https://untrusted.example/whl/cpu/a.whl.metadata",
    "http://download.pytorch.org/whl/cpu/a.whl.metadata",
    "https://user:secret@download.pytorch.org/whl/cpu/a.whl.metadata",
    "https://huggingface.co/a/model.safetensors",
])
def test_cuda_or_unapproved_origins_cannot_bypass_metadata_guard(url):
    assert not cpu["cpu_url_allowed"](url)


def test_controlled_cpu_index_retains_hash_upload_time_and_public_version():
    class Client:
        def get(self, *args):
            return (b'<a href="https://download-r2.pytorch.org/whl/cpu/torch-2.15.0%2Bcpu-cp311-cp311-manylinux_2_28_aarch64.whl#sha256='
                    + b'a' * 64 + b'" data-core-metadata="sha256=' + b'b' * 64
                    + b'" data-upload-time="2026-10-28T00:00:00Z">current</a>'
                    + b'<a href="https://download.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp311-cp311-manylinux_2_28_aarch64.whl#sha256='
                    + b'c' * 64 + b'">older</a>')

    gateway = cpu["CPUGateway"](Client())
    result = json.loads(gateway.index("torch", "http://127.0.0.1:1234"))
    assert len(result["files"]) == 1
    selected = result["files"][0]
    assert selected["hashes"]["sha256"] == "a" * 64
    assert selected["core-metadata"]["sha256"] == "b" * 64
    assert selected["upload-time"] == "2026-10-28T00:00:00Z"
    assert "+cpu" in selected["filename"]
    assert selected["url"].startswith("http://127.0.0.1:1234/")


def test_pytorch_index_is_not_used_for_unrelated_dependencies():
    class Client:
        def get(self, url, accept):
            assert url == "https://pypi.org/simple/filelock/"
            return b'{"name":"filelock","files":[]}'

    gateway = cpu["CPUGateway"](Client())
    assert json.loads(gateway.index("filelock", "http://127.0.0.1:1234"))["files"] == []
