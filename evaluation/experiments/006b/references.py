"""Offline integrity checks for frozen development references, not a parser."""

import hashlib
import json
import math
from pathlib import Path


def verify_freeze(directory):
    directory = Path(directory)
    freeze = json.loads((directory / "freeze.json").read_text())
    for filename, expected in freeze["files"].items():
        actual = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Frozen input changed: " + filename)
    return freeze


def validate_annotations(data, geometries):
    docs = {d["document_id"]: d["source_sha256"] for d in data["documents"]}
    seen = set()

    def identify(value):
        if value in seen:
            raise ValueError("Duplicate identifier")
        seen.add(value)

    for page in data["pages"]:
        identify(page["id"])
        if page["source_sha256"] != docs[page["document_id"]]:
            raise ValueError("Document hash mismatch")
        if page["verification"] != "agent_visual_checked":
            raise ValueError("Unreviewed reference cannot be human verified")
        g = geometries[page["id"]]

        def box(values):
            if (len(values) != 4 or not all(math.isfinite(v) for v in values)
                    or not 0 <= values[0] < values[2] <= g["width"]
                    or not 0 <= values[1] < values[3] <= g["height"]):
                raise ValueError("Malformed reference geometry")

        for window in page["windows"]:
            box(window)
        region_ids = set()
        for region in page["regions"]:
            identify(region["id"])
            region_ids.add(region["id"])
            box(region["bbox"])
            if (region["verification"] != "agent_visual_checked"
                    or region["human_reviewer"] is not None):
                raise ValueError("No human review has occurred")
            x0, top, x1, bottom = region["bbox"]
            if not any(w[0] <= x0 and w[1] <= top and x1 <= w[2] and bottom <= w[3]
                       for w in page["windows"]):
                raise ValueError("Reference outside scoring windows")
        for pair in page["order_pairs"]:
            identify(pair["id"])
            if (pair["before"] not in region_ids or pair["after"] not in region_ids
                    or pair["before"] == pair["after"]):
                raise ValueError("Invalid order endpoint")
        for group in page["ambiguous_order_groups"]:
            if not set(group["regions"]) <= region_ids or not group["reason"]:
                raise ValueError("Invalid ambiguity group")
        for decision in page["paragraph_decisions"]:
            identify(decision["id"])
            if len(decision["line_strips"]) != 2 or len(decision["source_character_ids"]) != 2:
                raise ValueError("Paragraph decision needs two source probes")
            for strip, refs in zip(decision["line_strips"], decision["source_character_ids"]):
                box(strip)
                prefix = f'{page["source_sha256"]}:p{page["page_number"]}:c'
                if not refs or len(refs) != len(set(refs)) or any(
                        not r.startswith(prefix) or not r[len(prefix):].isdigit() for r in refs):
                    raise ValueError("Invalid source-character reference")
    return {"pages": len(data["pages"]),
            "regions": sum(len(p["regions"]) for p in data["pages"]),
            "order_pairs": sum(len(p["order_pairs"]) for p in data["pages"]),
            "paragraph_decisions": sum(len(p["paragraph_decisions"]) for p in data["pages"])}
