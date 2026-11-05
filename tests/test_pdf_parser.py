import hashlib
import json
from collections import Counter

import pdfplumber
import pytest

from understanding_engine.contracts import ExtractionError, json_bytes, validate_extraction
from understanding_engine.pdf_parser import extract_pdf


def test_fixture_integrity(fixtures):
    manifest = json.loads((fixtures / "manifest.json").read_text())
    assert set(manifest["sha256"]) == {p.name for p in fixtures.glob("*.pdf")}
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((fixtures / name).read_bytes()).hexdigest() == digest


def test_single_page_known_text_and_coordinates(fixtures):
    data = extract_pdf(fixtures / "single.pdf")
    validate_extraction(data)
    assert data["page_count"] == 1
    page = data["pages"][0]
    assert page["derived"]["text"] == "Scientific PDF"
    assert "".join(c["text"] for c in page["characters"]) == "Scientific PDF"
    first = page["characters"][0]
    # PDF draws Helvetica 12 at (40, 160), page height=200; font ascent/descent
    # are 9.516 / -2.484 units. These checks are independent of backend comparison.
    assert first["bbox"] == pytest.approx([40, 30.484, 48.004, 42.484])
    assert first["backend_bbox_bottom_origin"] == pytest.approx([40, 157.516, 48.004, 169.516])
    assert first["matrix"] == [1, 0, 0, 1, 40, 160]
    assert first["id"] == f"{data['source_sha256']}:p1:c0"
    assert [c["backend_index"] for c in page["characters"]] == list(range(14))


def test_multi_page_and_document_offsets(fixtures):
    pages = extract_pdf(fixtures / "multi.pdf")["pages"]
    assert [p["derived"]["text"] for p in pages] == ["First page", "Second page"]
    assert [p["page_number"] for p in pages] == [1, 2]
    assert pages[1]["geometry"]["initial_doctop"] == 200
    for p in pages:
        assert p["characters"][0]["doctop"] == pytest.approx(
            p["geometry"]["initial_doctop"] + p["characters"][0]["bbox"][1])
    ids = [c["id"] for p in pages for c in p["characters"]]
    assert len(set(ids)) == len(ids)


def test_unicode_preserved_in_both_layers(fixtures):
    data = extract_pdf(fixtures / "unicode.pdf")
    page = data["pages"][0]
    expected = "café ﬁ Ω −"
    assert "".join(c["text"] for c in page["characters"]) == expected
    assert page["derived"]["text"] == expected
    assert "ﬁ" in json_bytes(data).decode("utf-8")
    assert data["parser"]["settings"]["unicode_norm"] is None
    assert data["parser"]["settings"]["text_map"]["expand_ligatures"] is False


def test_multicodepoint_units_and_line_references(fixtures):
    page = extract_pdf(fixtures / "unicode_units.pdf")["pages"][0]
    assert page["derived"]["text"] == "cafe\u0301 ﬁ\nNext line"
    assert "e\u0301" in [c["text"] for c in page["characters"]]
    by_id = {c["id"]: c for c in page["characters"]}
    for line, expected in zip(page["derived"]["lines"], ["cafe\u0301ﬁ", "Nextline"], strict=True):
        assert "".join(by_id[r]["text"] for r in line["source_character_ids"]).replace(" ", "") == expected


def test_no_dehyphenation_or_deduplication(fixtures):
    page = extract_pdf(fixtures / "verbatim.pdf")["pages"][0]
    assert "".join(c["text"] for c in page["characters"]) == "inter-pretationEE"
    assert page["derived"]["text"] == "inter-\npretation\nEE"


def test_whitespace_text_is_retained_but_classified_textless(fixtures):
    data = extract_pdf(fixtures / "whitespace.pdf")
    assert data["status"] == "textless"
    assert "".join(c["text"] for c in data["pages"][0]["characters"]) == "   "


@pytest.mark.parametrize("name", ["single", "unicode", "unicode_units", "rotations", "cropped", "shifted"])
def test_authoritative_layer_matches_backend_and_derived_references(fixtures, name):
    data = extract_pdf(fixtures / f"{name}.pdf")
    with pdfplumber.open(fixtures / f"{name}.pdf", unicode_norm=None, laparams=None) as pdf:
        for actual, backend in zip(data["pages"], pdf.pages, strict=True):
            assert len(actual["characters"]) == len(backend.chars)
            by_id = {c["id"]: c for c in actual["characters"]}
            for index, (char, raw) in enumerate(zip(actual["characters"], backend.chars, strict=True)):
                assert char["backend_index"] == index
                assert char["text"] == raw["text"]
                assert char["bbox"] == [raw["x0"], raw["top"], raw["x1"], raw["bottom"]]
            for line in actual["derived"]["lines"]:
                assert line["source_character_ids"]
                assert all(ref in by_id for ref in line["source_character_ids"])
                assert Counter("".join(by_id[r]["text"] for r in line["source_character_ids"]).replace(" ", "")) == Counter(line["text"].replace(" ", ""))


