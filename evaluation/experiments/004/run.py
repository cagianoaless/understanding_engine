"""Offline three-page development probe. Frozen agent annotations are not truth."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

from understanding_engine.contracts import json_bytes
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.structure import StructureSettings, structure_to_directory
from understanding_engine.structure_contract import validate_structure

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def iou(a, b):
    intersect = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersect
    return intersect / union if union else 0


def in_windows(region, windows):
    x0, y0, x1, y1 = region["bbox"]
    return any(a <= (x0 + x1) / 2 <= c and b <= (y0 + y1) / 2 <= d for a, b, c, d in windows)


def score(page, annotation):
    predicted = [r for r in page["regions"] if in_windows(r, annotation["windows"])]
    expected = annotation["regions"]
    candidates = sorted((-iou(a["bbox"], b["bbox"]), a["id"], b["id"])
                        for a in expected for b in predicted)
    matches, used = {}, set()
    for negative, aid, bid in candidates:
        if -negative >= .5 and aid not in matches and bid not in used:
            matches[aid] = bid
            used.add(bid)
    lookup = {r["id"]: r for r in predicted}
    region_decisions = [{"reference": a, "predicted": lookup.get(matches.get(a["id"])),
                         "iou": iou(a["bbox"], lookup[matches[a["id"]]]["bbox"]) if a["id"] in matches else 0,
                         "type_correct": a["id"] in matches and a["type"] == lookup[matches[a["id"]]]["type"]}
                        for a in expected]
    adjacency = {r["id"]: set() for r in page["regions"]}
    for edge in page["relations"]:
        adjacency[edge["before"]].add(edge["after"])

    def precedes(a, b):
        pending, visited = list(adjacency.get(a, [])), set()
        while pending:
            current = pending.pop()
            if current == b:
                return True
            if current not in visited:
                visited.add(current)
                pending.extend(adjacency[current])
        return False

    order = []
    for pair in annotation["order_pairs"]:
        a, b = matches.get(pair["before"]), matches.get(pair["after"])
        order.append({**pair, "correct": bool(a and b and precedes(a, b)),
                      "inverted": bool(a and b and precedes(b, a)),
                      "reason": "missing_region" if not a or not b else "ordered" if precedes(a, b) else "abstained_or_wrong"})
    line_regions = {lid: r["id"] for r in page["regions"] for lid in r["line_ids"]}

    def align(point):
        x, y = point
        candidates = sorted((abs((line["bbox"][1] + line["bbox"][3]) / 2 - y), line["id"])
                            for line in page["lines"] if line["bbox"][0] - 15 <= x <= line["bbox"][2] + 15)
        if not candidates or candidates[0][0] > 8 or (len(candidates) > 1 and candidates[0][0] == candidates[1][0]):
            return None
        return candidates[0][1]

    boundaries = []
    for reference in annotation["paragraph_pairs"]:
        a, b = [align(point) for point in reference["points"]]
        aligned = a is not None and b is not None and a != b
        actual = line_regions[a] != line_regions[b] if aligned else None
        boundaries.append({**reference, "line_ids": [a, b], "actual_break": actual,
                           "correct": aligned and actual == reference["break"]})
    tp = sum(r["break"] and r["actual_break"] is True for r in boundaries)
    fn = sum(r["break"] and r["actual_break"] is not True for r in boundaries)
    fp = sum(not r["break"] and r["actual_break"] is not False for r in boundaries)
    refs = [ref for r in page["regions"] for ref in r["source_character_ids"]]
    metrics = {"reference_regions": len(expected), "predicted_regions_in_windows": len(predicted),
               "matched_regions": len(matches), "false_positive_regions": len(predicted) - len(matches),
               "missed_regions": len(expected) - len(matches),
               "correct_region_types": sum(r["type_correct"] for r in region_decisions),
               "order_pairs": len(order), "correct_order_pairs": sum(r["correct"] for r in order),
               "inverted_order_pairs": sum(r["inverted"] for r in order),
               "paragraph_decisions": len(boundaries), "correct_paragraph_decisions": sum(r["correct"] for r in boundaries),
               "paragraph_tp": tp, "paragraph_fp": fp, "paragraph_fn": fn,
               "unaligned_paragraph_pairs": sum(r["actual_break"] is None for r in boundaries),
               "character_references": len(refs), "unique_character_references": len(set(refs)),
               "unknown_text_regions": sum(r["type"] == "unknown" for r in page["regions"]),
               "detected_columns": len(page["columns"]), "layout": page["layout"],
               "unsupported_figure_references": len(annotation.get("unsupported_regions", [])),
               "localized_figure_matches": 0}
    return {"metrics": metrics, "region_decisions": region_decisions, "order_decisions": order,
            "paragraph_decisions": boundaries,
            "unmatched_predictions": [r for r in predicted if r["id"] not in used]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="append", required=True, help="document_id=/local/path.pdf")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    annotations_bytes = (ROOT / "annotations.json").read_bytes()
    annotations = json.loads(annotations_bytes)
    freeze = json.loads((ROOT / "freeze.json").read_bytes())
    if digest(annotations_bytes) != freeze["annotations_sha256"]:
        raise ValueError("Frozen annotations changed")
    supplied = [entry.split("=", 1) for entry in args.pdf]
    paths = {key: Path(value) for key, value in supplied}
    if len(paths) != len(supplied) or set(paths) != {d["document_id"] for d in annotations["documents"]}:
        raise ValueError("Supply each of the three documents exactly once")
    for annotation in annotations["documents"]:
        if digest(paths[annotation["document_id"]].read_bytes()) != annotation["source_sha256"]:
            raise ValueError("PDF hash differs from frozen source")
    config = json.loads((ROOT / "config.json").read_bytes())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    artifacts = {}
    for annotation in annotations["documents"]:
        name = annotation["document_id"]
        original = paths[name].read_bytes()
        extraction = extract_pdf(paths[name])  # unchanged production implementation/settings
        source = json_bytes(extraction)
        extraction_path = args.output_dir / f"{name}-extraction.json"
        extraction_path.write_bytes(source)
        structure = structure_to_directory(extraction_path, args.output_dir / name,
                                           settings=StructureSettings(**config), page_numbers=[annotation["page_number"]])
        validate_structure(structure, source)
        page = structure["pages"][0]
        result = score(page, annotation)
        result.update(document_id=name, page_number=annotation["page_number"],
                      verification=annotation["verification"], source_sha256=annotation["source_sha256"],
                      source_characters=len(extraction["pages"][annotation["page_number"] - 1]["characters"]),
                      extraction_unchanged=extraction_path.read_bytes() == source,
                      pdf_unchanged=paths[name].read_bytes() == original)
        results.append(result)
        artifacts[name] = {"extraction_sha256": digest(source),
                           "structure_sha256": digest(json_bytes(structure))}
    numeric = [k for k, v in results[0]["metrics"].items() if isinstance(v, int) and k not in ("detected_columns",)]
    aggregate = {key: sum(r["metrics"][key] for r in results) for key in numeric}
    summary = {"experiment": annotations["experiment"], "verification": "agent_visual_checked",
               "human_verified_count": 0, "annotations_sha256": digest(annotations_bytes),
               "configuration": config, "aggregate": aggregate,
               "documents": [{k: r[k] for k in ["document_id", "page_number", "source_sha256", "metrics", "source_characters", "extraction_unchanged", "pdf_unchanged"]} for r in results],
               "artifact_sha256": artifacts,
               "implementation_sha256": structure["algorithm"]["implementation_sha256"],
               "repository_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "python": platform.python_version(),
               "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
               "scope": "Three frozen development pages; bounded agent-checked windows, not human ground truth or full-document performance"}
    (args.output_dir / "decisions.json").write_bytes(json_bytes({"documents": results}))
    (args.output_dir / "summary.json").write_bytes(json_bytes(summary))
    (args.output_dir / "execution.json").write_bytes(json_bytes({"argv": sys.argv, "platform": platform.platform()}))
    print(json.dumps({"output": str(args.output_dir), "aggregate": aggregate}, indent=2))


if __name__ == "__main__":
    main()
