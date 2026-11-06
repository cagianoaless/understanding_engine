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


def test_cgroup_v2_finite_boundary_and_observation_requirement():
    gates = module("gates")
    values = {"memory.max": str(4 * gates.GIB), "memory.swap.max": "0", "cpu.max": "400000 100000"}
    assert gates.cgroup_limits(values) == {"memory_bytes": 4 * gates.GIB, "swap_bytes": 0, "cpu_cores": 4}
    observations = {key: True for key in gates.OBSERVATIONS}  # synthetic only
    assert not gates.authorize_install(False, values, observations, 0, 0)
    assert not gates.authorize_install(True, values, {}, 0, 0)
    assert gates.authorize_install(True, values, observations, 2 * gates.GIB, 4 * gates.GIB)
    for key in gates.OBSERVATIONS:
        incomplete = dict(observations, **{key: None})
        assert not gates.authorize_install(True, values, incomplete, 0, 0)


@pytest.mark.parametrize("key,value", [
    ("memory.max", "max"), ("memory.max", "4294967297"), ("memory.max", "0"),
    ("memory.max", "-1"), ("memory.max", "4G"), ("memory.max", "nan"),
    ("memory.swap.max", "max"), ("memory.swap.max", "1"),
    ("cpu.max", "max 100000"), ("cpu.max", "400001 100000"),
    ("cpu.max", "1 0"), ("cpu.max", "0 100000"), ("cpu.max", "1 2 3"),
    ("cpu.max", "nan 100000"), ("memory.max", "４２"),
])
def test_unbounded_or_malformed_cgroups_rejected(key, value):
    gates = module("gates")
    values = {"memory.max": "4294967296", "memory.swap.max": "0", "cpu.max": "400000 100000"}
    values[key] = value
    with pytest.raises(ValueError):
        gates.cgroup_limits(values)
    assert not gates.authorize_install(True, values, {k: True for k in gates.OBSERVATIONS}, 0, 0)


@pytest.mark.parametrize("limit", [2 * 1024 ** 3, 4 * 1024 ** 3])
def test_byte_accounting_includes_existing_images_and_cache(limit):
    gates = module("gates")
    image, wheels, model = limit // 2, limit // 4, limit // 4
    count = gates.add_bytes(gates.add_bytes(image, wheels, limit), model, limit)
    assert count == limit
    with pytest.raises(ValueError, match="budget"):
        gates.add_bytes(count, 1, limit)
    assert count == limit  # refusal before accepting more bytes
    for invalid in (-1, True, 1.5):
        with pytest.raises(ValueError):
            gates.add_bytes(0, invalid, limit)


@pytest.mark.parametrize("elapsed,code,timeout,expected", [
    (119.9, 0, False, "success"), (120, 0, False, "timeout"),
    (120.1, 0, False, "timeout"), (0.1, -9, False, "failed"),
    (0.1, 0, True, "timeout"),
])
def test_failed_or_timed_out_samples_never_leave_denominator(elapsed, code, timeout, expected):
    result = module("gates").page_outcome(elapsed, code, timeout)
    assert result["status"] == expected and result["denominator"] == 1
    assert result["successful_pages"] == int(expected == "success")


@pytest.mark.parametrize("elapsed", [-1, float("nan"), float("inf")])
def test_invalid_timeout_measurements_rejected(elapsed):
    with pytest.raises(ValueError):
        module("gates").page_outcome(elapsed, 0)


def test_fixed_versions_budgets_and_registered_hashes():
    plan = read("plan.json")
    assert plan["docling_version"] == "2.148.0"
    assert plan["heron_revision"] == "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
    assert plan["limits"] == {"new_download_bytes": 2147483648, "installed_cache_bytes": 4294967296,
                              "container_memory_bytes": 4294967296, "swap_bytes": 0,
                              "cpu_quota_cores": 4, "effective_inference_threads": 4, "seconds_per_page": 120}
    prior = json.loads((ROOT / "evaluation/experiments/006/summary.json").read_text())
    assert {d["document_id"]: d["source_sha256"] for d in read("annotations.json")["documents"]} == {
        d["document_id"]: d["source_sha256"] for d in prior["benchmark"]["per_document"]}


def test_blocked_stages_cannot_be_reported_as_measured_comparison():
    summary = read("summary.json")
    assert summary["decision"] == "NO_GO"
    assert summary["stages"] == {"A": "complete", "B": "blocked_prerequisite", "C": "not_run", "D": "not_run"}
    assert summary["annotations"]["human_verified_count"] == 0
    benchmark = summary["benchmark"]
    assert benchmark["planned_page_denominator"] == benchmark["unexecuted_pages"] == 6
    assert benchmark["executed_pages"] == 0
    assert benchmark["aggregate_metrics"] is None and benchmark["macro_metrics"] is None
    assert all(doc[candidate] == {"status": "not_run", "metrics": None}
               for doc in benchmark["per_document"] for candidate in ("structure_0_2", "docling"))
    preflight = read("preflight.json")
    assert all(g["status"] == "not_run" for g in preflight["actual_container_gates"].values())
    assert preflight["image_pulls"] == preflight["docling_installations"] == preflight["weight_downloads"] == 0


def test_review_rebuild_failure_is_not_published(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(HERE))
    helper = module("reproduce_review")

    def fail(paths, destination):
        destination.mkdir()
        (destination / "partial.png").write_bytes(b"incomplete")
        raise RuntimeError("render failed")

    monkeypatch.setattr(helper, "build", fail)
    destination = tmp_path / "review"
    with pytest.raises(RuntimeError, match="render failed"):
        helper.rebuild({}, destination)
    assert not destination.exists()
    assert not list(tmp_path.iterdir())


def test_review_rebuild_rejects_repo_and_existing_directory(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(HERE))
    helper = module("reproduce_review")
    with pytest.raises(ValueError, match="outside"):
        helper.rebuild({}, ROOT / "review-renders")
    with pytest.raises(FileExistsError):
        helper.rebuild({}, tmp_path)
