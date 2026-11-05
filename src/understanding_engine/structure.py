"""Deterministic candidate structure; never rewrites or replaces extraction text.

Run separately: python -m understanding_engine.structure extraction.json --output-dir NEW
"""

import argparse
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from statistics import median
import tempfile

from .contracts import ExtractionError, json_bytes, validate_extraction


@dataclass(frozen=True)
class StructureSettings:
    row_overlap: float = 0.5
    line_gap_em: float = 1.2
    gutter_min_support: int = 3
    gutter_min_side_fraction: float = 0.15
    paragraph_gap_em: float = 0.45
    paragraph_indent_em: float = 0.9
    heading_size_ratio: float = 1.15
    heading_bold_fraction: float = 0.7
    heading_max_characters: int = 100

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ExtractionError("invalid_settings", f"{field.name} must be finite and positive")
        for name in ("row_overlap", "gutter_min_side_fraction", "heading_bold_fraction"):
            if getattr(self, name) > 1:
                raise ExtractionError("invalid_settings", f"{name} must be <= 1")
        for name in ("gutter_min_support", "heading_max_characters"):
            if not isinstance(getattr(self, name), int):
                raise ExtractionError("invalid_settings", f"{name} must be an integer")


def _box(items):
    boxes = [item["bbox"] for item in items]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _refs(chars):
    # References retain backend order; geometry order is represented by relations.
    return [c["id"] for c in sorted(chars, key=lambda c: c["backend_index"])]


def _lines(chars, settings):
    rows = []
    unsupported = []
    for char in sorted(chars, key=lambda c: (c["bbox"][1], c["bbox"][0], c["backend_index"])):
        x0, top, x1, bottom = char["bbox"]
        a, b, c, d, _, _ = char["matrix"]
        if (not char["upright"] or abs(b) > 1e-6 or abs(c) > 1e-6 or
                a <= 0 or d <= 0 or bottom <= top or x1 <= x0 or char["size"] <= 0):
            unsupported.append(char)
            continue
        choices = []
        for i, row in enumerate(rows):
            seed = row[0]["bbox"]
            overlap = min(bottom, seed[3]) - max(top, seed[1])
            if overlap >= settings.row_overlap * min(bottom - top, seed[3] - seed[1]):
                choices.append((abs(bottom - seed[3]), i))
        if choices:
            rows[min(choices)[1]].append(char)
        else:
            rows.append([char])
    segments, gaps = [], []
    for row_index, row in enumerate(rows):
        ordered = sorted(row, key=lambda c: (c["bbox"][0], c["backend_index"]))
        size = median(c["size"] for c in row)
        group = []
        right = None
        for char in ordered:
            if right is not None and char["bbox"][0] - right > settings.line_gap_em * size:
                segments.append(group)
                gaps.append((right, char["bbox"][0], row_index))
                group = []
            group.append(char)
            right = max(right if right is not None else char["bbox"][2], char["bbox"][2])
        segments.append(group)
    return sorted(segments, key=lambda cs: (_box(cs)[1], _box(cs)[0], _refs(cs))), gaps, unsupported


def _gutter(segments, gaps, settings):
    if not segments:
        return None, False
    bounds = _box([{"bbox": _box(cs)} for cs in segments])
    width = bounds[2] - bounds[0]
    boxes = [_box(cs) for cs in segments]
    # Projection evidence also handles columns whose baselines are staggered.
    # A spanning heading may cross a gutter; many crossing lines veto it.
    edges = sorted({b[i] for b in boxes for i in (0, 2)})
    for left, right in zip(edges, edges[1:]):
        x = (left + right) / 2
        on_left = sum(b[2] <= x for b in boxes)
        on_right = sum(b[0] >= x for b in boxes)
        crossing = len(boxes) - on_left - on_right
        if (right - left > median(c["size"] for cs in segments for c in cs) * settings.line_gap_em
                and min(on_left, on_right) >= settings.gutter_min_support
                and crossing <= min(on_left, on_right) * .2):
            # Distinct supporting line fragments; shared row evidence below remains independent.
            gaps.extend((left, right, len(segments) + i) for i in range(min(on_left, on_right)))
    candidates = []
    for left, right, _ in gaps:
        x = (left + right) / 2
        if not bounds[0] + width * .2 <= x <= bounds[2] - width * .2:
            continue
        support = len({row for lo, hi, row in gaps if lo <= x <= hi})
        on_left = sum(_box(cs)[2] <= x for cs in segments)
        on_right = sum(_box(cs)[0] >= x for cs in segments)
        if support >= settings.gutter_min_support and min(on_left, on_right) >= len(segments) * settings.gutter_min_side_fraction:
            candidates.append((support, x, right - left))
    if not candidates:
        return None, False
    best = max(item[0] for item in candidates)
    peaks = sorted(item for item in candidates if item[0] == best)
    # Disjoint equally supported gutters are an ambiguity, not an arbitrary choice.
    if max(p[1] for p in peaks) - min(p[1] for p in peaks) > min(p[2] for p in peaks):
        return None, True
    return median(p[1] for p in peaks), False


