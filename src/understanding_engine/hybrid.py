"""Offline, source-authoritative hybrid construction. No candidate execution.

The inclusive-center and BOTTOMLEFT policies follow frozen Experiment 006b.
These few geometric operations live here so the installed package never imports
an experiment/scorer. Historical code, thresholds and outputs remain untouched.
"""

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import math

from .contracts import ExtractionError, check_box, json_bytes, validate_extraction, validate_schema
from .hybrid_contract import HYBRID_VERSION, HybridDocument, LayoutPrediction


def _require(condition, message):
    if not condition:
        raise ExtractionError("invalid_hybrid", message)


def _digest(value):
    try:
        return hashlib.sha256(json_bytes(value)).hexdigest()
    except (TypeError, ValueError) as exc:
        raise ExtractionError("invalid_hybrid", "Evidence must be finite, JSON-serializable data") from exc


def _inside(box, point):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _center(box):
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)


def _box(box, geometry):
    check_box(box, "hybrid region")
    bounds = geometry["bbox"]
    _require(bounds[0] <= box[0] < box[2] <= bounds[2] and
             bounds[1] <= box[1] < box[3] <= bounds[3], "Region outside original page or degenerate")
    return box


def _docling_geometry(geometry, size):
    w, h = geometry["width"], geometry["height"]
    _require(geometry["rotation"] == 0 and geometry["raw_rotation"] == 0 and geometry["user_unit"] == 1,
             "Unsupported Docling rotation/UserUnit transformation")
    for field in ["bbox", "mediabox", "cropbox", "raw_mediabox", "pdfminer_layout_bbox"]:
        _require(geometry[field] == [0, 0, w, h], "Ambiguous Docling crop/media/coordinate frame")
    _require(geometry["raw_cropbox"] is None or geometry["raw_cropbox"] == [0, 0, w, h], "Ambiguous raw crop")
    _require(size == {"width": w, "height": h}, "Native page dimensions differ from original")


def _convert(native, geometry):
    check_box([native[k] for k in ["l", "t", "r", "b"]], "native bbox", allow_reversed=True)
    if native["coord_origin"] == "BOTTOMLEFT":
        result = [native["l"], geometry["height"]-native["t"], native["r"], geometry["height"]-native["b"]]
    elif native["coord_origin"] == "TOPLEFT":
        result = [native[k] for k in ["l", "t", "r", "b"]]
    else:
        raise ExtractionError("invalid_hybrid", "Unknown coordinate origin")
    return _box(result, geometry)


def _hierarchy(items):
    by_id = {i["native_id"]: i for i in items}
    _require(len(by_id) == len(items), "Duplicate native item ID")
    for item in items:
        parent, children = item["parent_id"], item["children_ids"]
        _require(len(children) == len(set(children)), "Duplicate native child reference")
        _require(parent is None or parent in by_id and item["native_id"] in by_id[parent]["children_ids"], "Contradictory native parent reference")
        _require(all(c in by_id and by_id[c]["parent_id"] == item["native_id"] for c in children), "Contradictory native child reference")
    # Iterative traversal avoids recursion limits on supplied hierarchies.
    visited = set()
    stack = [(i["native_id"], False) for i in items if i["parent_id"] is None]
    while stack:
        node, leaving = stack.pop()
        if leaving:
            continue
        _require(node not in visited, "Repeated hierarchy node")
        visited.add(node)
        stack.extend((c, False) for c in reversed(by_id[node]["children_ids"]))
    _require(visited == set(by_id), "Cyclic or unreachable native hierarchy")
    return by_id


def _item(native_id, pointer, label, parent=None, children=None, text=None, confidence=None):
    _require(isinstance(native_id, str) and native_id and isinstance(label, str), "Invalid native identity/label")
    _require(text is None or isinstance(text, str), "Model diagnostic text must be a string or null")
    return {"native_id": native_id, "native_pointer": pointer, "label": label, "parent_id": parent,
            "children_ids": children or [], "diagnostic_model_text": text, "confidence": confidence,
            "region_ids": [], "geometry_status": "unavailable"}


