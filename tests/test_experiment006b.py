"""Offline tests use committed metadata, never PDFs, containers or models."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "evaluation/experiments/006b"


def module(name):
    spec = importlib.util.spec_from_file_location("e006b_" + name, HERE / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def read(name):
    return json.loads((HERE / name).read_text())


def test_frozen_references_and_original_files():
    module("references").verify_freeze(HERE)
    assert module("references").validate_annotations(read("annotations.json"), read("page_geometry.json")) == {
        "pages": 6, "regions": 48, "order_pairs": 24, "paragraph_decisions": 18}
    for filename, digest in read("protected-files.json")["files"].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest, filename


def test_fresh_development_pages_and_pending_human_review():
    selection = read("selection.json")
    assert selection["split"] == "development" and not selection["held_out_used"]
    assert selection["selected"] == {"attention": [6, 9], "bert": [6, 10], "tabpfn_nature_2025": [15, 19]}
    for doc, pages in selection["selected"].items():
        assert not set(pages).intersection(p for group in selection["excluded_pages"][doc].values() for p in group)
    form = read("human-review-form.json")
    assert form["reviewer_name"] is None and form["review_status"] == "pending"
    for page in form["pages"]:
        for key in ("region_decisions", "order_decisions", "paragraph_decisions"):
            assert all(x["decision"] == "pending" for x in page[key])


@pytest.mark.parametrize("defect", ["id", "bbox", "source", "order", "verification"])
def test_bad_annotations_rejected(defect):
    annotations = copy.deepcopy(read("annotations.json"))
    page = annotations["pages"][0]
    if defect == "id":
        page["regions"][1]["id"] = page["regions"][0]["id"]
    elif defect == "bbox":
        page["regions"][0]["bbox"] = [10, 10, 9, 20]
    elif defect == "source":
        page["paragraph_decisions"][0]["source_character_ids"][0] = ["fabricated"]
    elif defect == "order":
        page["order_pairs"][0]["before"] = "nonexistent"
    else:
        page["verification"] = "human_verified"
    with pytest.raises(ValueError):
        module("references").validate_annotations(annotations, read("page_geometry.json"))


@pytest.mark.parametrize("page_id", list(json.loads((HERE / "page_geometry.json").read_text())))
def test_actual_page_coordinate_roundtrip(page_id):
    transform = module("review_pack").transform
    geometry = read("page_geometry.json")[page_id]
    pixels = (893, 1263)  # independent x/y rounding, not assumed exactly 1.5
    native = [39, 45, 285, 183]
    assert transform(transform(native, geometry, pixels), geometry, pixels, inverse=True) == pytest.approx(native)


@pytest.mark.parametrize("change", [{"rotation": 90}, {"raw_rotation": 360}, {"user_unit": 2},
                                    {"cropbox": [10, 10, 500, 700]}, {"bbox": [1, 0, 612, 792]}])
def test_unaudited_transform_fails_explicitly(change):
    geometry = dict(read("page_geometry.json")["attention-p06"], **change)
    with pytest.raises(ValueError, match="Unaudited"):
        module("review_pack").transform([1, 2, 3, 4], geometry, (918, 1188))


def test_freeze_detects_changed_bytes(tmp_path):
    (tmp_path / "annotations.json").write_text("changed")
    (tmp_path / "freeze.json").write_text(json.dumps({"files": {"annotations.json": "0" * 64}}))
    with pytest.raises(ValueError, match="Frozen input changed"):
        module("references").verify_freeze(tmp_path)