def reconstruct(extraction_bytes: bytes, *, settings: StructureSettings | None = None,
                page_numbers: list[int] | None = None) -> dict:
    """Read exact v1 JSON bytes, validate them, and return a separate overlay."""
    from .structure_contract import validate_structure

    settings = settings or StructureSettings()
    try:
        extraction = json.loads(extraction_bytes.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ExtractionError("invalid_contract", "Input is not UTF-8 extraction JSON") from exc
    validate_extraction(extraction)
    selected = list(range(1, extraction["page_count"] + 1)) if page_numbers is None else page_numbers
    if (not selected or any(type(n) is not int or n < 1 or n > extraction["page_count"] for n in selected)
            or len(set(selected)) != len(selected)):
        raise ExtractionError("invalid_pages", "Choose distinct existing one-based page numbers")
    source_hash = hashlib.sha256(extraction_bytes).hexdigest()
    implementation = b"".join(Path(__file__).with_name(name).read_bytes() for name in
                             ("structure.py", "structure_contract.py"))
    implementation += Path(__file__).with_name("schemas").joinpath("structure.schema.json").read_bytes()
    algorithm = {"name": "deterministic_geometry", "version": "0.1.0",
                 "implementation_sha256": hashlib.sha256(implementation).hexdigest(),
                 "settings": asdict(settings)}
    identity = hashlib.sha256(json_bytes({"source": source_hash, "algorithm": algorithm})).hexdigest()
    result = {"structure_schema_version": "0.1.0", "coordinate_system": extraction["coordinate_system"],
              "source": {"pdf_sha256": extraction["source_sha256"], "extraction_sha256": source_hash,
                         "extraction_schema_version": extraction["schema_version"], "parser": extraction["parser"]},
              "algorithm": algorithm, "pages": []}
    for number in sorted(selected):
        page = extraction["pages"][number - 1]
        prefix = f"{identity}:p{number}"
        segments, gaps, unsupported = _lines(page["characters"], settings)
        gutter, uncertain_layout = _gutter(segments, gaps, settings)
        bounds = page["geometry"]["bbox"]
        columns = []
        if not uncertain_layout and segments:
            edges = [bounds[0], bounds[2]] if gutter is None else [bounds[0], gutter, bounds[2]]
            for i, (left, right) in enumerate(zip(edges, edges[1:])):
                columns.append({"id": f"{prefix}:column{i}", "bbox": [left, bounds[1], right, bounds[3]]})
        body_size = median(c["size"] for cs in segments for c in cs) if segments else 1
        lines = []
        for i, cs in enumerate(segments):
            box = _box(cs)
            column = next((c["id"] for c in columns if c["bbox"][0] <= box[0] and box[2] <= c["bbox"][2]), None)
            bold = sum("bold" in c["fontname"].lower() for c in cs) / len(cs)
            size = median(c["size"] for c in cs)
            heading = len(cs) <= settings.heading_max_characters and (
                size >= body_size * settings.heading_size_ratio or
                (bold >= settings.heading_bold_fraction and size >= body_size * .95))
            lines.append({"id": f"{prefix}:line{i}", "bbox": box, "source_character_ids": _refs(cs),
                          "column_id": column, "median_font_size": size,
                          "heading_candidate": heading, "rule": "vertical_overlap_and_horizontal_gap"})
        regions = []
        by_char = {c["id"]: c for c in page["characters"]}

        def add_region(group, kind, reason):
            chars = [by_char[ref] for line in group for ref in line["source_character_ids"]]
            regions.append({"id": f"{prefix}:region{len(regions)}", "type": kind,
                            "bbox": _box(chars), "line_ids": [line["id"] for line in group],
                            "source_character_ids": _refs(chars), "column_id": group[0]["column_id"],
                            "rule": reason, "uncertainty": ["geometric_hypothesis", "semantic_role_unclassified"]})

        # Group each column independently. Spanning/unassigned lines stay isolated.
        for column in [c["id"] for c in columns] + [None]:
            group = []
            previous = None
            for line in (line for line in lines if line["column_id"] == column):
                split = (previous is None or column is None or line["heading_candidate"] or
                         previous["heading_candidate"] or
                         line["bbox"][1] - previous["bbox"][3] > body_size * settings.paragraph_gap_em or
                         line["bbox"][1] < previous["bbox"][3] - body_size * .3 or
                         line["bbox"][0] - previous["bbox"][0] > body_size * settings.paragraph_indent_em)
                if split and group:
                    add_region(group, "heading" if group[0]["heading_candidate"] else "paragraph", "font_and_gap_grouping")
                    group = []
                group.append(line)
                previous = line
            if group:
                add_region(group, "heading" if group[0]["heading_candidate"] else "paragraph", "font_and_gap_grouping")
        if unsupported:
            regions.append({"id": f"{prefix}:region{len(regions)}", "type": "unknown", "bbox": _box(unsupported),
                            "source_character_ids": _refs(unsupported), "line_ids": [], "column_id": None,
                            "rule": "unsupported_orientation_or_degenerate_geometry",
                            "uncertainty": ["not_grouped", "reading_order_unknown"]})
        relations, ambiguities = [], []
        for i, left in enumerate(regions):
            for right in regions[i + 1:]:
                same_column = left["column_id"] is not None and left["column_id"] == right["column_id"]
                span_heading = (len(columns) == 2 and any(r["type"] == "heading" and r["column_id"] is None
                                                        for r in (left, right)))
                if (same_column or span_heading) and left["type"] != "unknown" and right["type"] != "unknown":
                    first, second = sorted([left, right], key=lambda r: (r["bbox"][1], r["id"]))
                    if first["bbox"][3] <= second["bbox"][1]:
                        # A spanning heading only licenses its own outgoing edges.
                        if same_column or (first["type"] == "heading" and first["column_id"] is None):
                            relations.append({"before": first["id"], "after": second["id"],
                                              "rule": "same_column_vertical_separation" if same_column else "spanning_heading_above"})
                            continue
                ambiguities.append({"region_ids": sorted([left["id"], right["id"]]),
                                    "reason": "overlap_or_column_transition_unproven"})
        result["pages"].append({"page_number": number, "geometry": page["geometry"], "status": page["status"],
                                "layout": "ambiguous" if uncertain_layout else "two_column" if gutter is not None else "single_column" if lines else "unknown",
                                "columns": columns, "lines": lines, "regions": regions,
                                "relations": relations, "ambiguities": ambiguities,
                                "unassigned_characters": [],
                                "unresolved_content": [{"type": "unknown", "bbox": bounds,
                                    "reason": "v1_has_no_graphics_geometry_or_formula_roles",
                                    "source_image_count": page["image_count"]}]})
    validate_structure(result, extraction_bytes)
    return result


def structure_to_directory(input_file, output_directory, *, settings=None, page_numbers=None):
    """Stage and atomically publish a new directory; never overwrite a destination."""
    destination = Path(output_directory).absolute()
    lock = destination.with_name(f".{destination.name}.lock")
    staging = None
    owns_lock = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ExtractionError("output_busy", "Destination is locked") from exc
        owns_lock = True
        os.close(descriptor)
        if os.path.lexists(destination):
            raise ExtractionError("output_exists", "Choose a new output directory")
        source = Path(input_file).read_bytes()
        result = reconstruct(source, settings=settings, page_numbers=page_numbers)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
        with (staging / "structure.json").open("xb") as stream:
            stream.write(json_bytes(result))
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.lexists(destination):
            raise ExtractionError("output_exists", "Destination appeared during reconstruction")
        os.rename(staging, destination)
        staging = None
        return result
    except OSError as exc:
        raise ExtractionError("structure_io_error", str(exc)) from exc
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        if owns_lock:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                # A complete publication must not become a reported failed run.
                import logging
                logging.getLogger(__name__).warning("structure_lock_cleanup_failed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction_json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pages", nargs="+", type=int, help="One-based pages; default all")
    parser.add_argument("--config", type=Path, help="JSON object overriding geometric settings")
    args = parser.parse_args(argv)
    try:
        settings = StructureSettings(**json.loads(args.config.read_text()) if args.config else {})
        result = structure_to_directory(args.extraction_json, args.output_dir, settings=settings, page_numbers=args.pages)
    except (ExtractionError, OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"structure_error: {exc}\n")
    print(f"Published structure for {len(result['pages'])} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
