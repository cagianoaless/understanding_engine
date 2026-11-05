"""Keep pdfplumber-specific extraction and its geometry in one module."""

import hashlib
import logging
import math
import platform
from importlib.metadata import version
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdftypes import PDFException, resolve1
from pdfminer.psparser import PSException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from . import __version__
from .contracts import ExtractionError, SCHEMA_VERSION, check_box, validate_extraction

LOGGER = logging.getLogger(__name__)
TEXT_SETTINGS = {
    "layout": False,
    "x_tolerance": 3,
    "y_tolerance": 3,
    "use_text_flow": False,
    "expand_ligatures": False,
    "line_dir": "ttb",
    "char_dir": "ltr",
    "line_dir_rotated": "ttb",
    "char_dir_rotated": "ltr",
}


def configuration() -> dict:
    return {
        "unicode_norm": None,
        "laparams": None,
        "deduplicate_characters": False,
        "crop_to_cropbox": False,
        "text_map": TEXT_SETTINGS.copy(),
        "raise_unicode_errors": True,
        "repair": False,
    }


def _warning(code: str, page_number: int | None, message: str,
             character_id: str | None = None) -> dict:
    return {"code": code, "page_number": page_number,
            "character_id": character_id, "message": message}


def _hash_stream(stream) -> str:
    stream.seek(0)
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stream.seek(0)
    return digest


def _raw_box(page, key: str) -> list | None:
    value = resolve1(page.page_obj.attrs.get(key))
    return None if value is None else [float(resolve1(n)) for n in value]


def _page_geometry(page) -> dict:
    attrs = page.page_obj.attrs
    user_unit = float(resolve1(attrs.get("UserUnit", 1)))
    raw_rotation = float(resolve1(attrs.get("Rotate", 0)))
    if (not math.isfinite(raw_rotation) or raw_rotation % 90 != 0 or
            not math.isfinite(user_unit) or user_unit <= 0):
        raise ExtractionError("malformed_geometry", f"page {page.page_number}: invalid rotation/UserUnit")
    return {
        "width": page.width,
        "height": page.height,
        "rotation": page.rotation,
        "raw_rotation": raw_rotation,
        "bbox": list(page.bbox),
        "mediabox": list(page.mediabox),
        "cropbox": list(page.cropbox),
        "raw_mediabox": _raw_box(page, "MediaBox"),
        "raw_cropbox": _raw_box(page, "CropBox"),
        "pdfminer_layout_bbox": list(page.layout.bbox),
        "initial_doctop": page.initial_doctop,
        "user_unit": user_unit,
    }


def _derived_lines(page, source_ids: dict) -> dict:
    # TextMap tokens retain the source object even when one glyph maps to
    # multiple Unicode code points. Avoid indexing tokens by string offsets.
    text_map = page.get_textmap(**TEXT_SETTINGS)
    lines = []
    text = []
    sources = {}

    def finish_line():
        chars = list(sources.values())
        bbox = ([min(c["x0"] for c in chars), min(c["top"] for c in chars),
                 max(c["x1"] for c in chars), max(c["bottom"] for c in chars)] if chars else None)
        lines.append({"text": "".join(text), "bbox": bbox,
                      "source_character_ids": list(sources)})
        text.clear()
        sources.clear()

    for token, char in text_map.tuples:
        for codepoint in token:
            if codepoint == "\n":
                finish_line()
            else:
                text.append(codepoint)
                if char is not None:
                    sources[source_ids[id(char)]] = char
    if text or lines:
        finish_line()
    derived = {"text": "\n".join(line["text"] for line in lines), "lines": lines}
    if derived["text"] != text_map.as_string:
        raise ExtractionError("invalid_contract", "Unsupported backend text-map rendering")
    return derived


