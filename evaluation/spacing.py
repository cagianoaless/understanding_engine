"""Offline research comparison; does not change parser defaults or source glyphs.

Run from the repository root with `python evaluation/spacing.py --help`.
Only explicit development-document mappings are accepted; no downloading occurs.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pdfplumber

from understanding_engine.pdf_parser import TEXT_SETTINGS


def spacing_counts(expected: str, actual: str) -> dict:
    """Score spaces only when every other code point matches exactly.

    An offset counts preceding non-space Unicode code points, not glyph units.
    Leading/trailing/repeated spaces are counted. No Unicode/ligature/line-wrap
    normalization or edit-distance alignment is performed.
    """
    def signature(text):
        characters = []
        spaces = Counter()
        for char in text:
            if char == " ":
                spaces[len(characters)] += 1
            else:
                if char.isspace():
                    raise ValueError("Only single-line samples with ASCII spaces are scoreable")
                characters.append(char)
        return "".join(characters), spaces

    expected_chars, expected_spaces = signature(expected)
    actual_chars, actual_spaces = signature(actual)
    if expected_chars != actual_chars:
        raise ValueError("Non-space code points differ; spacing score would hide another error")
    return {
        "missing_spaces": sum((expected_spaces - actual_spaces).values()),
        "extra_spaces": sum((actual_spaces - expected_spaces).values()),
        "expected_spaces": sum(expected_spaces.values()),
        "non_space_codepoints": len(expected_chars),
        "non_space_boundaries": max(0, len(expected_chars) - 1),
        "expected_no_space_boundaries": max(0, len(expected_chars) - 1) - sum(
            0 < offset < len(expected_chars) for offset in expected_spaces
        ),
    }


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compare(document_paths: dict[str, Path], samples: dict, plan: dict) -> dict:
    """Return per-sample candidates and separate verification-level aggregates."""
    documents = {doc["document_id"]: doc for doc in samples["documents"]}
    if set(document_paths) != set(documents):
        raise ValueError("Supply exactly the development document IDs in the sample file")
    if len(documents) != len(samples["documents"]):
        raise ValueError("Document IDs must be unique")
    identifiers = set()
    for sample in samples["samples"]:
        if sample["document_id"] not in documents:
            raise ValueError("Sample references an unknown development document")
        key = (sample["document_id"], sample["id"])
        if key in identifiers:
            raise ValueError("Sample IDs must be unique within a document")
        identifiers.add(key)
        if sample["page_number"] < 1:
            raise ValueError("Sample page numbers must be one-based")
    if len({candidate["name"] for candidate in plan["candidates"]}) != len(plan["candidates"]):
        raise ValueError("Candidate names must be unique")
    rows = []
    for document_id, path in document_paths.items():
        if digest(path) != documents[document_id]["sha256"]:
            raise ValueError(f"PDF hash differs: {document_id}")
        with pdfplumber.open(path, unicode_norm=None, laparams=None, repair=False) as pdf:
            for sample in samples["samples"]:
                if sample["document_id"] != document_id:
                    continue
                status = sample["verification"]
                if status not in {"agent_visual_checked", "human_verified", "synthetic_designed"}:
                    raise ValueError("Unknown verification level")
                if status == "human_verified" and not sample.get("human_reviewer"):
                    raise ValueError("Human-verified samples require a named human reviewer")
                page = pdf.pages[sample["page_number"] - 1]
                # Select full glyphs without clipping their geometry or using text
                # content to find the expected phrase. Boundaries were annotated
                # before candidate scoring. No fuzzy substring matching occurs.
                region = page.within_bbox(tuple(sample["bbox"]))
                original = json.dumps(region.chars, sort_keys=True, default=str)
                for candidate in plan["candidates"]:
                    settings = {**TEXT_SETTINGS, **{k: v for k, v in candidate.items() if k != "name"}}
                    text = region.get_textmap(**settings).as_string
                    row = {
                        "document_id": document_id, "sample_id": sample["id"],
                        "candidate": candidate["name"], "verification": status,
                        "actual": text, "expected": sample["expected"],
                    }
                    try:
                        row.update(spacing_counts(sample["expected"], text))
                        row["scoreable"] = True
                    except ValueError as exc:
                        row.update({"scoreable": False, "reason": str(exc)})
                    rows.append(row)
                if json.dumps(region.chars, sort_keys=True, default=str) != original:
                    raise RuntimeError("A candidate mutated the backend character layer")
            for page in pdf.pages:
                page.close()
    groups = {}
    for row in rows:
        key = (row["document_id"], row["verification"], row["candidate"])
        group = groups.setdefault(key, {
            "document_id": key[0], "verification": key[1], "candidate": key[2],
            "sample_count": 0, "unscoreable_count": 0, "exact_samples": 0,
            "missing_spaces": 0, "extra_spaces": 0, "expected_spaces": 0,
            "non_space_boundaries": 0, "expected_no_space_boundaries": 0,
        })
        group["sample_count"] += 1
        if not row["scoreable"]:
            group["unscoreable_count"] += 1
        else:
            for key in ("missing_spaces", "extra_spaces", "expected_spaces",
                        "non_space_boundaries", "expected_no_space_boundaries"):
                group[key] += row[key]
            group["exact_samples"] += row["actual"] == row["expected"]
    return {
        "experiment": plan["experiment"], "baseline_commit": plan["baseline_commit"],
        "candidates": plan["candidates"], "metric": plan["metric"],
        "source_characters_mutated": False,
        "human_verified_sample_count": sum(s["verification"] == "human_verified" for s in samples["samples"]),
        "aggregates": list(groups.values()), "samples": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="append", required=True, help="DOCUMENT_ID=/local/path.pdf")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=Path(__file__).with_name("spacing_plan.json"))
    parser.add_argument("--output", type=Path, required=True, help="New results JSON; never overwritten")
    args = parser.parse_args(argv)
    try:
        paths = {}
        for mapping in args.pdf:
            name, value = mapping.split("=", 1)
            if name in paths:
                raise ValueError("Duplicate development-document mapping")
            paths[name] = Path(value)
        result = compare(paths, json.loads(args.samples.read_text()), json.loads(args.plan.read_text()))
        result["sample_file_sha256"] = digest(args.samples)
        result["plan_sha256"] = digest(args.plan)
        result["evaluation_tool_sha256"] = digest(Path(__file__))
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        # Assemble before opening so comparison/serialization failures cannot leave
        # a successful-looking result. The application output writer is unchanged.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        parser.exit(2, f"spacing_evaluation_failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
