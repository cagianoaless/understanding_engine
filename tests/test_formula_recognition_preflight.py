"""Offline admission tests; never import the candidate or contact model sources."""

from copy import deepcopy
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def preflight(monkeypatch):
    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root))
    return importlib.import_module("evaluation.experiments.formula_recognition_v0.preflight")


@pytest.fixture
def inventory():
    p = Path(__file__).parents[1] / "evaluation/experiments/formula_recognition_v0/model-inventory.json"
    return json.loads(p.read_text())


def test_host_reserve_blocks_even_when_candidate_projection_fits(preflight, inventory):
    result = preflight.assess(dict(host_available_bytes=19 * preflight.GiB, allocated_bytes=preflight.GiB), inventory)
    assert result["decision"] == "BLOCKED"
    assert result["host_reserve_gate"] == "FAIL"
    assert result["scenarios"]["2_copies"]["fits_arithmetic_projection"]
    assert not result["model_download_authorized_to_start"]


def test_fitting_numbers_do_not_establish_runtime_or_storage_compatibility(preflight, inventory):
    result = preflight.assess(dict(host_available_bytes=21 * preflight.GiB, allocated_bytes=preflight.GiB), inventory)
    assert result["decision"] == "INDETERMINATE"
    assert result["guest_storage_gate"].startswith("UNKNOWN")
    assert not result["inference_authorized_to_start"]
    assert result["historical_provisioning_peak"] == "UNKNOWN"
    assert not result["scenarios"]["1_copies"]["measured_installed_fit"]


def test_all_copies_and_scratch_are_counted(preflight, inventory):
    result = preflight.assess(dict(host_available_bytes=21 * preflight.GiB, allocated_bytes=5382258688), inventory)
    one = result["scenarios"]["1_copies"]
    two = result["scenarios"]["2_copies"]
    assert one["fits_arithmetic_projection"] and not two["fits_arithmetic_projection"]
    assert two["projected_inclusive_bytes"] - one["projected_inclusive_bytes"] == result["projected_repository_payload_bytes"]
    assert one["projected_inclusive_bytes"] == 5382258688 + result["projected_repository_payload_bytes"] + preflight.WORK


def test_measured_guest_capacity_is_not_installed_fit(preflight, inventory):
    snapshot = dict(host_available_bytes=19 * preflight.GiB, allocated_bytes=5382258688,
                    guest_filesystems=[dict(available_bytes=2123157504), dict(available_bytes=2608353280)])
    result = preflight.assess(snapshot, inventory)
    assert result["guest_storage_gate"].startswith("PASS")
    assert result["decision"] == "BLOCKED"
    assert not result["scenarios"]["1_copies"]["measured_installed_fit"]


def test_incomplete_guest_measurement_rejected(preflight, inventory):
    with pytest.raises(ValueError):
        preflight.assess(dict(host_available_bytes=21 * preflight.GiB, allocated_bytes=0,
                              guest_filesystems=[dict(available_bytes=1)]), inventory)


@pytest.mark.parametrize("value", [-1, 0.0, True, None])
def test_invalid_measurements_fail(preflight, inventory, value):
    with pytest.raises(ValueError):
        preflight.assess(dict(host_available_bytes=value, allocated_bytes=0), inventory)


@pytest.mark.parametrize("damage", ["revision", "repo", "url", "hash", "path", "duplicate"])
def test_artifact_identity_failures(preflight, inventory, damage):
    data = deepcopy(inventory)
    if damage == "revision":
        data["revision"] = "main"
    elif damage == "repo":
        data["repo_id"] = "another/model"
    elif damage == "url":
        data["files"][0]["url"] = "https://example.com/artifact"
    elif damage == "hash":
        next(r for r in data["files"] if r["role"] == "weights")["sha256"] = None
    elif damage == "path":
        data["files"][0]["file"] = "../escape"
    else:
        data["files"].append(deepcopy(data["files"][0]))
    with pytest.raises(ValueError):
        preflight.assess(dict(host_available_bytes=21 * preflight.GiB, allocated_bytes=0), data)


def test_assessment_never_mutates_model_metadata(preflight, inventory):
    before = deepcopy(inventory)
    snapshot = dict(host_available_bytes=21 * preflight.GiB, allocated_bytes=0)
    a = preflight.assess(snapshot, inventory)
    assert a == preflight.assess(snapshot, inventory)
    assert inventory == before
    assert "tokenizer.json" in a["missing_artifact_sha256"]


def test_frozen_inputs_and_unexecuted_denominators():
    root = Path(__file__).parents[1] / "evaluation/experiments/formula_recognition_v0"
    import hashlib
    manifest = json.loads((root / "input-manifest.json").read_text())
    for name in ["selection", "references"]:
        assert hashlib.sha256((root / (name + ".json")).read_bytes()).hexdigest() == manifest[name + "_sha256"]
    selection = json.loads((root / "selection.json").read_text())
    refs = json.loads((root / "references.json").read_text())
    results = json.loads((root / "results.json").read_text())
    ids = [r["id"] for r in selection["expressions"]]
    assert len(ids) == len(set(ids)) == 8
    assert refs["independent_human_verifications"] == 0
    assert set(ids) == {r["id"] for r in results["expressions"]}
    assert all(r["status"] == "NOT_EXECUTED" and r["quality"] is None for r in results["expressions"])
    assert results["unexecuted_targets"] == 8 and results["attempted_targets"] == 0
