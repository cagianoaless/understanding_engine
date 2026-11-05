"""Accounting checks for the small frozen evaluation, without real PDFs."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("structure_evaluation", Path(__file__).parents[1] / "evaluation/experiments/004/run.py")
EVALUATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATION)


@pytest.mark.parametrize("mode", ["correct", "missing", "duplicate", "abstention", "inverted"])
def test_region_and_order_denominators_include_failures(mode):
    a = {"id": "a", "type": "paragraph", "bbox": [0, 0, 50, 10], "source_character_ids": ["c1"], "line_ids": []}
    b = {"id": "b", "type": "paragraph", "bbox": [0, 20, 50, 30], "source_character_ids": ["c2"], "line_ids": []}
    reference = {"windows": [[-1, -1, 100, 100]], "regions": [a, b],
                 "order_pairs": [{"before": "a", "after": "b"}], "paragraph_pairs": []}
    page = {"regions": [a, b], "relations": [{"before": "a", "after": "b"}],
            "lines": [], "columns": [{"id": "col"}], "layout": "single_column"}
    if mode == "missing":
        page["regions"] = [a]
        page["relations"] = []
    elif mode == "duplicate":
        page["regions"].append({**a, "id": "duplicate"})
    elif mode == "abstention":
        page["relations"] = []
    elif mode == "inverted":
        page["relations"] = [{"before": "b", "after": "a"}]
    result = EVALUATION.score(page, reference)["metrics"]
    assert result["reference_regions"] == 2
    assert result["order_pairs"] == 1
    assert result["correct_order_pairs"] == (1 if mode in {"correct", "duplicate"} else 0)
    assert result["missed_regions"] == (1 if mode == "missing" else 0)
    assert result["false_positive_regions"] == (1 if mode == "duplicate" else 0)
    assert result["inverted_order_pairs"] == (1 if mode == "inverted" else 0)


def test_unaligned_paragraph_decisions_are_incorrect_and_counted():
    page = {"regions": [], "lines": [], "relations": [], "columns": [], "layout": "unknown"}
    annotations = {"regions": [], "windows": [], "order_pairs": [],
                   "paragraph_pairs": [{"points": [[0, 0], [0, 12]], "break": True},
                                       {"points": [[0, 30], [0, 42]], "break": False}]}
    result = EVALUATION.score(page, annotations)["metrics"]
    assert result["paragraph_decisions"] == result["unaligned_paragraph_pairs"] == 2
    assert result["correct_paragraph_decisions"] == result["paragraph_tp"] == 0
    assert result["paragraph_fp"] == result["paragraph_fn"] == 1
