import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from understanding_engine.pdf_parser import TEXT_SETTINGS, extract_pdf

SPEC = importlib.util.spec_from_file_location("spacing_evaluation", Path(__file__).parents[1] / "evaluation/spacing.py")
SPACING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SPACING)


@pytest.mark.parametrize("expected,actual,missing,extra", [
    ("one two", "onetwo", 1, 0),
    ("AVATAR, next.", "A VATAR ,next.", 1, 2),
    ("α+β = γ", "α + β=γ", 2, 2),
    ("e\u0301 ﬁ Ω", "e\u0301ﬁ Ω", 1, 0),
    (" one  two ", "one two", 3, 0),
    ("one two", "onet wo", 1, 1),
])
def test_spacing_metric_counts_both_error_directions(expected, actual, missing, extra):
    result = SPACING.spacing_counts(expected, actual)
    assert result["missing_spaces"] == missing
    assert result["extra_spaces"] == extra


@pytest.mark.parametrize("expected,actual", [("ﬁ", "fi"), ("é", "e\u0301"),
    ("α = β", "a = b"), ("one two", "one\ntwo"), ("one two", "one\ttwo")])
def test_nonspacing_changes_are_not_normalized_or_silently_scored(expected, actual):
    with pytest.raises(ValueError):
        SPACING.spacing_counts(expected, actual)


@pytest.fixture(scope="module")
def comparison():
    root = Path(__file__).parents[1]
    samples = json.loads((root / "tests/fixtures/spacing_samples.json").read_text())
    plan = json.loads((root / "evaluation/spacing_plan.json").read_text())
    return SPACING.compare({"synthetic_spacing": root / "tests/fixtures/spacing.pdf"}, samples, plan)


def test_all_synthetic_samples_and_candidates_are_counted(comparison):
    assert len(comparison["candidates"]) == 9
    assert len(comparison["samples"]) == 54 * 9
    assert comparison["human_verified_sample_count"] == 0
    assert not comparison["source_characters_mutated"]
    assert all(row["scoreable"] for row in comparison["samples"])


@pytest.mark.parametrize("sample", ["attention-gap-2.49", "attention-gap-2.68"])
def test_attention_sized_word_gaps_detect_missing_spaces(comparison, sample):
    rows = {r["candidate"]: r for r in comparison["samples"] if r["sample_id"] == sample}
    assert rows["absolute_3"]["missing_spaces"] == 2
    for candidate in ("absolute_2", "absolute_1.5", "relative_0.125", "relative_0.15", "relative_0.20"):
        assert rows[candidate]["missing_spaces"] == rows[candidate]["extra_spaces"] == 0


def test_lower_absolute_threshold_can_split_large_tracked_words(comparison):
    rows = {r["candidate"]: r for r in comparison["samples"] if r["sample_id"] == "Helvetica-24-tracked"}
    assert rows["absolute_3"]["extra_spaces"] == 0
    assert rows["absolute_2"]["extra_spaces"] > 0
    assert rows["relative_0.125"]["extra_spaces"] == 0


def test_small_fonts_and_tight_headings_expose_threshold_tradeoffs(comparison):
    rows = {(r["sample_id"], r["candidate"]): r for r in comparison["samples"]}
    assert rows["Helvetica-6-plain", "absolute_2"]["missing_spaces"] == 2
    assert rows["tight-heading-24", "absolute_3"]["missing_spaces"] == 0
    assert rows["tight-heading-24", "relative_0.15"]["missing_spaces"] == 2


def test_explicit_spaces_punctuation_and_symbols_retained(comparison):
    for row in comparison["samples"]:
        if row["sample_id"].endswith("-explicit") or row["sample_id"] in {"unicode-math", "ligature-accent"}:
            assert row["actual"].replace(" ", "") == row["expected"].replace(" ", "")
        if row["sample_id"].endswith("-explicit"):
            assert row["missing_spaces"] == row["extra_spaces"] == 0


def test_research_comparison_does_not_change_production_settings(comparison, fixtures):
    assert TEXT_SETTINGS["x_tolerance"] == 3
    assert "x_tolerance_ratio" not in TEXT_SETTINGS
    extraction = extract_pdf(fixtures / "spacing.pdf")
    assert extraction["schema_version"] == "1.0.0"
    assert extraction["parser"]["settings"]["text_map"]["x_tolerance"] == 3


def test_comparison_rejects_mismatched_pdf_hash(fixtures):
    samples = {"documents": [{"document_id": "wrong", "sha256": "0" * 64}], "samples": []}
    with pytest.raises(ValueError, match="hash differs"):
        SPACING.compare({"wrong": fixtures / "single.pdf"}, samples, {"candidates": []})