def _region(evidence_id, item, index, page, native_box, box, claims=None, supports_native=False):
    return {"id": "hybrid:"+_digest({"evidence": evidence_id, "item": item["native_id"], "box": index}),
            "native_item_id": item["native_id"], "native_provenance_index": index, "page_number": page,
            "native_bbox": deepcopy(native_box), "bbox": list(box), "geometric_character_ids": [], "native_membership": [],
            "status": "unmatched", "_claims": claims or [], "_supports_native": supports_native}


def _docling(prediction, source, evidence_id):
    native = prediction["native"]; document = native["document"]
    numbers = []
    for key, page in document["pages"].items():
        number = int(key)
        _require(str(number) == key and type(page["page_no"]) is int and page["page_no"] == number and 1 <= number <= source["page_count"], "Unknown/duplicate native page")
        _docling_geometry(source["pages"][number-1]["geometry"], page["size"])
        numbers.append(number)
    _require(numbers, "No native pages")
    items, regions, nodes = [], [], {}
    for key in sorted(document):
        collection = document[key]
        entries = [("#/"+key, collection)] if key in {"body", "furniture"} else (
            [(f"#/{key}/{i}", value) for i, value in enumerate(collection)] if isinstance(collection, list) else [])
        for pointer, node in entries:
            _require(node["self_ref"] == pointer, "Native reference is not its document pointer")
            confidence = None
            if node.get("confidence") is not None:
                value = node["confidence"]
                _require(type(value) in (int, float) and math.isfinite(value), "Invalid supplied confidence")
                confidence = {"value": value, "native_pointer": pointer+"/confidence"}
            parent = node.get("parent")
            item = _item(pointer, pointer, node["label"],
                None if parent is None else parent["$ref"], [c["$ref"] for c in node.get("children", [])],
                node.get("text"), confidence)
            items.append(item); nodes[pointer] = node
            claims = node.get("source_character_ids", [])
            _require(isinstance(claims, list) and all(isinstance(c, str) for c in claims), "Invalid native source claims")
            _require(not claims or node.get("prov"), "Unsupported source claims on geometry-free Docling item")
            for i, prov in enumerate(node.get("prov", [])):
                number = prov["page_no"]
                _require(type(number) is int and number in numbers, "Provenance refers to an unknown page")
                box = _convert(prov["bbox"], source["pages"][number-1]["geometry"])
                regions.append(_region(evidence_id, item, i, number, prov["bbox"], box, claims))
                item["region_ids"].append(regions[-1]["id"])
            item["geometry_status"] = "present" if item["region_ids"] else "unavailable"
    by_id = _hierarchy(items)
    exposed = native.get("items")
    sequence = []
    if exposed is not None:
        for index, row in enumerate(exposed):
            _require(type(row["order_index"]) is int and row["order_index"] == index, "Invalid exposed traversal position")
            node = nodes[row["self_ref"]]
            _require(row["label"] == node["label"] and row["text"] == node.get("text") and
                     row["provenance"] == node.get("prov", []), "Traversal export disagrees with native item")
            sequence.append(row["self_ref"])
        # Check the exported body traversal, without importing Docling. Groups
        # remain hierarchy nodes; they are not invented reading-order items.
        expected, stack = [], list(reversed(by_id["#/body"]["children_ids"]))
        while stack:
            current = stack.pop()
            if not current.startswith("#/groups/"):
                expected.append(current)
            stack.extend(reversed(by_id[current]["children_ids"]))
        _require(sequence == expected and len(sequence) == len(set(sequence)), "Native body traversal is incomplete or contradictory")
    order = {"kind": "item_sequence" if exposed is not None else "unavailable", "item_ids": sequence,
             "relations": [], "unresolved_policy": "No order within a multi-box item; missing positions unresolved"}
    return items, regions, sorted(numbers), order