def test_reproducible_and_path_independent(fixtures, tmp_path):
    source = fixtures / "unicode.pdf"
    renamed = tmp_path / "different-name.pdf"
    renamed.write_bytes(source.read_bytes())
    first = json_bytes(extract_pdf(source))
    assert first == json_bytes(extract_pdf(source)) == json_bytes(extract_pdf(renamed))
    assert str(fixtures).encode() not in first
    for key in (b'"started_at_utc"', b'"duration_seconds"', b'"input_path"'):
        assert key not in first


@pytest.mark.parametrize("name,images", [("empty", 0), ("image", 1)])
def test_textless_documents_are_valid(fixtures, name, images):
    data = extract_pdf(fixtures / f"{name}.pdf")
    assert data["status"] == "textless"
    page = data["pages"][0]
    assert page["status"] == "empty_text_layer"
    assert page["characters"] == []
    assert page["derived"] == {"text": "", "lines": []}
    assert page["image_count"] == images
    assert [w["code"] for w in data["warnings"]] == ["empty_text_layer"]


def test_mixed_pages_preserved(fixtures):
    data = extract_pdf(fixtures / "mixed.pdf")
    assert data["status"] == "text"
    assert [p["status"] for p in data["pages"]] == ["text", "empty_text_layer", "empty_text_layer"]
    assert [w["page_number"] for w in data["warnings"]] == [2, 3]


@pytest.mark.parametrize("name,code", [
    ("missing", "missing_input"), ("invalid", "invalid_pdf"),
    ("encrypted", "encrypted_pdf"), ("encrypted_empty_password", "encrypted_pdf"),
    ("bad_rotation", "malformed_geometry"),
])
def test_explicit_input_errors(fixtures, name, code):
    with pytest.raises(ExtractionError) as caught:
        extract_pdf(fixtures / f"{name}.pdf")
    assert caught.value.code == code


def test_rotated_page_geometry_and_character_retention(fixtures):
    pages = extract_pdf(fixtures / "rotations.pdf")["pages"]
    assert [p["geometry"]["rotation"] for p in pages] == [0, 90, 180, 270]
    assert [(p["geometry"]["width"], p["geometry"]["height"]) for p in pages] == [
        (300, 200), (200, 300), (300, 200), (200, 300)]
    for page in pages:
        assert Counter("".join(c["text"] for c in page["characters"])) == Counter("Scientific PDF")
    # No assertion about rotated derived reading order.


def test_cropbox_is_metadata_not_a_filter(fixtures):
    data = extract_pdf(fixtures / "cropped.pdf")
    page = data["pages"][0]
    assert page["geometry"]["raw_cropbox"] == [20, 60, 280, 180]
    assert page["geometry"]["cropbox"] == [20, 20, 280, 140]
    assert page["geometry"]["bbox"] == [0, 0, 300, 200]
    assert page["derived"]["text"] == "Visible\nOutside crop"
    assert "cropbox_not_applied" in [w["code"] for w in data["warnings"]]


def test_nonzero_origin_and_userunit_preserved(fixtures):
    data = extract_pdf(fixtures / "shifted.pdf")
    page = data["pages"][0]
    geometry = page["geometry"]
    assert geometry["raw_mediabox"] == [10, 20, 310, 220]
    assert geometry["bbox"] == [10, -20, 310, 180]
    assert geometry["pdfminer_layout_bbox"] == [0, 0, 300, 200]
    assert geometry["raw_cropbox"] == [30, 80, 290, 200]
    assert geometry["user_unit"] == 2
    assert page["characters"][0]["bbox"] == pytest.approx([50, 10.484, 58.004, 22.484])
    assert "nondefault_user_unit" in [w["code"] for w in data["warnings"]]


def test_multi_column_retention_without_reading_order_claim(fixtures):
    page = extract_pdf(fixtures / "columns.pdf")["pages"][0]
    assert "".join(c["text"] for c in page["characters"]) == "Left oneLeft twoRight oneRight two"
    for phrase in ["Left one", "Left two", "Right one", "Right two"]:
        assert phrase in page["derived"]["text"]


def test_changed_input_is_detected(fixtures, monkeypatch):
    from understanding_engine import pdf_parser
    original = pdf_parser._hash_stream
    count = 0

    def changed_hash(stream):
        nonlocal count
        count += 1
        return original(stream) if count == 1 else "0" * 64
    monkeypatch.setattr(pdf_parser, "_hash_stream", changed_hash)
    with pytest.raises(ExtractionError) as caught:
        extract_pdf(fixtures / "single.pdf")
    assert caught.value.code == "input_changed"


def test_outside_and_degenerate_geometry_warn_without_clipping(fixtures, monkeypatch):
    from understanding_engine import pdf_parser
    original = pdf_parser._page_geometry

    def modify_backend(page):
        geometry = original(page)
        page.chars[0]["x0"] = -10
        page.chars[1]["x1"] = page.chars[1]["x0"]
        return geometry
    monkeypatch.setattr(pdf_parser, "_page_geometry", modify_backend)
    data = extract_pdf(fixtures / "single.pdf")
    assert data["pages"][0]["characters"][0]["bbox"][0] == -10
    second = data["pages"][0]["characters"][1]
    assert second["bbox"][0] == second["bbox"][2]
    assert {w["code"] for w in data["warnings"]} == {
        "character_outside_page", "degenerate_character_bbox"}
