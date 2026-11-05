"""Versioned JSON contracts plus invariants JSON Schema cannot express."""

import json
import math
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0.0"


class ExtractionError(Exception):
    """An expected, actionable extraction or publication failure."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@lru_cache
def validator(name: str) -> Draft202012Validator:
    schema = json.loads(files("understanding_engine").joinpath(
        "schemas", f"{name}.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(data: dict, name: str) -> None:
    error = next(validator(name).iter_errors(data), None)
    if error:
        path = "/".join(str(part) for part in error.absolute_path)
        raise ExtractionError("invalid_contract", f"{name}/{path}: {error.message}")


def check_box(box: list, label: str, *, allow_reversed: bool = False) -> None:
    if (len(box) != 4 or any(isinstance(n, bool) or not isinstance(n, (int, float))
                             or not math.isfinite(n) for n in box)):
        raise ExtractionError("malformed_geometry", f"{label}: expected four finite numbers")
    if not allow_reversed and (box[0] > box[2] or box[1] > box[3]):
        raise ExtractionError("malformed_geometry", f"{label}: inverted bounding box")


def validate_extraction(data: dict) -> None:
    validate_schema(data, "extraction")
    if data["page_count"] != len(data["pages"]):
        raise ExtractionError("invalid_contract", "page_count does not match pages")
    ids = set()
    for page_number, page in enumerate(data["pages"], 1):
        if page["page_number"] != page_number:
            raise ExtractionError("invalid_contract", "Pages must be contiguous and one-based")
        geometry = page["geometry"]
        for key in ("bbox", "mediabox", "cropbox", "pdfminer_layout_bbox"):
            check_box(geometry[key], f"page {page_number}/{key}")
        # Original PDF rectangles can legally specify opposite corners in either order.
        for key in ("raw_mediabox", "raw_cropbox"):
            raw = geometry[key]
            if raw is not None:
                check_box(raw, f"page {page_number}/{key}", allow_reversed=True)
        for key in ("raw_rotation", "initial_doctop", "user_unit"):
            if not math.isfinite(geometry[key]):
                raise ExtractionError("malformed_geometry", f"page {page_number}: non-finite {key}")
        if geometry["raw_rotation"] % 360 != geometry["rotation"]:
            raise ExtractionError("malformed_geometry", f"page {page_number}: inconsistent rotation")
        width, height = geometry["width"], geometry["height"]
        if (not math.isfinite(width) or not math.isfinite(height) or
                width <= 0 or height <= 0 or
                not math.isclose(width, geometry["bbox"][2] - geometry["bbox"][0]) or
                not math.isclose(height, geometry["bbox"][3] - geometry["bbox"][1])):
            raise ExtractionError("malformed_geometry", f"page {page_number}: invalid dimensions")
        chars = page["characters"]
        by_id = {}
        for index, char in enumerate(chars):
            expected = f"{data['source_sha256']}:p{page_number}:c{index}"
            if char["id"] != expected or char["id"] in ids or char["backend_index"] != index:
                raise ExtractionError("invalid_contract", "Invalid character ID or extraction index")
            ids.add(char["id"])
            by_id[char["id"]] = char
            check_box(char["bbox"], char["id"])
            check_box(char["backend_bbox_bottom_origin"], char["id"])
            for value in (*char["matrix"], char["doctop"], char["size"]):
                if not math.isfinite(value):
                    raise ExtractionError("malformed_geometry", "Non-finite character transform")
        for line in page["derived"]["lines"]:
            if line["bbox"] is not None:
                check_box(line["bbox"], f"page {page_number}/derived line")
            if any(ref not in by_id for ref in line["source_character_ids"]):
                raise ExtractionError("invalid_contract", "Derived line references an unknown character")
        if page["derived"]["text"] != "\n".join(line["text"] for line in page["derived"]["lines"]):
            raise ExtractionError("invalid_contract", "Derived text does not match derived lines")
        has_text = any(c["text"].strip() for c in chars)
        if (page["status"] == "text") != has_text:
            raise ExtractionError("invalid_contract", "Page status contradicts character layer")
    has_text = any(page["status"] == "text" for page in data["pages"])
    if (data["status"] == "text") != has_text:
        raise ExtractionError("invalid_contract", "Document status contradicts pages")


def json_bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")
