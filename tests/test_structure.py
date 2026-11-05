"""Authored, offline layout regressions; these are not real-paper ground truth."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from reportlab.pdfgen import canvas

from understanding_engine.contracts import ExtractionError, json_bytes
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.structure import StructureSettings, reconstruct, structure_to_directory
from understanding_engine.structure_contract import resolve_region, validate_structure


def document(tmp_path, rows):
    path = tmp_path / "authored.pdf"
    pdf = canvas.Canvas(str(path), pagesize=(600, 800), invariant=1)
    for x, top, text, size, font in rows:
        pdf.setFont(font, size)
        pdf.drawString(x, 800 - top, text)
    pdf.save()
    return json_bytes(extract_pdf(path))


def words(rows, x=40):
    return [(x, y, text, 10, "Helvetica") for y, text in rows]


def text(region, source):
    chars = {c["id"]: c for c in json.loads(source)["pages"][0]["characters"]}
    return "".join(chars[r]["text"] for r in region["source_character_ids"])


def test_lines_paragraphs_heading_and_order(tmp_path):
    source = document(tmp_path, [(40, 50, "Section heading", 18, "Helvetica-Bold"),
                                *words([(80, "First paragraph starts"), (92, "and continues."),
                                        (120, "Second paragraph.")])])
    page = reconstruct(source)["pages"][0]
    assert len(page["lines"]) == 4
    assert [r["type"] for r in page["regions"]] == ["heading", "paragraph", "paragraph"]
    assert [len(r["line_ids"]) for r in page["regions"]] == [1, 2, 1]
    first, second, third = [r["id"] for r in page["regions"]]
    edges = {(r["before"], r["after"]) for r in page["relations"]}
    assert {(first, second), (second, third)} <= edges
    assert page["ambiguities"] == []


def test_two_columns_do_not_merge_or_assert_transition(tmp_path):
    rows = [(40, 45, "A spanning heading over both columns", 22, "Helvetica-Bold")]
    rows += words([(80, "Left first line"), (92, "Left second line"), (104, "Left third line")])
    rows += words([(80, "Right first line"), (92, "Right second line"), (104, "Right third line")], 330)
    source = document(tmp_path, rows)
    page = reconstruct(source)["pages"][0]
    assert page["layout"] == "two_column"
    paragraphs = [r for r in page["regions"] if r["type"] == "paragraph"]
    assert len(paragraphs) == 2
    assert all(not ("Left" in text(r, source) and "Right" in text(r, source)) for r in paragraphs)
    assert not any({e["before"], e["after"]} == {r["id"] for r in paragraphs} for e in page["relations"])
    assert any(set(a["region_ids"]) == {r["id"] for r in paragraphs} for a in page["ambiguities"])
    headings = [r for r in page["regions"] if r["type"] == "heading"]
    assert len(headings) == 1
    assert sum(e["before"] == headings[0]["id"] for e in page["relations"]) == 2


def test_equally_supported_three_column_layout_abstains(tmp_path):
    rows = [row for x in (40, 230, 420) for row in words([(80, "same width"), (92, "same width"), (104, "same width")], x)]
    page = reconstruct(document(tmp_path, rows))["pages"][0]
    assert page["layout"] == "ambiguous"
    assert not page["relations"]
    assert page["ambiguities"]
    assert sum(len(r["source_character_ids"]) for r in page["regions"]) == 90


def test_overlap_has_no_invented_order(tmp_path):
    source = document(tmp_path, words([(80, "OVERPRINT"), (80, "OVERPRINT")]))
    result = reconstruct(source)
    refs = result["pages"][0]["regions"][0]["source_character_ids"]
    assert len(refs) == len(set(refs)) == 18
    assert not result["pages"][0]["relations"]


@pytest.mark.parametrize("fixture", ["unicode.pdf", "unicode_units.pdf", "verbatim.pdf", "rotations.pdf", "cropped.pdf", "shifted.pdf", "image.pdf", "empty.pdf", "whitespace.pdf", "multi.pdf"])
def test_original_units_and_page_geometry_round_trip(fixtures, fixture):
    original = extract_pdf(fixtures / fixture)
    before = deepcopy(original)
    source = json_bytes(original)
    result = reconstruct(source)
    validate_structure(result, source)
    assert original == before
    assert result["source"]["extraction_sha256"] == hashlib.sha256(source).hexdigest()
    for page in result["pages"]:
        expected = original["pages"][page["page_number"] - 1]
        assert page["geometry"] == expected["geometry"]
        refs = [ref for r in page["regions"] for ref in r["source_character_ids"]]
        assert sorted(refs) == sorted(c["id"] for c in expected["characters"])
        assert page["unresolved_content"][0]["source_image_count"] == expected["image_count"]
        if page["regions"]:
            region = page["regions"][0]
            resolved = resolve_region(result, source, region["id"])
            assert all(c in expected["characters"] for c in resolved)


def test_rotated_text_remains_explicitly_unknown(fixtures):
    result = reconstruct(json_bytes(extract_pdf(fixtures / "rotations.pdf")))
    assert any(r["type"] == "unknown" for p in result["pages"] for r in p["regions"])


def test_determinism_across_paths_and_hash_seeds(fixtures, tmp_path):
    source = json_bytes(extract_pdf(fixtures / "columns.pdf"))
    outputs = []
    for seed in ("1", "937"):
        path = tmp_path / f"source-{seed}.json"
        path.write_bytes(source)
        dest = tmp_path / f"out-{seed}"
        run = subprocess.run([sys.executable, "-m", "understanding_engine.structure", str(path),
                              "--output-dir", str(dest)], env={**os.environ, "PYTHONHASHSEED": seed},
                             text=True, capture_output=True)
        assert run.returncode == 0, run.stderr
        outputs.append((dest / "structure.json").read_bytes())
        assert path.read_bytes() == source
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("mutation,message", [
    ("hash", "byte hash"), ("metadata", "metadata"), ("box", "box"),
    ("foreign_ref", "character references"), ("duplicate_ref", "non-unique"),
    ("omitted_region", "Lines must belong"), ("cycle", "geometric separation|cycle"),
    ("foreign_line", "line reference"), ("unknown_field", "Additional properties"),
    ("nonfinite", "finite"), ("false_ambiguity", "Ambiguous pair"),
])
def test_corrupt_contracts_are_rejected(tmp_path, mutation, message):
    source = document(tmp_path, words([(80, "First block"), (120, "Second block")]))
    result = reconstruct(source)
    page = result["pages"][0]
    first, second = page["regions"]
    if mutation == "hash":
        result["source"]["extraction_sha256"] = "0" * 64
    elif mutation == "metadata":
        page["geometry"]["rotation"] = 90
    elif mutation == "box":
        first["bbox"][0] += 1
    elif mutation == "foreign_ref":
        first["source_character_ids"][0] = "missing"
    elif mutation == "duplicate_ref":
        first["source_character_ids"].append(first["source_character_ids"][0])
    elif mutation == "omitted_region":
        page["regions"].pop()
    elif mutation == "cycle":
        page["relations"].append({"before": second["id"], "after": first["id"], "rule": "same_column_vertical_separation"})
    elif mutation == "foreign_line":
        first["line_ids"][0] = "missing"
    elif mutation == "unknown_field":
        first["corrected_text"] = "never"
    elif mutation == "nonfinite":
        first["bbox"][0] = float("nan")
    elif mutation == "false_ambiguity":
        page["ambiguities"].append({"region_ids": [first["id"], second["id"]], "reason": "contradiction"})
    with pytest.raises(ExtractionError, match=message):
        validate_structure(result, source)


@pytest.mark.parametrize("settings", [{"line_gap_em": 0}, {"row_overlap": 2}, {"gutter_min_support": 2.5},
                                     {"heading_size_ratio": float("nan")}, {"line_gap_em": True}])
def test_settings_reject_invalid_values(settings):
    with pytest.raises(ExtractionError, match="must"):
        StructureSettings(**settings)


def test_configurable_grouping_and_selected_pages(tmp_path, fixtures):
    source = document(tmp_path, words([(80, "Line one"), (98, "Line two")]))
    assert len(reconstruct(source)["pages"][0]["regions"]) == 2
    assert len(reconstruct(source, settings=StructureSettings(paragraph_gap_em=2))["pages"][0]["regions"]) == 1
    multi = json_bytes(extract_pdf(fixtures / "multi.pdf"))
    assert [p["page_number"] for p in reconstruct(multi, page_numbers=[2])["pages"]] == [2]
    for invalid in ([], [0], [99], [1, 1], [True]):
        with pytest.raises(ExtractionError, match="one-based"):
            reconstruct(multi, page_numbers=invalid)


def test_publication_failure_and_existing_destination(tmp_path, fixtures, monkeypatch):
    source = tmp_path / "extraction.json"
    source.write_bytes(json_bytes(extract_pdf(fixtures / "single.pdf")))
    dest = tmp_path / "new"
    monkeypatch.setattr(os, "rename", lambda *args: (_ for _ in ()).throw(OSError("injected failure")))
    with pytest.raises(ExtractionError, match="injected"):
        structure_to_directory(source, dest)
    assert not dest.exists()
    assert not list(tmp_path.glob(".new*"))
    dest.mkdir()
    (dest / "sentinel").write_text("keep")
    with pytest.raises(ExtractionError, match="new output"):
        structure_to_directory(source, dest)
    assert (dest / "sentinel").read_text() == "keep"


def test_invalid_input_and_missing_file_publish_nothing(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("not JSON")
    for path in (source, tmp_path / "missing.json"):
        with pytest.raises(ExtractionError):
            structure_to_directory(path, tmp_path / "dest")
        assert not (tmp_path / "dest").exists()


def test_staggered_columns_remain_separate(tmp_path):
    rows = words([(80, "Left text"), (100, "Left text"), (120, "Left text")])
    rows += words([(89, "Right text"), (109, "Right text"), (129, "Right text")], 330)
    source = document(tmp_path, rows)
    page = reconstruct(source)["pages"][0]
    assert page["layout"] == "two_column"
    for region in page["regions"]:
        assert not ("Left" in text(region, source) and "Right" in text(region, source))
    assert all(next(r for r in page["regions"] if r["id"] == e["before"])["column_id"] ==
               next(r for r in page["regions"] if r["id"] == e["after"])["column_id"] for e in page["relations"])


def test_settings_cli_and_failure_exit_codes(tmp_path, fixtures):
    source = tmp_path / "source.json"
    source.write_bytes(json_bytes(extract_pdf(fixtures / "single.pdf")))
    config = tmp_path / "config.json"
    config.write_text('{"paragraph_gap_em": 0.8}')
    command = [sys.executable, "-m", "understanding_engine.structure", str(source),
               "--output-dir", str(tmp_path / "result"), "--config", str(config)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    structure = json.loads((tmp_path / "result/structure.json").read_bytes())
    assert structure["algorithm"]["settings"]["paragraph_gap_em"] == .8
    config.write_text('{"unrecognized": 1}')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert "structure_error" in result.stderr