def test_unscoreable_samples_are_counted_as_failures(fixtures):
    samples = {"documents": [{"document_id": "single", "sha256": SPACING.digest(fixtures / "single.pdf")}],
               "samples": [{"id": "wrong-transcription", "document_id": "single", "page_number": 1,
                            "bbox": [0, 0, 300, 200], "expected": "Different text",
                            "verification": "agent_visual_checked"}]}
    result = SPACING.compare({"single": fixtures / "single.pdf"}, samples,
                             {"experiment": "test", "baseline_commit": "test", "metric": "test",
                              "candidates": [{"name": "baseline", "x_tolerance": 3}]})
    assert result["aggregates"][0]["sample_count"] == 1
    assert result["aggregates"][0]["unscoreable_count"] == 1
    assert not result["samples"][0]["scoreable"]
    assert result["aggregates"][0]["exact_samples"] == 0


def test_human_verification_cannot_be_claimed_without_reviewer(fixtures):
    samples = {"documents": [{"document_id": "single", "sha256": SPACING.digest(fixtures / "single.pdf")}],
               "samples": [{"id": "not-reviewed", "document_id": "single", "page_number": 1,
                            "bbox": [0, 0, 300, 200], "expected": "Scientific PDF",
                            "verification": "human_verified"}]}
    with pytest.raises(ValueError, match="named human reviewer"):
        SPACING.compare({"single": fixtures / "single.pdf"}, samples, {"candidates": []})


def _assert_development_documents_registered(samples, manifest):
    # Check uniqueness before building dictionaries, which would hide conflicts.
    for documents, label in ((samples["documents"], "annotation"),
                             (manifest["documents"], "registered")):
        ids = [document["document_id"] for document in documents]
        assert len(ids) == len(set(ids)), f"Duplicate {label} document ID"
    declared = {document["document_id"]: document["sha256"] for document in samples["documents"]}
    registered = {document["document_id"]: document["sha256"] for document in manifest["documents"]}
    for sample in samples["samples"]:
        assert sample["document_id"] in declared, "Sample references an undeclared document"
    for document_id, expected_sha in declared.items():
        assert document_id in registered, f"Missing document registration: {document_id}"
        assert registered[document_id] == expected_sha, f"Document hash mismatch: {document_id}"


def test_annotations_have_explicit_development_provenance():
    root = Path(__file__).parents[1]
    samples = json.loads((root / "evaluation/development/spacing_samples.json").read_text())
    manifest = json.loads((root / "evaluation/development/manifest.json").read_text())
    assert len(samples["samples"]) == 25
    _assert_development_documents_registered(samples, manifest)
    for sample in samples["samples"]:
        assert sample["verification"] in {"agent_visual_checked", "human_verified"}
        if sample["verification"] == "human_verified":
            assert sample.get("human_reviewer")


@pytest.fixture
def provenance_catalogs():
    documents = [{"document_id": "attention", "sha256": "a" * 64},
                 {"document_id": "bert", "sha256": "b" * 64}]
    return ({"documents": deepcopy(documents), "samples": [
        {"document_id": "attention"}, {"document_id": "bert"}]},
        {"documents": deepcopy(documents)})


@pytest.mark.parametrize("extra_count", [0, 1, 3])
def test_experiment_provenance_allows_additional_registered_documents(provenance_catalogs, extra_count):
    samples, manifest = provenance_catalogs
    manifest["documents"].extend({"document_id": f"future-{i}", "sha256": "c" * 64}
                                for i in range(extra_count))
    _assert_development_documents_registered(samples, manifest)


@pytest.mark.parametrize("problem,message", [
    ("missing_registration", "Missing document registration"),
    ("duplicate_registered_id", "Duplicate registered document ID"),
    ("conflicting_registered_id", "Duplicate registered document ID"),
    ("duplicate_unreferenced_id", "Duplicate registered document ID"),
    ("changed_hash", "Document hash mismatch"),
    ("duplicate_annotation_id", "Duplicate annotation document ID"),
    ("conflicting_annotation_id", "Duplicate annotation document ID"),
    ("undeclared_sample_document", "Sample references an undeclared document"),
])
def test_experiment_provenance_rejects_missing_or_conflicting_sources(provenance_catalogs, problem, message):
    samples, manifest = provenance_catalogs
    if problem == "missing_registration":
        manifest["documents"].pop()
    elif problem in {"duplicate_registered_id", "conflicting_registered_id"}:
        duplicate = deepcopy(manifest["documents"][0])
        if problem == "conflicting_registered_id":
            duplicate["sha256"] = "d" * 64
        manifest["documents"].append(duplicate)
    elif problem == "duplicate_unreferenced_id":
        manifest["documents"].extend([{"document_id": "future", "sha256": "c" * 64}] * 2)
    elif problem == "changed_hash":
        manifest["documents"][0]["sha256"] = "d" * 64
    elif problem in {"duplicate_annotation_id", "conflicting_annotation_id"}:
        duplicate = deepcopy(samples["documents"][0])
        if problem == "conflicting_annotation_id":
            duplicate["sha256"] = "d" * 64
        samples["documents"].append(duplicate)
    else:
        manifest["documents"].append({"document_id": "future", "sha256": "c" * 64})
        samples["samples"].append({"document_id": "future"})
    with pytest.raises(AssertionError, match=message):
        _assert_development_documents_registered(samples, manifest)
