"""Experiment 003 only: frozen comparison and explicit failure accounting.

No parser/common-evaluator changes, downloading, corrections, or parameter search.
The existing evaluator is imported from this checkout without copying its logic.
"""

import argparse
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import subprocess
from collections import Counter
from pathlib import Path

import pdfplumber

from understanding_engine.pdf_parser import TEXT_SETTINGS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONFIGURATIONS = [
    {"name": "absolute_3", "x_tolerance": 3},
    {"name": "absolute_2", "x_tolerance": 2},
    {"name": "relative_0.125", "x_tolerance": 3, "x_tolerance_ratio": 0.125},
]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def load_common():
    spec = importlib.util.spec_from_file_location("unchanged_spacing_evaluator", REPO / "evaluation/spacing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def glyph_fingerprints(path, document_sha):
    """Hash the same authoritative character fields without deriving any text."""
    pages = []
    with pdfplumber.open(path, unicode_norm=None, laparams=None, repair=False) as pdf:
        for page in pdf.pages:
            records = []
            for index, char in enumerate(page.chars):
                records.append({
                    "id": f"{document_sha}:p{page.page_number}:c{index}",
                    "backend_index": index, "text": char["text"],
                    "bbox": [char["x0"], char["top"], char["x1"], char["bottom"]],
                    "backend_bbox_bottom_origin": [char["x0"], char["y0"], char["x1"], char["y1"]],
                    "doctop": char["doctop"], "matrix": list(char["matrix"]),
                    "upright": char["upright"], "fontname": char["fontname"], "size": char["size"],
                })
            payload = json.dumps(records, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            pages.append({"page_number": page.page_number, "character_units": len(records),
                          "character_layer_sha256": hashlib.sha256(payload).hexdigest()})
            page.close()
    return pages


def unicode_differences(expected, actual):
    # Only ASCII spaces are excluded, matching the common scorer's comparison.
    # Newlines, ligatures, combining marks and superscripts remain distinct.
    left, right = expected.replace(" ", ""), actual.replace(" ", "")
    differences = []
    for op, a, b, c, d in difflib.SequenceMatcher(a=left, b=right, autojunk=False).get_opcodes():
        if op != "equal":
            differences.append({
                "operation": op, "expected_offsets": [a, b], "actual_offsets": [c, d],
                "expected": left[a:b], "actual": right[c:d],
                "expected_codepoints": [f"U+{ord(char):04X}" for char in left[a:b]],
                "actual_codepoints": [f"U+{ord(char):04X}" for char in right[c:d]],
            })
    return differences


def aggregate(rows, annotations, common, candidate, category=None):
    chosen = [r for r in rows if r["candidate"] == candidate and
              (category is None or annotations[r["sample_id"]]["category"] == category)]
    expected = [common.spacing_counts(r["expected"], r["expected"]) for r in chosen]
    scoreable = [r for r in chosen if r["scoreable"]]
    return {
        "candidate": candidate, "category": category or "all",
        "verification": "agent_visual_checked", "sample_count": len(chosen),
        "exact_match_samples": sum(r["actual"] == r["expected"] for r in chosen),
        "scoreable_samples": len(scoreable), "unscoreable_samples": len(chosen) - len(scoreable),
        "missing_spaces": sum(r["missing_spaces"] for r in scoreable),
        "extra_spaces": sum(r["extra_spaces"] for r in scoreable),
        "space_error_counts_complete": len(scoreable) == len(chosen),
        "space_error_scope": "Measured only on scoreable samples; unknown on unscoreable samples, which remain in all sample/reference denominators.",
        "expected_space_boundaries": sum(r["expected_spaces"] for r in expected),
        "expected_no_space_boundaries": sum(r["expected_no_space_boundaries"] for r in expected),
        "scoreable_expected_space_boundaries": sum(r["expected_spaces"] for r in scoreable),
        "scoreable_expected_no_space_boundaries": sum(r["expected_no_space_boundaries"] for r in scoreable),
        "non_space_unicode_mismatch_samples": sum(bool(r["unicode_differences"]) for r in chosen),
        "unexpected_whitespace_samples": sum(bool(r["unexpected_whitespace"]) for r in chosen),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New external directory")
    args = parser.parse_args()
    source = json.loads((HERE / "source.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    plan = json.loads((HERE / "plan.json").read_text())
    samples = json.loads((HERE / "annotations.json").read_text())
    assert plan["candidates"] == CONFIGURATIONS, "Only the three frozen configurations are permitted"
    assert sha(args.pdf) == source["sha256"], "Unexpected PDF bytes"
    for name, expected_sha in freeze["files"].items():
        assert sha(HERE / name) == expected_sha, f"Frozen file changed: {name}"
    assert len(samples["samples"]) == 30
    assert all(s["verification"] == "agent_visual_checked" and
               s["document_sha256"] == source["sha256"] for s in samples["samples"])
    pre_settings = TEXT_SETTINGS.copy()
    common = load_common()
    helper_sha = sha(REPO / "evaluation/spacing.py")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    before = glyph_fingerprints(args.pdf, source["sha256"])
    raw = common.compare({"tabpfn_nature_2025": args.pdf}, samples, plan)
    # Preserve the unchanged common evaluator's output, including its scoreable-
    # only denominators. Required all-sample accounting is separate and explicit.
    write(args.output_dir / "raw_results.json", raw)
    by_id = {s["id"]: s for s in samples["samples"]}
    rows = []
    for original in raw["samples"]:
        row = {**original, "category": by_id[original["sample_id"]]["category"],
               "page_number": by_id[original["sample_id"]]["page_number"],
               "bbox": by_id[original["sample_id"]]["bbox"],
               "font_sizes": by_id[original["sample_id"]]["font_sizes"],
               "fonts": by_id[original["sample_id"]]["fonts"]}
        row["unicode_differences"] = unicode_differences(row["expected"], row["actual"])
        row["unexpected_whitespace"] = sorted({f"U+{ord(c):04X}" for c in row["actual"] if c.isspace() and c != " "})
        rows.append(row)
    assert len(rows) == 90
    assert len({(r["sample_id"], r["candidate"]) for r in rows}) == 90
    after = glyph_fingerprints(args.pdf, source["sha256"])
    assert before == after, "Authoritative character fields changed"
    assert TEXT_SETTINGS == pre_settings and sha(REPO / "evaluation/spacing.py") == helper_sha
    assert sha(args.pdf) == source["sha256"]
    for name, expected_sha in freeze["files"].items():
        assert sha(HERE / name) == expected_sha
    categories = sorted({s["category"] for s in samples["samples"]})
    overall = [aggregate(rows, by_id, common, c["name"]) for c in CONFIGURATIONS]
    grouped = [aggregate(rows, by_id, common, c["name"], category)
               for category in categories for c in CONFIGURATIONS]
    for overall_row in overall:
        parts = [r for r in grouped if r["candidate"] == overall_row["candidate"]]
        for field in ("sample_count", "exact_match_samples", "unscoreable_samples", "missing_spaces",
                      "extra_spaces", "expected_space_boundaries", "expected_no_space_boundaries"):
            assert sum(r[field] for r in parts) == overall_row[field]
    previous = json.loads((REPO / "evaluation/experiments/002/summary.json").read_text())
    summary = {
        "experiment": plan["experiment"], "source_sha256": source["sha256"],
        "repository_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "python": platform.python_version(),
        "dependencies": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
        "uv_lock_sha256": sha(REPO / "uv.lock"), "evaluation_tool_sha256": helper_sha,
        "experiment_runner_sha256": sha(Path(__file__)), "freeze_sha256": sha(HERE / "freeze.json"),
        "annotations_sha256": sha(HERE / "annotations.json"), "plan_sha256": sha(HERE / "plan.json"),
        "candidate_configurations": [{"name": c["name"], "effective_text_settings": {
            **pre_settings, **{k: v for k, v in c.items() if k != "name"}}} for c in CONFIGURATIONS],
        "human_verified_sample_count": 0, "agent_visual_checked_sample_count": 30,
        "sample_categories": dict(Counter(s["category"] for s in samples["samples"])),
        "sample_pages": sorted({s["page_number"] for s in samples["samples"]}),
        "aggregate": overall, "by_category": grouped,
        "experiment_002_separate_cohorts": [r for r in previous["aggregates"]
            if r["candidate"] in {c["name"] for c in CONFIGURATIONS}],
        "production_default_changed": False, "source_characters_mutated": raw["source_characters_mutated"],
        "authoritative_glyph_fingerprints_equal": before == after,
        "denominator_note": "All annotated reference boundaries are counted, including unscoreable samples. The unmodified common scorer reports boundary denominators only for its scoreable rows; raw and supplementary denominators are intentionally distinct.",
        "unicode_note": "Only ASCII space is removed for mismatch diagnostics. All other Unicode and line breaks remain distinct. Diff opcodes are diagnostics, not corrections or a minimal-edit accuracy metric.",
    }
    write(args.output_dir / "results_by_sample.json", rows)
    write(args.output_dir / "character_fingerprints.json", {"before": before, "after": after})
    write(args.output_dir / "summary.json", summary)
    write(args.output_dir / "artifact_hashes.json", {p.name: sha(p) for p in args.output_dir.iterdir() if p.is_file()})
    print(json.dumps({"status": "completed", "aggregate": overall}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