def _structure(prediction, source, evidence_id):
    from .structure_v2_contract import validate_structure

    document = prediction["native"]["document"]
    validate_structure(document, json_bytes(source))
    _require(prediction["version"] == document["algorithm"]["version"], "Structure provider version differs")
    items, regions, numbers, relations = [], [], [], []
    for p, page in enumerate(document["pages"]):
        number = page["page_number"]; numbers.append(number)
        for i, region in enumerate(page["regions"]):
            item = _item(region["id"], f"#/pages/{p}/regions/{i}", region["type"])
            box = _box(region["bbox"], source["pages"][number-1]["geometry"])
            native = dict(zip(["l", "t", "r", "b"], box), coord_origin="TOPLEFT")
            regions.append(_region(evidence_id, item, 0, number, native, box, region["source_character_ids"], True))
            item["region_ids"] = [regions[-1]["id"]]; item["geometry_status"] = "present"; items.append(item)
        relations.extend(page["relations"])
    return items, regions, numbers, {"kind": "dag", "item_ids": [], "relations": relations,
        "unresolved_policy": "Frozen Structure0.2 transitive closure; every other distinct pair unresolved"}


def _associate(source, items, regions, numbers):
    associations, overlaps = [], []
    by_item = {item["native_id"]: item for item in items}
    for number in numbers:
        chars = source["pages"][number-1]["characters"]
        by_id = {c["id"]: c for c in chars}
        owners, native, contradictions = defaultdict(list), defaultdict(list), defaultdict(list)
        local = [r for r in regions if r["page_number"] == number]
        for r in local:
            r["geometric_character_ids"] = [c["id"] for c in chars if _inside(r["bbox"], _center(c["bbox"]))]
            for ref in r["geometric_character_ids"]:
                owners[ref].append(r["id"])
            counts = Counter(r["_claims"])
            for ref in r["_claims"]:
                reason = ("provider_has_no_native_source_crosswalk" if not r["_supports_native"] else
                          "unknown_or_foreign_page_character" if ref not in by_id else
                          "duplicate_native_reference" if counts[ref] > 1 else
                          "native_reference_outside_geometry" if ref not in r["geometric_character_ids"] else None)
                r["native_membership"].append({"character_id": ref, "status": "contradictory" if reason else "valid", "reason": reason})
                (contradictions if reason else native)[ref].append(r["id"])
        for r in local:
            ids = r["geometric_character_ids"]
            r["status"] = ("contradictory" if any(c["status"] == "contradictory" for c in r["native_membership"]) else
                "ambiguous" if any(len(owners[ref]) > 1 for ref in ids) else "unambiguous" if ids else
                "zero_character_visual" if by_item[r["native_item_id"]]["label"] in {"picture", "table", "formula"} else "unmatched")
        for i, left in enumerate(local):
            for right in local[i+1:]:
                a, b = left["bbox"], right["bbox"]
                if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                    overlaps.append({"page_number": number, "region_ids": [left["id"], right["id"]],
                                     "meaning": "positive_area_intersection_not_inferred_hierarchy"})
        associations.append({"page_number": number, "characters": [{"character_id": c["id"],
            "geometric_region_ids": owners[c["id"]], "native_region_ids": native[c["id"]],
            "contradictory_region_ids": list(dict.fromkeys(contradictions[c["id"]])),
            "geometric_status": "ambiguous" if len(owners[c["id"]]) > 1 else "unambiguous" if owners[c["id"]] else "unmatched"} for c in chars]})
    for region in regions:
        del region["_claims"], region["_supports_native"]
    return associations, overlaps


