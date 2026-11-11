"""Read-only source selections; no inference, annotation input or text repair."""

from copy import deepcopy
import hashlib

from .contracts import ExtractionError, check_box, json_bytes, validate_schema
from .hybrid import _box, _center, _docling_geometry, _inside, source_text
from .hybrid_contract import validate_hybrid
from .selection_contract import SELECTION_VERSION, SelectionResult, validate_request


def _require(value, message):
    if not value:
        raise ExtractionError("invalid_selection", message)


def _intersects(a, b):
    # Same positive-area rule as Hybrid overlap records. Edge-only contact is
    # not a rectangle intersection; inclusive glyph-center/point rules differ.
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _as_list(values):
    _require(isinstance(values, (list, tuple)), "Expected a list or tuple")
    return list(values)


class SelectionIndex:
    """Validate once, borrow immutable evidence, lazily index requested pages.

    The caller must not mutate the original hybrid for this index's lifetime.
    Results are detached copies. No complete hybrid/source serialization occurs
    during a query; source_text and original association/order data are reused.
    """

    def __init__(self, document, original_source, *, expected_pdf_sha256):
        _require(expected_pdf_sha256 == original_source.get("source_sha256"), "Wrong expected PDF identity")
        validate_hybrid(document, original_source)
        self._document = document
        self._pdf = expected_pdf_sha256
        self._pages = {}
        parser = document["source"]["parser"]
        self._provenance = {"extraction_canonical_sha256": document["source_canonical_sha256"],
            "parser_name": parser["name"], "parser_version": parser["version"],
            "parser_settings_sha256": hashlib.sha256(json_bytes(parser["settings"])).hexdigest()}

    def _page(self, number):
        pages = self._document["source"]["pages"]
        _require(type(number) is int and 1 <= number <= len(pages), "Unknown source page")
        if number not in self._pages:
            page = pages[number-1]
            evidence = []
            for h in self._document["hypotheses"]:
                regions = [r for r in h["regions"] if r["page_number"] == number]
                associations = next((p["characters"] for p in h["associations"] if p["page_number"] == number), [])
                evidence.append({"h": h, "regions": regions, "region_ids": {r["id"]: r for r in regions},
                    "items": {i["native_id"]: i for i in h["items"]},
                    "associations": {a["character_id"]: a for a in associations},
                    "positions": {rid: i for i, rid in enumerate(h["reading_order"]["item_ids"])}})
            self._pages[number] = {"page": page, "characters": {c["id"]: c for c in page["characters"]}, "evidence": evidence}
        return self._pages[number]

    def by_character_ids(self, page_number, character_ids):
        return self.select({"kind": "character_ids", "page_number": page_number, "character_ids": _as_list(character_ids)})

    def by_rectangle(self, page_number, bbox, *, coordinate_system):
        return self.select({"kind": "rectangle", "page_number": page_number, "bbox": _as_list(bbox), "coordinate_system": coordinate_system})

    def at_point(self, page_number, point, *, coordinate_system):
        return self.select({"kind": "point", "page_number": page_number, "point": _as_list(point), "coordinate_system": coordinate_system})

    def by_region(self, page_number, evidence_id, region_id, *, basis="geometric"):
        return self.select({"kind": "region", "page_number": page_number, "evidence_id": evidence_id,
                            "region_id": region_id, "basis": basis})

    def select(self, query) -> SelectionResult:
        validate_request(query)
        number, kind = query["page_number"], query["kind"]
        page = self._page(number)
        geometry, units = page["page"]["geometry"], page["page"]["characters"]
        requested = None
        if kind in {"rectangle", "point"}:
            try:
                _docling_geometry(geometry, {k: geometry[k] for k in ["width", "height"]})
                if kind == "rectangle":
                    _box(query["bbox"], geometry)
                else:
                    x, y = query["point"]
                    check_box([x, y, x, y], "selection point")
                    _require(_inside(geometry["bbox"], [x, y]), "Point outside original page")
            except ExtractionError as exc:
                raise ExtractionError("invalid_selection", str(exc)) from exc
        if kind == "character_ids":
            refs = query["character_ids"]
            _require(len(refs) == len(set(refs)) and set(refs) <= set(page["characters"]), "Duplicate or foreign source IDs")
        elif kind == "rectangle":
            refs = [c["id"] for c in units if _inside(query["bbox"], _center(c["bbox"]))]
        elif kind == "point":
            refs = [c["id"] for c in units if _inside(c["bbox"], query["point"])]
        else:
            evidence = next((e for e in page["evidence"] if e["h"]["id"] == query["evidence_id"]), None)
            _require(evidence is not None and query["region_id"] in evidence["region_ids"], "Unknown evidence/region on this source page")
            region = evidence["region_ids"][query["region_id"]]
            requested = (query["evidence_id"], region["id"])
            refs = (region["geometric_character_ids"] if query["basis"] == "geometric" else
                    [m["character_id"] for m in region["native_membership"] if m["status"] == "valid"])
        selected = set(refs)
        characters = [{k: c[k] for k in ["id", "backend_index", "text", "bbox"]} for c in units if c["id"] in selected]
        hypotheses, linked, ambiguous = [], set(), set()
        overlapping = contradictory = textless = False
        available = False
        for entry in page["evidence"]:
            h, items = entry["h"], entry["items"]
            available |= h["status"] == "available" and number in h["page_numbers"]
            associated = set()
            for ref in selected:
                a = entry["associations"].get(ref)
                if a:
                    associated.update(a["geometric_region_ids"]+a["native_region_ids"]+a["contradictory_region_ids"])
                    if a["geometric_region_ids"] or a["native_region_ids"]:
                        linked.add(ref)
                    if len(a["geometric_region_ids"]) > 1:
                        ambiguous.add(ref)
            candidates = []
            for r in entry["regions"]:
                reasons = []
                if r["id"] in associated:
                    reasons.append("source_association")
                if requested == (h["id"], r["id"]):
                    reasons.append("requested_region")
                if kind == "rectangle" and _intersects(query["bbox"], r["bbox"]):
                    reasons.append("rectangle_intersection")
                if kind == "point" and _inside(r["bbox"], query["point"]):
                    reasons.append("point_containment")
                if not reasons:
                    continue
                item = items[r["native_item_id"]]
                native = [m for m in r["native_membership"] if m["status"] == "contradictory" or m["character_id"] in selected or requested == (h["id"], r["id"])]
                contradictory |= any(m["status"] == "contradictory" for m in native)
                textless |= r["status"] == "zero_character_visual"
                candidates.append({"region_id": r["id"], "native_item_id": r["native_item_id"],
                    "native_provenance_index": r["native_provenance_index"], "native_pointer": item["native_pointer"],
                    "label": item["label"], "bbox": r["bbox"], "native_bbox": r["native_bbox"],
                    "association_status": r["status"], "matching_reasons": reasons,
                    "geometric_character_ids": [ref for ref in r["geometric_character_ids"] if ref in selected],
                    "native_membership": native, "geometric_character_count": len(r["geometric_character_ids"]),
                    "valid_native_character_count": sum(m["status"] == "valid" for m in r["native_membership"]),
                    "textless_visual": r["status"] == "zero_character_visual", "confidence": item["confidence"],
                    "native_item_region_ids": item["region_ids"], "within_item_order": "unresolved"})
            candidate_ids = {r["region_id"] for r in candidates}
            overlapping |= any(set(pair["region_ids"]) <= candidate_ids for pair in h["overlaps"])
            matched_items = {r["native_item_id"] for r in candidates}
            needed = set(matched_items)
            for item_id in matched_items:
                parent = items[item_id]["parent_id"]
                while parent is not None and parent not in needed:
                    needed.add(parent); parent = items[parent]["parent_id"]
            hierarchy = [{"native_item_id": i["native_id"], "label": i["label"], "native_parent_id": i["parent_id"],
                "relevant_child_ids": [c for c in i["children_ids"] if c in needed],
                "total_native_child_count": len(i["children_ids"])} for i in h["items"] if i["native_id"] in needed]
            order = h["reading_order"]
            hypotheses.append({"evidence_id": h["id"], "provider": h["prediction"]["provider"],
                "provider_version": h["prediction"]["version"], "candidate_status": h["status"],
                "page_available": number in h["page_numbers"], "issue_codes": [i["code"] for i in h["issues"]],
                "regions": candidates, "hierarchy": hierarchy,
                "reading_order": {"kind": order["kind"], "subset_only": True,
                    "native_item_positions": [{"native_item_id": rid, "position": entry["positions"][rid]}
                                              for rid in order["item_ids"] if rid in matched_items],
                    "direct_native_relations": [r for r in order["relations"] if r["before"] in matched_items and r["after"] in matched_items],
                    "within_item_order": "unresolved", "unresolved_policy": order["unresolved_policy"]}})
        any_regions = any(h["regions"] for h in hypotheses)
        point_ambiguity = kind == "point" and (len(characters) > 1 or any(len(h["regions"]) > 1 for h in hypotheses))
        result = {"selection_schema_version": SELECTION_VERSION, "pdf_sha256": self._pdf, "page_number": number,
            "coordinate_system": self._document["coordinate_system"], "page_geometry": geometry,
            "source_provenance": self._provenance, "query": query, "characters": characters,
            "source_text": source_text(self._document, number, [c["id"] for c in characters]),
            "text_role": "candidate_units_not_resolved_selection" if kind == "point" else "selected_original_units",
            "text_order": "backend_extraction_order_not_verified_human_reading_order",
            "candidate_order": "evidence_then_native_region_order_not_preference", "math_transcription": "not_performed",
            "status": {"unmatched": not characters and not any_regions, "source_only": not available,
                "ambiguous": bool(ambiguous) or overlapping or point_ambiguity,
                "overlapping_regions": overlapping, "contradictory": contradictory, "textless_visual": textless,
                "unmatched_character_ids": [c["id"] for c in characters if c["id"] not in linked],
                "ambiguous_character_ids": [c["id"] for c in characters if c["id"] in ambiguous]},
            "hypotheses": hypotheses}
        validate_schema(result, "selection-0.1")
        return deepcopy(result)
