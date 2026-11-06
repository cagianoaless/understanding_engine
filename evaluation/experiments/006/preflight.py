"""Replay Experiment 006's fail-closed gate. Never installs or runs a model."""

import argparse
import json
from pathlib import Path
import sys

BASELINE = "ba82b2c7f71604d5bcc2859b1a05de112723107d"
LIMITS = {"new_download_bytes": 2 * 1024**3, "installed_cache_bytes": 4 * 1024**3,
          "process_tree_rss_bytes": 4 * 1024**3, "cpu_threads": 4, "seconds_per_page": 120}
CHECKS = ("baseline_integrity", "package_and_platform", "dependency_inventory", "model_inventory",
          "license_compatibility", "artifact_download_budget", "installed_cache_budget",
          "process_tree_rss_enforcement", "cpu_thread_enforcement", "page_timeout_enforcement",
          "offline_and_plugin_isolation")


def assess(evidence):
    """Only explicitly evidenced passing checks permit proceeding to the next phase.

    This replays recorded audit decisions, not an independent license clearance or
    hardware verifier. A GO here never invokes acquisition or conversion.
    """
    if not isinstance(evidence, dict):
        raise ValueError("Expected an audit object")
    blocked = {}
    if evidence.get("baseline_commit") != BASELINE:
        blocked["baseline_commit"] = "The requested baseline does not match"
    if evidence.get("limits") != LIMITS:
        blocked["fixed_limits"] = "Resource limits are immutable for this experiment"
    checks = evidence.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    for name in CHECKS:
        check = checks.get(name, {})
        if not isinstance(check, dict):
            check = {}
        if check.get("status") != "pass" or not isinstance(check.get("reason"), str) or not check["reason"].strip():
            blocked[name] = check.get("reason") or "Missing, unknown, or unverified check"
    values = [evidence.get("expected_wheel_bytes"), evidence.get("expected_model_bytes")]
    if any(type(value) is not int or value < 0 for value in values):
        blocked["artifact_download_budget"] = "Artifact sizes are unknown or malformed"
        total = None
    else:
        total = sum(values)
        if total > LIMITS["new_download_bytes"]:
            blocked["artifact_download_budget"] = "Known artifact bytes exceed 2 GiB"
    outcome = "NO_GO" if blocked else "GO"
    documents = [{"document_id": d["document_id"], "source_sha256": d["sha256"], "pages": None,
                  "structure_0_2": {"status": "not_run", "metrics": None},
                  "docling": {"status": "not_run", "metrics": None}}
                 for d in evidence.get("development_documents", [])]
    return {"experiment": "006", "baseline_commit": BASELINE, "decision": outcome,
            "blocking_checks": blocked, "limits": dict(LIMITS), "known_artifact_bytes": total,
            "benchmark": {"status": "not_run", "reason": "preflight_NO_GO" if blocked else "preflight_only_no_execution",
                          "per_document": documents, "aggregate_metrics": None, "macro_metrics": None},
            "grounding": {"status": "not_run", "valid": None, "missing": None,
                          "unassigned": None, "ambiguous": None, "contradictory": None, "unmapped": None},
            "candidate_resources": {"status": "not_run", "wall_seconds_per_page": None,
                                    "peak_process_tree_rss_bytes": None, "effective_cpu_threads": None,
                                    "installed_cache_bytes": None},
            "annotations": {"status": "not_created", "human_verified_count": 0},
            "acquisition_authorized": not blocked,
            "next_step": "Stop; no candidate installation, weight acquisition, annotations or predictions" if blocked
                         else "Preflight only; separate frozen evaluation and verified isolated acquisition required"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).with_name("evidence.json"))
    parser.add_argument("--output", type=Path, help="New result file; never overwrite")
    args = parser.parse_args(argv)
    try:
        result = assess(json.loads(args.evidence.read_text(encoding="utf-8")))
        raw = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            # Compute/validate before creating the file; exclusive creation protects previous audits.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(raw)
        else:
            print(raw, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"preflight_error: {exc}\n")
    return 0 if result["decision"] == "GO" else 3


if __name__ == "__main__":
    raise SystemExit(main())
