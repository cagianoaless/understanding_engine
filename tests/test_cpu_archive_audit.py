"""Safety regressions use synthetic ZIPs; no network or neural dependencies."""

import json
from pathlib import Path
import runpy
import zipfile

import pytest


MODULE = Path(__file__).resolve().parents[1] / "evaluation/experiments/006b/runs/2026-11-09-cpu-archive-audit/archive_audit.py"
audit = runpy.run_path(str(MODULE))


def test_frozen_exact_cpu_allowlist():
    rows = audit["load_allowlist"]()
    assert len(rows) == 103
    assert sum(r["bytes"] for r in rows) == 379580121


@pytest.mark.parametrize("values", [
    {"host_available_bytes":audit["HOST_RESERVE"]-1,"allocated_bytes":0},
    {"host_available_bytes":audit["HOST_RESERVE"]+1024**3,"allocated_bytes":audit["STORAGE_CAP"]},
])
def test_both_resource_limits_stop(values):
    with pytest.raises(ValueError, match="STOP"):
        audit["check_limits"](values)


def test_redirects_never_expand_source_allowlist():
    with pytest.raises(ValueError, match="redirect"):
        audit["NoRedirect"]().redirect_request(None,None,None,None,None,"https://example.com/a.whl")


def make_zip(path, extra="module.py"):
    with zipfile.ZipFile(path, "w") as stream:
        stream.writestr("example-1.0.dist-info/METADATA", "Name: example\nVersion: 1.0\n")
        stream.writestr("example-1.0.dist-info/licenses/LICENSE", "Permission is hereby granted, free of charge")
        stream.writestr(extra, b"abcdef")


def test_zip_sizes_and_bounded_notices_without_code_extraction(tmp_path):
    path = tmp_path / "a.whl"
    make_zip(path)
    notices=tmp_path/"notices";notices.mkdir()
    result, used=audit["inspect_zip"](path,{"name":"example","version":"1.0","filename":"a.whl"},notices,1024)
    assert result["file_count"] == 3
    assert result["zip_uncompressed_logical_bytes"] == 77
    assert used == 44 and result["notices"][0]["signatures"] == ["MIT_grant"]
    assert not (tmp_path/"module.py").exists()
    assert not (tmp_path/"example-1.0.dist-info").exists()


def test_notice_limit_does_not_read_oversize_entry(tmp_path):
    path=tmp_path/"a.whl";make_zip(path)
    notices=tmp_path/"notices";notices.mkdir()
    result, used=audit["inspect_zip"](path,{"name":"example","version":"1.0","filename":"a.whl"},notices,1)
    assert used == 0 and result["notices"][0]["status"] == "UNREAD_BOUNDED_LIMIT"
    assert not list(notices.iterdir())


def test_unsafe_zip_path_rejected(tmp_path):
    path=tmp_path/"a.whl";make_zip(path,"../escape")
    notices=tmp_path/"notices";notices.mkdir()
    with pytest.raises(ValueError,match="Unsafe"):
        audit["inspect_zip"](path,{"name":"example","version":"1.0","filename":"a.whl"},notices,1024)


def test_wheel_identity_mismatch_rejected(tmp_path):
    path=tmp_path/"a.whl";make_zip(path)
    notices=tmp_path/"notices";notices.mkdir()
    with pytest.raises(ValueError,match="identity"):
        audit["inspect_zip"](path,{"name":"example","version":"2.0","filename":"a.whl"},notices,1024)


def test_license_module_code_is_not_a_notice():
    assert not audit["notice_file"]("setuptools/_vendor/packaging/licenses/__init__.py")
    assert audit["notice_file"]("example.dist-info/licenses/README.rst")


def test_nested_vendor_metadata_does_not_replace_root_identity(tmp_path):
    path=tmp_path/"a.whl";make_zip(path)
    with zipfile.ZipFile(path,"a") as stream:
        stream.writestr("example/_vendor/other-2.0.dist-info/METADATA","Name: other\nVersion: 2.0\n")
    notices=tmp_path/"notices";notices.mkdir()
    result, used=audit["inspect_zip"](path,{"name":"example","version":"1.0","filename":"a.whl"},notices,1024)
    assert result["name"]=="example" and result["file_count"]==4
