"""Authored development regressions, independent of the frozen real-page scores."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from understanding_engine.contracts import ExtractionError, json_bytes
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.structure import reconstruct as original
from understanding_engine.structure_v2 import reconstruct, RobustSettings, structure_to_directory
from understanding_engine.structure_v2_contract import validate_structure, resolve_region
from understanding_engine.structure_order import compact_order, closure, order_status

SPEC = importlib.util.spec_from_file_location("structure_benchmark", Path(__file__).parents[1] / "evaluation/structure_benchmark.py")
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


def source(tmp_path, rows, height=800):
    path = tmp_path / "synthetic.pdf"
    pdf = canvas.Canvas(str(path), pagesize=(620, height), invariant=1)
    for x, top, text, size, font in rows:
        pdf.setFont(font, size)
        pdf.drawString(x, height - top, text)
    pdf.save()
    return json_bytes(extract_pdf(path))


@pytest.mark.parametrize("n", [50, 100, 300])
@pytest.mark.parametrize("layout", ["single_column", "two_column"])
def test_compact_order_preserves_every_known_and_unknown_pair(n, layout):
    regions, columns = BENCH.synthetic_regions(n, layout)
    legacy, _ = BENCH.legacy_order_function()
    dense = legacy(regions, columns)
    sparse = compact_order(regions, columns)
    _, old = closure(regions, dense["relations"])
    _, new = closure(regions, sparse["relations"])
    assert old == new
    ambiguous = {frozenset(a["region_ids"]) for a in dense["ambiguities"]}
    for a in range(n):
        for b in range(a + 1, n):
            unresolved = not (new[a] & (1 << b) or new[b] & (1 << a))
            assert unresolved == (frozenset([regions[a]["id"], regions[b]["id"]]) in ambiguous)
    assert len(sparse["relations"]) == n - len(columns)
    assert sparse["ambiguities"] == []
    assert len(json_bytes(sparse)) < len(json_bytes(dense))


def test_compact_overlap_and_spanning_heading_semantics():
    regions, columns = BENCH.synthetic_regions(6, "two_column")
    regions[1]["bbox"][1] = regions[0]["bbox"][1] + 2  # overlapping intervals
    regions.insert(0, {"id": "spanning", "type": "heading", "column_id": None, "bbox": [0, 0, 620, 10]})
    regions.append({"id": "unsupported", "type": "unknown", "column_id": None, "bbox": [0, 500, 620, 510]})
    legacy, _ = BENCH.legacy_order_function()
    dense = legacy(regions, columns)
    sparse = compact_order(regions, columns)
    assert closure(regions, dense["relations"])[1] == closure(regions, sparse["relations"])[1]
    page = {"regions": regions, **sparse}
    assert order_status(page, "spanning", regions[1]["id"]) == "before"
    assert order_status(page, regions[1]["id"], regions[2]["id"]) == "unresolved"
    assert order_status(page, "unsupported", "spanning") == "unresolved"


@pytest.mark.parametrize("n", [50, 100, 300])
def test_large_synthetic_page_full_contract(tmp_path, n):
    rows = [(30 + (i // (n // 2)) * 300, 40 + (i % (n // 2)) * 24,
             f"Region number {i}", 10, "Helvetica") for i in range(n)]
    raw = source(tmp_path, rows, height=n * 24 + 80)
    output = reconstruct(raw)
    page = output["pages"][0]
    assert len(page["regions"]) == n
    assert len(page["relations"]) == n - 2
    assert page["layout"] == "two_column"
    assert len({c for r in page["regions"] for c in r["source_character_ids"]}) == len(json.loads(raw)["pages"][0]["characters"])
    validate_structure(output, raw)


@pytest.mark.parametrize("left_size,right_size", [(8, 8), (10, 10), (18, 18), (8, 18), (18, 8)])
def test_narrow_gutters_and_mixed_font_sizes(tmp_path, left_size, right_size):
    left = "Left column words"
    right_x = 30 + stringWidth(left, "Helvetica", left_size) + .7 * min(left_size, right_size)
    rows = [(30, top, left, left_size, "Helvetica") for top in (100, 130, 160, 190)]
    rows += [(right_x, top, "Right column words", right_size, "Helvetica") for top in (100, 130, 160, 190)]
    raw = source(tmp_path, rows)
    page = reconstruct(raw)["pages"][0]
    assert page["layout"] == "two_column"
    assert all(l["column_id"] is not None for l in page["lines"])
    assert len(page["lines"]) == 8
    assert all(r["type"] == "paragraph" for r in page["regions"])


def test_heading_uses_opaque_font_identity_and_isolation(tmp_path):
    rows = [(30, 60, "Section", 10, "Helvetica-Bold")]
    rows += [(30, y, "Ordinary body text with several words", 10, "Helvetica") for y in (85, 97, 109, 140)]
    raw = source(tmp_path, rows)
    data = json.loads(raw)
    for c in data["pages"][0]["characters"]:
        c["fontname"] = {"Helvetica": "opaque-X", "Helvetica-Bold": "opaque-Y"}[c["fontname"]]
    renamed = json_bytes(data)
    baseline = original(renamed)["pages"][0]
    proposed = reconstruct(renamed)["pages"][0]
    assert not any(l["heading_candidate"] for l in baseline["lines"])
    assert proposed["lines"][0]["heading_candidate"]
    assert [l["heading_candidate"] for l in proposed["lines"]] == [l["heading_candidate"] for l in reconstruct(raw)["pages"][0]["lines"]]


def test_spanning_heading_and_run_in_style(tmp_path):
    rows = [(30, 50, "A spanning heading across the whole page", 20, "Helvetica-Bold")]
    rows += [(x, y, "Ordinary paragraph words", 10, "Helvetica") for x in (30, 340) for y in (90, 102, 114)]
    raw = source(tmp_path, rows)
    page = reconstruct(raw)["pages"][0]
    heading = next(r for r in page["regions"] if r["type"] == "heading")
    assert heading["column_id"] is None
    for paragraph in (r for r in page["regions"] if r["type"] == "paragraph"):
        assert order_status(page, heading["id"], paragraph["id"]) == "before"
    rows = [(30, 60, "Label", 10, "Helvetica-Bold"), (60, 60, " ordinary text continues", 10, "Helvetica")]
    rows += [(30, y, "Ordinary body text continues", 10, "Helvetica") for y in (72, 84, 96)]
    page = reconstruct(source(tmp_path, rows))["pages"][0]
    assert not page["lines"][0]["heading_candidate"]


@pytest.mark.parametrize("fixture", ["unicode_units.pdf", "rotations.pdf", "cropped.pdf", "shifted.pdf", "image.pdf", "empty.pdf"])
def test_source_units_and_original_contract_unchanged(fixtures, fixture):
    extraction = extract_pdf(fixtures / fixture)
    before = deepcopy(extraction)
    raw = json_bytes(extraction)
    result = reconstruct(raw)
    assert extraction == before
    for page in result["pages"]:
        original_page = extraction["pages"][page["page_number"] - 1]
        assert page["geometry"] == original_page["geometry"]
        refs = [ref for r in page["regions"] for ref in r["source_character_ids"]]
        assert sorted(refs) == sorted(c["id"] for c in original_page["characters"])
        if page["regions"]:
            resolved = resolve_region(result, raw, page["regions"][0]["id"])
            assert all(c in original_page["characters"] for c in resolved)


@pytest.mark.parametrize("mutation", ["unresolved_semantics", "redundant", "cycle", "contradiction", "source_hash"])
def test_new_contract_rejects_changed_meaning(tmp_path, mutation):
    raw = source(tmp_path, [(30, y, f"Block {y}", 10, "Helvetica") for y in (60, 100, 140)])
    result = reconstruct(raw)
    page = result["pages"][0]
    a, b, c = [r["id"] for r in page["regions"]]
    if mutation == "unresolved_semantics":
        page["ordering"]["otherwise"] = "after"
    elif mutation == "redundant":
        page["relations"].append({"before": a, "after": c, "rule": "same_column_vertical_separation"})
    elif mutation == "cycle":
        page["relations"].append({"before": c, "after": a, "rule": "same_column_vertical_separation"})
    elif mutation == "contradiction":
        page["ambiguities"].append({"region_ids": [a, c], "reason": "unresolved"})
    else:
        result["source"]["extraction_sha256"] = "0" * 64
    with pytest.raises(ExtractionError):
        validate_structure(result, raw)


def test_new_cli_reproducible_and_safe_publication(tmp_path, fixtures, monkeypatch):
    raw = json_bytes(extract_pdf(fixtures / "single.pdf"))
    source_file = tmp_path / "source.json"
    source_file.write_bytes(raw)
    outputs = []
    for seed in ("1", "987"):
        destination = tmp_path / seed
        run = subprocess.run([sys.executable, "-m", "understanding_engine.structure_v2", str(source_file),
                              "--output-dir", str(destination)], capture_output=True, text=True,
                             env={**os.environ, "PYTHONHASHSEED": seed})
        assert run.returncode == 0, run.stderr
        outputs.append((destination / "structure.json").read_bytes())
    assert outputs[0] == outputs[1]
    monkeypatch.setattr(os, "rename", lambda *args: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(ExtractionError):
        structure_to_directory(source_file, tmp_path / "failure")
    assert not (tmp_path / "failure").exists()
    assert not list(tmp_path.glob(".failure*"))
    with pytest.raises(ExtractionError):
        structure_to_directory(source_file, tmp_path / "1")
    assert source_file.read_bytes() == raw


def test_three_columns_remain_ambiguous(tmp_path):
    rows = [(x, y, "same width", 10, "Helvetica") for x in (30, 230, 430) for y in (80, 100, 120)]
    page = reconstruct(source(tmp_path, rows))["pages"][0]
    assert page["layout"] == "ambiguous"
    assert page["relations"] == []
    assert page["ordering"]["otherwise"] == "unresolved_for_every_distinct_region_pair"


@pytest.mark.parametrize("config", [{"gutter_split_gap_em": 0}, {"row_overlap": 2},
    {"heading_style_fraction": float("nan")}, {"heading_size_ratio": True}, {"heading_max_characters": 3.5}])
def test_robust_settings_reject_invalid_values(config):
    with pytest.raises(ExtractionError):
        RobustSettings(**config)
