"""Publish the three artifacts together, without replacing previous results."""

import hashlib
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .contracts import ExtractionError, SCHEMA_VERSION, json_bytes, validate_schema
from .pdf_parser import extract_pdf

LOGGER = logging.getLogger(__name__)


def paper_text(extraction: dict) -> str:
    """Explicit page headers and form-feed boundaries, including empty pages."""
    return "\n\f\n".join(
        f"=== Page {page['page_number']} ===\n{page['derived']['text']}\n"
        for page in extraction["pages"]
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_to_directory(input_pdf: str | Path, output_directory: str | Path) -> dict:
    """Return run metadata only after the complete directory is published.

    A sibling exclusive lock coordinates invocations of this application. Staging
    and destination are on the same filesystem. Fatal failures publish nothing.
    """
    started = _now()
    start = time.perf_counter()
    destination = Path(output_directory).absolute()
    staging = None
    lock = destination.with_name(f".{destination.name}.lock")
    owns_lock = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ExtractionError("output_busy", "Output is locked by another invocation or stale lock") from exc
        owns_lock = True
        os.close(descriptor)
        if os.path.lexists(destination):
            raise ExtractionError("output_exists", "Output directory already exists; choose a new destination")
        extraction = extract_pdf(input_pdf)
        artifacts = {"extraction.json": json_bytes(extraction),
                     "paper.txt": paper_text(extraction).encode("utf-8")}
        statistics = {
            "page_count": extraction["page_count"],
            "character_count": sum(len(p["characters"]) for p in extraction["pages"]),
            "derived_character_count": sum(len(p["derived"]["text"]) for p in extraction["pages"]),
            "empty_page_count": sum(p["status"] == "empty_text_layer" for p in extraction["pages"]),
            "image_count": sum(p["image_count"] for p in extraction["pages"]),
        }
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
        for name, content in artifacts.items():
            with (staging / name).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        run = {
            "schema_version": SCHEMA_VERSION,
            "status": "textless" if extraction["status"] == "textless" else "success",
            "input_path": str(Path(input_pdf).absolute()),
            "output_directory": str(destination),
            "started_at_utc": started,
            "finished_at_utc": _now(),
            "duration_seconds": time.perf_counter() - start,
            "source_sha256": extraction["source_sha256"],
            "configuration": extraction["parser"]["settings"],
            "statistics": statistics,
            "artifacts": {name: hashlib.sha256(content).hexdigest() for name, content in artifacts.items()},
            "warnings": extraction["warnings"],
        }
        validate_schema(run, "run")
        with (staging / "run.json").open("xb") as stream:
            stream.write(json_bytes(run))
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck while holding the lock; existing destinations are never reused.
        if os.path.lexists(destination):
            raise ExtractionError("output_exists", "Destination appeared during extraction")
        os.rename(staging, destination)
        staging = None
        return run
    except OSError as exc:
        raise ExtractionError("output_io_error", str(exc)) from exc
    finally:
        if staging is not None:
            try:
                shutil.rmtree(staging)
            except OSError:
                LOGGER.warning("staging_cleanup_failed: hidden staging directory remains")
        if owns_lock:
            try:
                lock.unlink()
            except OSError:
                # Publication may already have succeeded. A cleanup problem must
                # not turn a complete committed result into a reported failure.
                LOGGER.warning("lock_cleanup_failed: sibling lock remains")
