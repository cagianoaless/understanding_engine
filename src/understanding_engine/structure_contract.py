"""Source-aware invariants for the separate structure 0.1.0 contract."""

from collections import Counter
import hashlib
import json

from .contracts import ExtractionError, check_box, json_bytes, validate_extraction, validate_schema


def _require(condition, message):
    if not condition:
        raise ExtractionError("invalid_structure", message)


def _unique(items, label):
    ids = [item["id"] for item in items]
    _require(len(ids) == len(set(ids)), f"Duplicate {label} ID")
    return {item["id"]: item for item in items}


def validate_structure(structure: dict, extraction_bytes: bytes) -> None:
    from .structure import StructureSettings

    validate_schema(structure, "structure")
    extraction = json.loads(extraction_bytes)
    validate_extraction(extraction)
    source = structure["source"]
    _require(source["extraction_sha256"] == hashlib.sha256(extraction_bytes).hexdigest(), "Extraction byte hash differs")
    _require(source["pdf_sha256"] == extraction["source_sha256"] and
             source["parser"] == extraction["parser"] and
             source["extraction_schema_version"] == extraction["schema_version"], "Source provenance differs")
    StructureSettings(**structure["algorithm"]["settings"])
    identity = hashlib.sha256(json_bytes({"source": source["extraction_sha256"],
                                          "algorithm": structure["algorithm"]})).hexdigest()
    numbers = [page["page_number"] for page in structure["pages"]]
    _require(numbers == sorted(set(numbers)), "Page numbers must be sorted and unique")
    for page in structure["pages"]:
        number = page["page_number"]
        _require(number <= len(extraction["pages"]), "Unknown source page")
        original = extraction["pages"][number - 1]
        _require(page["geometry"] == original["geometry"] and page["status"] == original["status"], "Page metadata differs")
        chars = {c["id"]: c for c in original["characters"]}
        prefix = f"{identity}:p{number}:"
        columns = _unique(page["columns"], "column")
        lines = _unique(page["lines"], "line")
        regions = _unique(page["regions"], "region")
        expected_count = {"single_column": 1, "two_column": 2, "ambiguous": 0, "unknown": 0}[page["layout"]]
        _require(len(columns) == expected_count, "Layout and column count differ")
        if columns:
            bounds = original["geometry"]["bbox"]
            boxes = [c["bbox"] for c in columns.values()]
            _require(boxes[0][0] == bounds[0] and boxes[-1][2] == bounds[2] and
                     all(b[1] == bounds[1] and b[3] == bounds[3] and b[0] < b[2] for b in boxes) and
                     all(a[2] == b[0] for a, b in zip(boxes, boxes[1:])), "Column boxes do not partition native page")
        for kind, items in (("column", page["columns"]), ("line", page["lines"]), ("region", page["regions"])):
            for index, item in enumerate(items):
                _require(item["id"] == f"{prefix}{kind}{index}", "Unstable or foreign structure ID")
                check_box(item["bbox"], item["id"])
        for item in [*lines.values(), *regions.values()]:
            _require(item["column_id"] is None or item["column_id"] in columns, "Unknown column reference")
            refs = item["source_character_ids"]
            _require(refs and all(ref in chars for ref in refs), "Unknown/empty character references")
            _require(refs == sorted(refs, key=lambda ref: chars[ref]["backend_index"]), "Character references changed backend order")
            boxes = [chars[ref]["bbox"] for ref in refs]
            expected = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)]
            _require(item["bbox"] == expected, "Region/line box must enclose exactly its source characters")
            if item["column_id"] is not None:
                box = columns[item["column_id"]]["bbox"]
                _require(box[0] <= expected[0] and expected[2] <= box[2], "Text crosses assigned column")
        used_lines = []
        assigned = []
        for region in regions.values():
            _require(all(ref in lines for ref in region["line_ids"]), "Unknown line reference")
            used_lines.extend(region["line_ids"])
            assigned.extend(region["source_character_ids"])
            if region["type"] != "unknown":
                refs = [ref for lid in region["line_ids"] for ref in lines[lid]["source_character_ids"]]
                _require(Counter(refs) == Counter(region["source_character_ids"]), "Region/line membership differs")
                _require(all(lines[lid]["column_id"] == region["column_id"] for lid in region["line_ids"]), "Region crosses columns")
            else:
                _require(not region["line_ids"], "Unknown region must not hide grouped lines")
        _require(Counter(used_lines) == Counter(lines.keys()), "Lines must belong to exactly one region")
        line_chars = [ref for line in lines.values() for ref in line["source_character_ids"]]
        _require(len(line_chars) == len(set(line_chars)), "Character belongs to multiple lines")
        unassigned = [item["character_id"] for item in page["unassigned_characters"]]
        _require(Counter(assigned + unassigned) == Counter(chars.keys()), "Characters missing, duplicated, or foreign")
        adjacency = {rid: set() for rid in regions}
        pairs = set()
        for relation in page["relations"]:
            a, b = relation["before"], relation["after"]
            _require(a in regions and b in regions and a != b, "Invalid order endpoints")
            _require((a, b) not in pairs, "Duplicate order relation")
            pairs.add((a, b))
            adjacency[a].add(b)
            left, right = regions[a], regions[b]
            _require(left["type"] != "unknown" and right["type"] != "unknown" and
                     left["bbox"][3] <= right["bbox"][1], "Order lacks geometric separation")
            if relation["rule"] == "same_column_vertical_separation":
                _require(left["column_id"] is not None and left["column_id"] == right["column_id"], "Order crosses columns")
            else:
                _require(left["type"] == "heading" and left["column_id"] is None and len(columns) == 2,
                         "Spanning order lacks a spanning heading")
        # Kahn's algorithm avoids recursive depth limits on large pages.
        incoming = Counter(b for targets in adjacency.values() for b in targets)
        ready = [rid for rid in regions if incoming[rid] == 0]
        visited = 0
        while ready:
            rid = ready.pop()
            visited += 1
            for target in adjacency[rid]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
        _require(visited == len(regions), "Reading-order cycle")
        ambiguous = set()
        for ambiguity in page["ambiguities"]:
            a, b = ambiguity["region_ids"]
            _require(a in regions and b in regions and a != b, "Invalid ambiguity endpoints")
            pair = frozenset([a, b])
            _require(pair not in ambiguous, "Duplicate ambiguity")
            ambiguous.add(pair)
            reachable, pending = set(), [a]
            while pending:
                node = pending.pop()
                if node not in reachable:
                    reachable.add(node)
                    pending.extend(adjacency[node])
            _require(b not in reachable, "Ambiguous pair is ordered by accepted edges")
            reachable, pending = set(), [b]
            while pending:
                node = pending.pop()
                if node not in reachable:
                    reachable.add(node)
                    pending.extend(adjacency[node])
            _require(a not in reachable, "Ambiguous pair is ordered by accepted edges")
        _require(page["unresolved_content"], "Non-text/semantic limitations must be explicit")
        for unresolved in page["unresolved_content"]:
            check_box(unresolved["bbox"], "unresolved content")
            _require(unresolved["bbox"] == original["geometry"]["bbox"] and
                     unresolved["source_image_count"] == original["image_count"], "Unresolved content provenance differs")


def resolve_region(structure: dict, extraction_bytes: bytes, region_id: str) -> list[dict]:
    """Resolve original units, preserving their Unicode and backend order."""
    validate_structure(structure, extraction_bytes)
    extraction = json.loads(extraction_bytes)
    for page in structure["pages"]:
        for region in page["regions"]:
            if region["id"] == region_id:
                chars = {c["id"]: c for c in extraction["pages"][page["page_number"] - 1]["characters"]}
                return [chars[ref] for ref in region["source_character_ids"]]
    raise ExtractionError("invalid_structure", "Unknown region ID")