def _extract_page(page, digest: str) -> tuple[dict, list]:
    number = page.page_number
    geometry = _page_geometry(page)
    warnings = []
    characters = []
    source_ids = {}
    for index, char in enumerate(page.chars):
        ident = f"{digest}:p{number}:c{index}"
        source_ids[id(char)] = ident
        bbox = [char["x0"], char["top"], char["x1"], char["bottom"]]
        check_box(bbox, ident)
        record = {
            "id": ident,
            "backend_index": index,
            "text": char["text"],
            "bbox": bbox,
            "backend_bbox_bottom_origin": [char["x0"], char["y0"], char["x1"], char["y1"]],
            "doctop": char["doctop"],
            "matrix": list(char["matrix"]),
            "upright": char["upright"],
            "fontname": char["fontname"],
            "size": char["size"],
        }
        characters.append(record)
        bounds = geometry["bbox"]
        if bbox[0] < bounds[0] or bbox[1] < bounds[1] or bbox[2] > bounds[2] or bbox[3] > bounds[3]:
            warnings.append(_warning("character_outside_page", number,
                                     "Character extends outside backend page bbox; retained unchanged.", ident))
        if bbox[0] == bbox[2] or bbox[1] == bbox[3]:
            warnings.append(_warning("degenerate_character_bbox", number,
                                     "Character has zero-area geometry; retained unchanged.", ident))
    derived = _derived_lines(page, source_ids)
    status = "text" if any(c["text"].strip() for c in characters) else "empty_text_layer"
    if status == "empty_text_layer":
        warnings.append(_warning("empty_text_layer", number,
                                 "No non-whitespace embedded text; this is not a parsing failure."))
    if geometry["raw_cropbox"] is not None:
        warnings.append(_warning("cropbox_not_applied", number,
                                 "Extraction uses MediaBox; characters outside CropBox may be retained."))
    if geometry["user_unit"] != 1:
        warnings.append(_warning("nondefault_user_unit", number,
                                 "Coordinates are backend units; UserUnit is retained, not applied."))
    page_data = {
        "page_number": number,
        "status": status,
        "geometry": geometry,
        "image_count": len(page.images),
        "characters": characters,
        "derived": derived,
    }
    return page_data, warnings


def extract_pdf(path: str | Path) -> dict:
    """Extract one PDF; raise ExtractionError for expected input failures.

    All encrypted PDFs, including ones with an empty user password, are rejected.
    A valid PDF with no non-whitespace text returns status='textless'.
    """
    try:
        stream = Path(path).open("rb")
    except FileNotFoundError as exc:
        raise ExtractionError("missing_input", "Input PDF does not exist") from exc
    except OSError as exc:
        raise ExtractionError("input_io_error", str(exc)) from exc
    try:
        with stream:
            digest = _hash_stream(stream)
            pages = []
            warnings = []
            with pdfplumber.open(stream, unicode_norm=None, laparams=None,
                                 raise_unicode_errors=True, repair=False) as pdf:
                if pdf.doc.encryption is not None:
                    raise ExtractionError("encrypted_pdf", "Encrypted PDFs are unsupported")
                for page in pdf.pages:
                    try:
                        page_data, page_warnings = _extract_page(page, digest)
                        pages.append(page_data)
                        warnings.extend(page_warnings)
                    finally:
                        page.close()
            if not pages:
                raise ExtractionError("invalid_pdf", "PDF contains no pages")
            if _hash_stream(stream) != digest:
                raise ExtractionError("input_changed", "Input PDF changed during extraction")
    except ExtractionError:
        raise
    except (PDFPasswordIncorrect, PDFEncryptionError) as exc:
        raise ExtractionError("encrypted_pdf", "Encrypted PDFs are unsupported") from exc
    except MalformedPDFException as exc:
        raise ExtractionError("malformed_geometry", "Backend rejected malformed PDF geometry") from exc
    except PdfminerException as exc:
        cause = exc.args[0] if exc.args else None
        if isinstance(cause, PDFEncryptionError):
            raise ExtractionError("encrypted_pdf", "Encrypted PDFs are unsupported") from exc
        raise ExtractionError("invalid_pdf", "PDF backend could not parse the document") from exc
    except (PDFException, PSException, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ExtractionError("invalid_pdf", f"PDF backend could not parse the document: {type(exc).__name__}") from exc
    except OSError as exc:
        raise ExtractionError("input_io_error", str(exc)) from exc
    result = {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": digest,
        "page_count": len(pages),
        "status": "text" if any(p["status"] == "text" for p in pages) else "textless",
        "parser": {
            "name": "understanding_engine",
            "version": __version__,
            "python": platform.python_version(),
            "dependencies": {name: version(name) for name in (
                "pdfplumber", "pdfminer.six", "Pillow", "pypdfium2", "jsonschema",
                "cryptography", "charset-normalizer", "cffi", "pycparser",
                "attrs", "jsonschema-specifications", "referencing", "rpds-py",
                "typing-extensions",
            )},
            "settings": configuration(),
        },
        "coordinate_system": "pdfplumber-native-v1",
        "pages": pages,
        "warnings": warnings,
    }
    validate_extraction(result)
    LOGGER.info("extracted document=%s pages=%d status=%s", digest, len(pages), result["status"])
    for warning in warnings:
        LOGGER.warning("%s document=%s page=%s character=%s", warning["code"], digest,
                       warning["page_number"], warning["character_id"])
    return result
