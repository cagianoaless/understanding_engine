import hashlib
import json
import os
import subprocess
import sys

import pytest

from understanding_engine import output
from understanding_engine.__main__ import main
from understanding_engine.contracts import ExtractionError, validate_schema


def test_three_outputs_and_run_manifest(fixtures, tmp_path):
    destination = tmp_path / "parsed"
    assert main([str(fixtures / "multi.pdf"), "--output-dir", str(destination)]) == 0
    assert {p.name for p in destination.iterdir()} == {"extraction.json", "paper.txt", "run.json"}
    run = json.loads((destination / "run.json").read_text())
    validate_schema(run, "run")
    assert run["status"] == "success"
    assert run["statistics"]["page_count"] == 2
    assert run["statistics"]["character_count"] == 21
    assert run["duration_seconds"] >= 0
    for name, digest in run["artifacts"].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
    assert (destination / "paper.txt").read_text() == "=== Page 1 ===\nFirst page\n\n\f\n=== Page 2 ===\nSecond page\n"


def test_subprocess_reproducibility_with_different_hash_seeds(fixtures, tmp_path):
    for seed in ("1", "42"):
        result = subprocess.run([
            sys.executable, "-m", "understanding_engine", str(fixtures / "unicode.pdf"),
            "--output-dir", str(tmp_path / seed),
        ], env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
    for name in ("extraction.json", "paper.txt"):
        assert (tmp_path / "1" / name).read_bytes() == (tmp_path / "42" / name).read_bytes()


@pytest.mark.parametrize("name", ["empty", "image"])
def test_textless_exit_code_and_artifacts(fixtures, tmp_path, name):
    destination = tmp_path / name
    assert main([str(fixtures / f"{name}.pdf"), "--output-dir", str(destination)]) == 3
    run = json.loads((destination / "run.json").read_text())
    assert run["status"] == "textless"
    assert run["statistics"]["empty_page_count"] == 1
    assert (destination / "paper.txt").read_text() == "=== Page 1 ===\n\n"


@pytest.mark.parametrize("name,code", [("invalid", "invalid_pdf"), ("missing", "missing_input"),
    ("encrypted", "encrypted_pdf"), ("encrypted_empty_password", "encrypted_pdf"),
    ("bad_rotation", "malformed_geometry")])
def test_failure_publishes_nothing(fixtures, tmp_path, capsys, name, code):
    destination = tmp_path / "failed"
    assert main([str(fixtures / f"{name}.pdf"), "--output-dir", str(destination)]) == 2
    assert code in capsys.readouterr().err
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_existing_output_never_replaced(fixtures, tmp_path):
    destination = tmp_path / "parsed"
    output.parse_to_directory(fixtures / "single.pdf", destination)
    before = {p.name: p.read_bytes() for p in destination.iterdir()}
    with pytest.raises(ExtractionError, match="already exists"):
        output.parse_to_directory(fixtures / "multi.pdf", destination)
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == before


def test_existing_empty_directory_and_symlink_refused(fixtures, tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    symlink = tmp_path / "dangling"
    symlink.symlink_to(tmp_path / "absent")
    for path in (destination, symlink):
        with pytest.raises(ExtractionError) as caught:
            output.parse_to_directory(fixtures / "single.pdf", path)
        assert caught.value.code == "output_exists"
    assert symlink.is_symlink()
    assert not (tmp_path / "absent").exists()


def test_sibling_lock_refuses_concurrent_writer(fixtures, tmp_path):
    lock = tmp_path / ".parsed.lock"
    lock.write_text("owned by another process")
    with pytest.raises(ExtractionError) as caught:
        output.parse_to_directory(fixtures / "single.pdf", tmp_path / "parsed")
    assert caught.value.code == "output_busy"
    assert lock.read_text() == "owned by another process"


@pytest.mark.parametrize("operation", ["fsync", "rename"])
def test_write_or_publication_failure_cleans_staging(fixtures, tmp_path, monkeypatch, operation):
    def fail(*args):
        raise OSError("injected write failure")
    monkeypatch.setattr(output.os, operation, fail)
    with pytest.raises(ExtractionError) as caught:
        output.parse_to_directory(fixtures / "single.pdf", tmp_path / "failed")
    assert caught.value.code == "output_io_error"
    assert list(tmp_path.iterdir()) == []


def test_later_page_failure_cannot_publish_partial_document(fixtures, tmp_path, monkeypatch):
    from understanding_engine import pdf_parser
    original = pdf_parser._extract_page

    def fail_on_second_page(page, digest):
        if page.page_number == 2:
            raise ExtractionError("invalid_pdf", "injected second page failure")
        return original(page, digest)
    monkeypatch.setattr(pdf_parser, "_extract_page", fail_on_second_page)
    with pytest.raises(ExtractionError):
        output.parse_to_directory(fixtures / "multi.pdf", tmp_path / "failed")
    assert list(tmp_path.iterdir()) == []


def test_destination_created_during_run_is_preserved(fixtures, tmp_path, monkeypatch):
    destination = tmp_path / "parsed"
    original = output.extract_pdf

    def create_destination(path):
        data = original(path)
        destination.mkdir()
        (destination / "sentinel").write_text("other writer")
        return data
    monkeypatch.setattr(output, "extract_pdf", create_destination)
    with pytest.raises(ExtractionError) as caught:
        output.parse_to_directory(fixtures / "single.pdf", destination)
    assert caught.value.code == "output_exists"
    assert (destination / "sentinel").read_text() == "other writer"
    assert list(tmp_path.iterdir()) == [destination]


def test_lock_cleanup_failure_does_not_misreport_published_run(fixtures, tmp_path, monkeypatch, caplog):
    from pathlib import Path
    original = Path.unlink

    def fail_lock(path, *args, **kwargs):
        if path.name == ".parsed.lock":
            raise OSError("injected cleanup failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_lock)
    run = output.parse_to_directory(fixtures / "single.pdf", tmp_path / "parsed")
    assert run["status"] == "success"
    assert (tmp_path / "parsed" / "run.json").is_file()
    assert "lock_cleanup_failed" in caplog.text


def test_normal_logs_do_not_contain_paper_text(fixtures, tmp_path, capsys):
    assert main([str(fixtures / "single.pdf"), "--output-dir", str(tmp_path / "parsed")]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Scientific PDF" not in captured.err
    assert "document=" in captured.err


def test_extraction_does_not_need_network(fixtures, tmp_path, monkeypatch):
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    assert output.parse_to_directory(fixtures / "single.pdf", tmp_path / "parsed")["status"] == "success"
