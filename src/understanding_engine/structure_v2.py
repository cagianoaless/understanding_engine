"""Opt-in structure 0.2.0. The original 02a API and PDF parser stay unchanged."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, fields, replace
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
from statistics import median
import tempfile

from .contracts import ExtractionError, json_bytes, validate_extraction
from .structure import _box, _refs, _lines, _gutter
from .structure_order import compact_order


@dataclass(frozen=True)
class RobustSettings:
    row_overlap: float = .5
    line_gap_em: float = 1.2
    gutter_split_gap_em: float = .5
    gutter_min_support: int = 3
    gutter_min_side_fraction: float = .15
    paragraph_gap_em: float = .45
    paragraph_indent_em: float = .9
    heading_size_ratio: float = 1.12
    heading_style_fraction: float = .8
    heading_rare_style_fraction: float = .35
    heading_isolation_em: float = .3
    heading_max_characters: int = 100

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ExtractionError("invalid_settings", f"{field.name} must be positive and finite")
            if (field.name.endswith("fraction") or field.name == "row_overlap") and value > 1:
                raise ExtractionError("invalid_settings", f"{field.name} must be <= 1")
        for name in ("gutter_min_support", "heading_max_characters"):
            if type(getattr(self, name)) is not int:
                raise ExtractionError("invalid_settings", f"{name} must be an integer")


def _split(chars, threshold, at=None):
    ordered = sorted(chars, key=lambda c: (c["bbox"][0], c["backend_index"]))
    groups, gaps = [], []
    group = [ordered[0]]
    right = ordered[0]["bbox"][2]
    previous = ordered[0]
    for char in ordered[1:]:
        gap = char["bbox"][0] - right
        if gap >= threshold * min(previous["size"], char["size"]) and (at is None or right <= at <= char["bbox"][0]):
            groups.append(group)
            gaps.append((right, char["bbox"][0]))
            group = []
        group.append(char)
        right = max(right, char["bbox"][2])
        previous = char
    return groups + [group], gaps


def reconstruct(extraction_bytes, *, settings=None, page_numbers=None):
    from .structure_v2_contract import validate_structure
    settings = settings or RobustSettings()
    try:
        source = json.loads(extraction_bytes.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ExtractionError("invalid_contract", "Expected UTF-8 extraction JSON") from exc
    validate_extraction(source)
    selected = list(range(1, source["page_count"] + 1)) if page_numbers is None else page_numbers
    if not selected or len(set(selected)) != len(selected) or any(type(n) is not int or n < 1 or n > source["page_count"] for n in selected):
        raise ExtractionError("invalid_pages", "Choose distinct existing one-based pages")
    fingerprint = b"".join(Path(__file__).with_name(name).read_bytes() for name in
                           ("structure.py", "structure_v2.py", "structure_order.py", "structure_v2_contract.py"))
    fingerprint += Path(__file__).with_name("schemas").joinpath("structure-0.2.schema.json").read_bytes()
    algorithm = {"name": "deterministic_geometry", "version": "0.2.0", "settings": asdict(settings),
                 "implementation_sha256": hashlib.sha256(fingerprint).hexdigest(),
                 "python": platform.python_version(), "dependencies": {"jsonschema": importlib.metadata.version("jsonschema")}}
    source_hash = hashlib.sha256(extraction_bytes).hexdigest()
    identity = hashlib.sha256(json_bytes({"source": source_hash, "algorithm": algorithm})).hexdigest()
    result = {"structure_schema_version": "0.2.0", "coordinate_system": source["coordinate_system"],
              "source": {"pdf_sha256": source["source_sha256"], "extraction_sha256": source_hash,
                         "extraction_schema_version": source["schema_version"], "parser": source["parser"]},
              "algorithm": algorithm, "pages": []}
    for number in sorted(selected):
        original = source["pages"][number - 1]
        chars = original["characters"]
        by_id = {c["id"]: c for c in chars}
        prefix = f"{identity}:p{number}"
        coarse, coarse_gaps, unsupported = _lines(chars, settings)
        fine, fine_gaps = [], list(coarse_gaps)
        for row, cs in enumerate(coarse):
            parts, gaps = _split(cs, settings.gutter_split_gap_em)
            fine.extend(parts)
            fine_gaps.extend((a, b, len(chars) + row) for a, b in gaps)
        gutter, uncertain = _gutter(fine, fine_gaps, replace(settings, line_gap_em=settings.gutter_split_gap_em))
        segments = []
        for cs in coarse:
            segments.extend(_split(cs, settings.gutter_split_gap_em, gutter)[0] if gutter is not None else [cs])
        segments.sort(key=lambda cs: (_box(cs)[1], _box(cs)[0], _refs(cs)))
        bounds = original["geometry"]["bbox"]
        columns = []
        if segments and not uncertain:
            edges = [bounds[0], bounds[2]] if gutter is None else [bounds[0], gutter, bounds[2]]
            columns = [{"id": f"{prefix}:column{i}", "bbox": [a, bounds[1], b, bounds[3]]}
                       for i, (a, b) in enumerate(zip(edges, edges[1:]))]
        eligible = [c for cs in segments for c in cs]
        body_size = median(c["size"] for c in eligible) if eligible else 1
        contexts = {}
        for column in [c["id"] for c in columns] + [None]:
            box = next((c["bbox"] for c in columns if c["id"] == column), None)
            local = [c for c in eligible if box is None or box[0] <= c["bbox"][0] and c["bbox"][2] <= box[2]]
            counts = Counter(c["fontname"] for c in local)
            modal = {f for f, count in counts.items() if count == max(counts.values(), default=0)}
            contexts[column] = (median(c["size"] for c in local) if local else body_size, counts, modal, len(local))
        lines = []
        for i, cs in enumerate(segments):
            box = _box(cs)
            column = next((c["id"] for c in columns if c["bbox"][0] <= box[0] and box[2] <= c["bbox"][2]), None)
            local_size, counts, modal_fonts, local_count = contexts[column]
            rare = sum(c["fontname"] not in modal_fonts and counts[c["fontname"]] <= local_count * settings.heading_rare_style_fraction for c in cs) / len(cs)
            peers = [_box(other) for other in segments if other is not cs and
                     min(_box(other)[2], box[2]) > max(_box(other)[0], box[0])]
            above = [box[1] - b[3] for b in peers if b[3] <= box[1]]
            below = [b[1] - box[3] for b in peers if b[1] >= box[3]]
            isolated = any(gap >= local_size * settings.heading_isolation_em for gap in
                           ([min(above)] if above else []) + ([min(below)] if below else []))
            size = median(c["size"] for c in cs)
            heading = len(cs) <= settings.heading_max_characters and (
                size >= local_size * settings.heading_size_ratio or
                (rare >= settings.heading_style_fraction and size >= local_size * .95 and isolated))
            lines.append({"id": f"{prefix}:line{i}", "bbox": box, "source_character_ids": _refs(cs),
                          "column_id": column, "median_font_size": size, "heading_candidate": heading,
                          "rule": "gutter_aware_vertical_overlap"})
        regions = []

        def add(group):
            cs = [by_id[ref] for line in group for ref in line["source_character_ids"]]
            regions.append({"id": f"{prefix}:region{len(regions)}", "type": "heading" if group[0]["heading_candidate"] else "paragraph",
                            "bbox": _box(cs), "source_character_ids": _refs(cs),
                            "line_ids": [line["id"] for line in group], "column_id": group[0]["column_id"],
                            "rule": "font_identity_and_gap_grouping",
                            "uncertainty": ["geometric_hypothesis", "semantic_role_unclassified"]})

        for column in [c["id"] for c in columns] + [None]:
            group_size = contexts[column][0]
            group = []
            previous = None
            for line in (l for l in lines if l["column_id"] == column):
                split = (previous is None or column is None or line["heading_candidate"] or previous["heading_candidate"] or
                         line["bbox"][1] - previous["bbox"][3] > group_size * settings.paragraph_gap_em or
                         line["bbox"][1] < previous["bbox"][3] - group_size * .3 or
                         line["bbox"][0] - previous["bbox"][0] > group_size * settings.paragraph_indent_em)
                if split and group:
                    add(group)
                    group = []
                group.append(line)
                previous = line
            if group:
                add(group)
        if unsupported:
            regions.append({"id": f"{prefix}:region{len(regions)}", "type": "unknown", "bbox": _box(unsupported),
                            "source_character_ids": _refs(unsupported), "line_ids": [], "column_id": None,
                            "rule": "unsupported_orientation_or_degenerate_geometry",
                            "uncertainty": ["not_grouped", "reading_order_unknown"]})
        result["pages"].append({"page_number": number, "geometry": original["geometry"], "status": original["status"],
                                "layout": "ambiguous" if uncertain else "two_column" if gutter is not None else "single_column" if lines else "unknown",
                                "columns": columns, "lines": lines, "regions": regions, **compact_order(regions, columns),
                                "unassigned_characters": [], "unresolved_content": [{"type": "unknown", "bbox": bounds,
                                "reason": "v1_has_no_graphics_geometry_or_formula_roles", "source_image_count": original["image_count"]}]})
    validate_structure(result, extraction_bytes)
    return result


def structure_to_directory(input_file, output_directory, *, settings=None, page_numbers=None):
    destination = Path(output_directory).absolute()
    staging = None
    lock = destination.with_name(f".{destination.name}.lock")
    owns_lock = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ExtractionError("output_busy", "Destination is locked") from exc
        owns_lock = True
        os.close(fd)
        if os.path.lexists(destination):
            raise ExtractionError("output_exists", "Choose a new output directory")
        result = reconstruct(Path(input_file).read_bytes(), settings=settings, page_numbers=page_numbers)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
        with (staging / "structure.json").open("xb") as stream:
            stream.write(json_bytes(result)); stream.flush(); os.fsync(stream.fileno())
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
                import logging
                logging.getLogger(__name__).warning("structure_lock_cleanup_failed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction_json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pages", nargs="+", type=int)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        settings = RobustSettings(**json.loads(args.config.read_text()) if args.config else {})
        result = structure_to_directory(args.extraction_json, args.output_dir, settings=settings, page_numbers=args.pages)
    except (ExtractionError, OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"structure_error: {exc}\n")
    print(f"Published structure 0.2.0 for {len(result['pages'])} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
