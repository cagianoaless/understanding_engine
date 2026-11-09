"""Offline guard/tag regressions; not empirical candidate or resource results."""

from pathlib import Path
import runpy

import pytest


AUDIT = Path(__file__).resolve().parents[1] / "evaluation/experiments/006b/runs/2026-11-09-linux-preflight/audit.py"
audit = runpy.run_path(str(AUDIT))


@pytest.mark.parametrize("url", [
    "https://files.pythonhosted.org/path/model.whl",
    "https://files.pythonhosted.org/path/archive.tar.gz",
    "https://huggingface.co/model.safetensors",
    "https://other.example/file.whl.metadata",
    "http://files.pythonhosted.org/file.whl.metadata",
    "https://user:secret@pypi.org/simple/docling/",
])
def test_payloads_credentials_and_unapproved_origins_are_refused(url):
    assert not audit["permitted_url"](url)


def test_metadata_sidecars_and_version_json_are_allowed():
    assert audit["permitted_url"]("https://files.pythonhosted.org/path/a.whl.metadata")
    assert audit["permitted_url"]("https://pypi.org/pypi/docling/2.148.0/json")


@pytest.mark.parametrize("filename", [
    "torch-2.15.0-cp311-cp311-macosx_14_0_arm64.whl",
    "torch-2.15.0-cp311-cp311-manylinux_2_28_x86_64.whl",
    "torch-2.15.0-cp312-cp312-manylinux_2_28_aarch64.whl",
    "torch-2.15.0-cp311-cp311-musllinux_1_2_aarch64.whl",
    "torch-2.15.0-cp311-cp311-manylinux_2_40_aarch64.whl",
])
def test_native_mac_and_wrong_linux_python_abi_tags_are_not_reused(filename):
    assert audit["wheel_rank"](filename) is None


def test_cp311_glibc_and_abi3_wheels_are_compatible():
    assert audit["wheel_rank"]("torch-2.15.0-cp311-cp311-manylinux_2_28_aarch64.whl") is not None
    assert audit["wheel_rank"]("example-1.0-cp310-abi3-manylinux2014_aarch64.whl") is not None
    assert audit["wheel_rank"]("example-1.0-py3-none-any.whl") is not None


@pytest.mark.parametrize("info", [{}, {"license": "BSD"}, {"license_expression": "not-a-license"},
                                   {"license_expression": "LicenseRef-NVIDIA-Proprietary"}])
def test_missing_or_ambiguous_license_is_unknown(info):
    result = audit["declared_license"](info)
    assert result["declared_expression_status"] == "UNKNOWN"
    assert result["full_clearance"] == "UNKNOWN"


def test_valid_declaration_does_not_invent_full_license_clearance():
    result = audit["declared_license"]({"license_expression": "MIT"})
    assert result["declared_expression_status"] == "PASS"
    assert result["full_clearance"] == "UNKNOWN"


def test_gateway_refuses_wheel_before_calling_upstream():
    class NoNetworkClient:
        def get(self, *args):
            raise AssertionError("The upstream must never be called for a wheel body")

    gateway = audit["Gateway"](NoNetworkClient())
    handler = gateway.handler()
    request = object.__new__(handler)
    request.path = "/files/x/example.whl"
    errors = []
    request.send_error = lambda code, message: errors.append(code)
    handler.do_GET(request)
    assert errors == [403]
    assert gateway.stop.is_set() and len(gateway.blocked) == 1


def test_invalid_legacy_index_filename_cannot_abort_current_wheel_resolution():
    import json

    class IndexClient:
        def get(self, *args):
            return json.dumps({"files": [
                {"filename": "pydantic-0.18-py36+-none-any.whl", "url": "https://files.pythonhosted.org/old.whl"},
                {"filename": "pydantic-2.14.3-py3-none-any.whl", "url": "https://files.pythonhosted.org/new.whl"},
            ]}).encode()

    gateway = audit["Gateway"](IndexClient())
    result = json.loads(gateway.index("pydantic", "http://127.0.0.1:1234"))
    assert len(result["files"]) == 1
    assert len(gateway.invalid_index_filenames) == 1
    assert not gateway.stop.is_set()


inventory = runpy.run_path(str(AUDIT.with_name("inventory.py")))


@pytest.mark.parametrize("filename", ["model.safetensors", "model.bin", "pytorch_model.bin"])
def test_pinned_weight_urls_are_never_allowed(filename):
    url = "https://huggingface.co/docling-project/docling-layout-heron/resolve/" + audit["REVISION"] + "/" + filename
    assert not inventory["model_url_allowed"](url)


def test_pinned_model_card_and_small_configs_are_allowed():
    base = "https://huggingface.co/docling-project/docling-layout-heron/resolve/" + audit["REVISION"] + "/"
    for filename in ["README.md", "config.json", "preprocessor_config.json"]:
        assert inventory["model_url_allowed"](base + filename)
    assert not inventory["model_url_allowed"](base.replace(audit["REVISION"], "main") + "config.json")


def test_transitive_extra_dependency_cannot_be_omitted_from_complete_closure():
    records = [
        {"name": "docling", "version": "2.148.0", "requires_python": ">=3.10", "requires_dist": ["demo[standard]==1"]},
        {"name": "demo", "version": "1", "requires_python": None, "requires_dist": ['missing==1; extra == "standard"']},
    ]
    errors, extras = inventory["closure_errors"](records)
    assert "standard" in extras["demo"]
    assert any("missing" in error for error in errors)


def test_linux_arm_marker_is_evaluated_independently_of_host_mac():
    records = [{"name": "docling", "version": "2.148.0", "requires_python": ">=3.10",
                "requires_dist": ['linuxonly>=1; sys_platform == "linux" and platform_machine == "aarch64"']}]
    errors, _ = inventory["closure_errors"](records)
    assert any("linuxonly" in error for error in errors)
