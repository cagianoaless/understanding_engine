"""Offline checks for the actual NO-GO gate; no speculative model adapter."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1] / "evaluation/experiments/006"
SPEC = importlib.util.spec_from_file_location("experiment006_preflight", ROOT / "preflight.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def passing_fixture():
    # Synthetic policy fixture; not a claim that this host passed any missing gate.
    data = json.loads((ROOT / "evidence.json").read_bytes())
    data["checks"] = {name: {"status": "pass", "reason": "Synthetic verified fixture"} for name in PREFLIGHT.CHECKS}
    return data


def test_real_evidence_is_no_go_and_metrics_are_not_fabricated():
    evidence = json.loads((ROOT / "evidence.json").read_bytes())
    result = PREFLIGHT.assess(evidence)
    assert result["decision"] == "NO_GO"
    assert not result["acquisition_authorized"]
    assert "process_tree_rss_enforcement" in result["blocking_checks"]
    assert result["benchmark"]["aggregate_metrics"] is None
    assert result["benchmark"]["macro_metrics"] is None
    assert all(d[engine]["status"] == "not_run" and d[engine]["metrics"] is None
               for d in result["benchmark"]["per_document"] for engine in ["docling", "structure_0_2"])
    assert result["grounding"]["valid"] is None
    assert result["candidate_resources"]["peak_process_tree_rss_bytes"] is None
    assert result["annotations"]["human_verified_count"] == 0


@pytest.mark.parametrize("name", PREFLIGHT.CHECKS)
@pytest.mark.parametrize("status", ["unknown", "fail"])
def test_every_failed_or_unknown_gate_prevents_acquisition(name, status):
    data = passing_fixture()
    data["checks"][name]["status"] = status
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"
    assert not PREFLIGHT.assess(data)["acquisition_authorized"]


def test_missing_gate_or_unsupported_status_is_not_a_pass():
    data = passing_fixture()
    del data["checks"]["offline_and_plugin_isolation"]
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"
    data = passing_fixture()
    data["checks"]["process_tree_rss_enforcement"]["status"] = True
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"


@pytest.mark.parametrize("value", [None, -1, True, float("nan"), "100"])
def test_unknown_or_invalid_size_cannot_pass(value):
    data = passing_fixture()
    data["expected_model_bytes"] = value
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"


def test_download_boundary_limits_and_baseline_are_fixed():
    data = passing_fixture()
    data["expected_wheel_bytes"] = PREFLIGHT.LIMITS["new_download_bytes"]
    data["expected_model_bytes"] = 0
    assert PREFLIGHT.assess(data)["decision"] == "GO"
    data["expected_model_bytes"] = 1
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"
    data = passing_fixture()
    data["limits"]["process_tree_rss_bytes"] *= 2
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"
    data = passing_fixture()
    data["baseline_commit"] = "0" * 40
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"


def test_successful_probe_process_with_limit_errors_is_not_enforcement():
    probe = json.loads((ROOT / "rss-limit-probe.json").read_bytes())
    assert probe["exit_code"] == 0  # The collector succeeded, not the OS limit calls.
    result = json.loads(probe["stdout"])
    assert "RLIMIT_RSS_error" in result and "RLIMIT_AS_error" in result
    assert PREFLIGHT.assess(json.loads((ROOT / "evidence.json").read_bytes()))["decision"] == "NO_GO"


def test_cli_preserves_previous_audit_and_does_not_import_neural_packages(tmp_path):
    output = tmp_path / "summary.json"
    result = subprocess.run([sys.executable, str(ROOT / "preflight.py"), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 3
    before = output.read_bytes()
    again = subprocess.run([sys.executable, str(ROOT / "preflight.py"), "--output", str(output)],
                           capture_output=True, text=True)
    assert again.returncode == 2
    assert output.read_bytes() == before
    program = """import builtins,runpy
old = builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in {'docling','torch','transformers'}: raise AssertionError(name)
    return old(name,*args,**kwargs)
builtins.__import__ = guarded
runpy.run_path(%r,run_name='__main__')
""" % str(ROOT / "preflight.py")
    run = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert run.returncode == 3, run.stderr


def test_evidence_and_candidate_identities_are_complete_without_installation():
    dependencies = json.loads((ROOT / "dependencies.json").read_bytes())
    assert dependencies["package_count"] == len(dependencies["records"]) == 103
    assert len({r["name"] for r in dependencies["records"]}) == 103
    assert dependencies["selected_wheel_bytes"] == sum(r["selected_wheel"]["bytes"] for r in dependencies["records"])
    assert all(len(r["selected_wheel"]["sha256"]) == 64 and r["selected_wheel"]["url"].startswith("https://") for r in dependencies["records"])
    lock = {line for line in (ROOT / "requirements.candidate.lock").read_text().splitlines() if line and not line.startswith("#")}
    assert lock == {f"{r['name']}=={r['version']} --hash=sha256:{r['selected_wheel']['sha256']}" for r in dependencies["records"]}
    models = json.loads((ROOT / "model-inventory.json").read_bytes())
    assert len(models["revision"]) == 40
    weights = next(r for r in models["model_files"] if r["role"] == "weights")
    assert not weights["downloaded"] and not weights["content_verified"]


def test_results_cannot_mutate_the_fixed_limits():
    data = passing_fixture()
    result = PREFLIGHT.assess(data)
    result["limits"]["cpu_threads"] = 100
    assert PREFLIGHT.LIMITS["cpu_threads"] == 4
    assert PREFLIGHT.assess(data)["limits"]["cpu_threads"] == 4


def test_malformed_audit_does_not_become_a_pass():
    with pytest.raises(ValueError, match="audit object"):
        PREFLIGHT.assess([])
    data = passing_fixture()
    data["checks"] = []
    assert PREFLIGHT.assess(data)["decision"] == "NO_GO"