def build_hybrid(source_document: dict, layout_predictions: list[LayoutPrediction] | None = None) -> HybridDocument:
    """Build without mutating inputs. Invalid candidates are rejected explicitly.

    Source corruption raises ExtractionError. Missing/failed/rejected candidates
    never alter or remove source pages/characters. Provider provenance binds
    Docling output to a separately verified SHA256; its binary_hash is not one.
    """
    validate_extraction(source_document)
    source = deepcopy(source_document)
    result = {"hybrid_schema_version": HYBRID_VERSION, "coordinate_system": source["coordinate_system"],
        "source": source, "source_canonical_sha256": _digest(source),
        "association_policy": "inclusive_original_character_center_v0", "hypotheses": [], "source_only_pages": []}
    covered, seen = set(), set()
    for supplied in layout_predictions or []:
        prediction = deepcopy(supplied)
        _require(prediction.get("provider") in {"docling", "structure_0_2"}, "Unsupported provider")
        evidence_id = "evidence:"+_digest(prediction)
        _require(evidence_id not in seen, "Duplicate evidence artifact")
        seen.add(evidence_id)
        hypothesis = {"id": evidence_id, "prediction": prediction, "status": "rejected", "issues": [],
                      "page_numbers": [], "items": [], "regions": [], "associations": [], "overlaps": [],
                      "reading_order": {"kind": "unavailable", "item_ids": [], "relations": [], "unresolved_policy": "Candidate unavailable"}}
        try:
            _require(prediction["source_pdf_sha256"] == source["source_sha256"], "Candidate PDF SHA256 differs")
            if prediction["status"] == "failed":
                _require(prediction["native"] is None and prediction["error"], "Failed evidence must provide a reason and no output")
                hypothesis["status"] = "failed"
                hypothesis["issues"] = [{"code": "candidate_failed", "detail": prediction["error"]}]
            else:
                _require(prediction["status"] == "available" and prediction["error"] is None, "Invalid candidate state")
                items, regions, numbers, order = (_docling if prediction["provider"] == "docling" else _structure)(prediction, source, evidence_id)
                associations, overlaps = _associate(source, items, regions, numbers)
                hypothesis.update(status="available", page_numbers=numbers, items=items, regions=regions,
                                  associations=associations, overlaps=overlaps, reading_order=order)
                covered.update(numbers)
        except (ExtractionError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            hypothesis["issues"] = [{"code": "candidate_rejected", "detail": str(exc)}]
        result["hypotheses"].append(hypothesis)
    result["source_only_pages"] = [n for n in range(1, source["page_count"]+1) if n not in covered]
    validate_schema(result, "hybrid-0.1")
    return result


def source_text(document: HybridDocument, page_number: int, character_ids: list[str] | None = None) -> str:
    """Only original Unicode, in backend extraction order (not reading order)."""
    pages = document["source"]["pages"]
    _require(type(page_number) is int and 1 <= page_number <= len(pages), "Unknown source page")
    chars = pages[page_number-1]["characters"]
    if character_ids is not None:
        _require(len(character_ids) == len(set(character_ids)) and set(character_ids) <= {c["id"] for c in chars}, "Duplicate/foreign source character selection")
        selected = set(character_ids); chars = [c for c in chars if c["id"] in selected]
    return "".join(c["text"] for c in chars)


def order_hypothesis(document: HybridDocument, evidence_id: str, before_region: str, after_region: str) -> dict:
    """Query provider evidence; never certify it as authoritative reading order."""
    h = next((h for h in document["hypotheses"] if h["id"] == evidence_id), None)
    _require(h is not None and h["status"] == "available", "Unknown/unavailable evidence")
    regions = {r["id"]: r for r in h["regions"]}
    _require(before_region in regions and after_region in regions, "Unknown hypothesis region")
    left, right = regions[before_region], regions[after_region]
    a, b = left["native_item_id"], right["native_item_id"]
    direction, reason = "unresolved", "Provider has no order for this pair"
    order = h["reading_order"]
    if a == b:
        reason = "Within-item order unproven, including multiple provenance boxes"
    elif order["kind"] == "item_sequence" and a in order["item_ids"] and b in order["item_ids"]:
        direction = "before" if order["item_ids"].index(a) < order["item_ids"].index(b) else "after"
        reason = "Native item traversal hypothesis"
    elif order["kind"] == "dag" and left["page_number"] == right["page_number"]:
        from .structure_order import closure
        native = h["prediction"]["native"]["document"]
        page = next(p for p in native["pages"] if p["page_number"] == left["page_number"])
        _, reach = closure(page["regions"], page["relations"])
        index = {r["id"]: i for i, r in enumerate(page["regions"])}
        if reach[index[a]] & (1 << index[b]):
            direction = "before"
        elif reach[index[b]] & (1 << index[a]):
            direction = "after"
        reason = "Frozen native DAG reachability; omitted pairs unresolved"
    return {"evidence_id": evidence_id, "provider": h["prediction"]["provider"],
            "provider_version": h["prediction"]["version"], "direction": direction, "reason": reason}
