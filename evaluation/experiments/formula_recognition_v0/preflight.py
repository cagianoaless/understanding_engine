"""Read-only resource assessment. No acquisition, neural imports or inference.

Consumes separately captured resource/model metadata, never references.json.
Projections do not establish an installed fit or model execution compatibility.
"""

import argparse
import json
from pathlib import Path
import re

GiB = 1024**3
RESERVE = 20 * GiB
CAP = 6 * GiB
WORK = 128 * 1024**2
REPOSITORY = "docling-project/CodeFormulaV2"


def byte_count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected a nonnegative integer byte count")
    return value


def assess(snapshot, inventory):
    """Fail closed; one-copy planning does not authorize that untested strategy."""
    available = byte_count(snapshot["host_available_bytes"])
    allocated = byte_count(snapshot["allocated_bytes"])
    if inventory["repo_id"] != REPOSITORY or not re.fullmatch(
        r"[0-9a-f]{40}", inventory["revision"]
    ):
        raise ValueError("Unpinned or different formula model")
    files = inventory["files"]
    names = [r["file"] for r in files]
    if len(names) != len(set(names)) or "model.safetensors" not in names:
        raise ValueError("Incomplete/duplicate model file identity")
    for row in files:
        name = row["file"]
        if Path(name).name != name or name in {".", ".."} or "\\" in name:
            raise ValueError("Unsafe model filename")
        expected = f"https://huggingface.co/{REPOSITORY}/resolve/{inventory['revision']}/{name}"
        if row["url"] != expected:
            raise ValueError("Unexpected model artifact source")
        byte_count(row["bytes"])
        digest = row["sha256"]
        if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Malformed SHA256")
        if row["role"] == "weights" and digest is None:
            raise ValueError("Missing model-weight hash")
    # Whole-repository allowance is conservative; no alternative model files.
    model_bytes = sum(row["bytes"] for row in files)
    scenarios = {}
    for copies in [1, 2]:
        projected = allocated + copies * model_bytes + WORK
        scenarios[str(copies) + "_copies"] = {
            "model_file_copies": copies,
            "projected_inclusive_bytes": projected,
            "excess_over_cap_bytes": max(0, projected - CAP),
            "fits_arithmetic_projection": projected <= CAP,
            "measured_installed_fit": False,
        }
    guest = snapshot.get("guest_filesystems")
    if guest is not None:
        if len(guest) != 2:
            raise ValueError("Expected both measured guest filesystems")
        for row in guest:
            byte_count(row["available_bytes"])
    return {
        "schema_version": "formula-resource-decision.1",
        "decision": "BLOCKED" if available < RESERVE else "INDETERMINATE",
        "model_quality_decision": "INDETERMINATE; no inference executed",
        "host_available_bytes": available,
        "host_reserve_bytes": RESERVE,
        "host_deficit_bytes": max(0, RESERVE - available),
        "inclusive_allocated_bytes": allocated,
        "inclusive_cap_bytes": CAP,
        "current_allocation_gate": "PASS" if allocated <= CAP else "FAIL",
        "remaining_current_cap_bytes": CAP - allocated,
        "projected_repository_payload_bytes": model_bytes,
        "work_allowance_bytes": WORK,
        "scenarios": scenarios,
        "host_reserve_gate": "PASS" if available >= RESERVE else "FAIL",
        "runtime_files_currently_verified": "Selected source files verified separately; full runtime/package tree not rehashed",
        "guest_storage_gate": (
            "PASS; current free capacity only, not observed model installation"
            if guest is not None and min(r["available_bytes"] for r in guest) >= model_bytes + WORK
            else "UNKNOWN; sufficient current guest capacity not established"
        ),
        "guest_filesystems": guest,
        "current_cgroup_gate": "UNKNOWN; historical controls not reinterpreted as current measurement",
        "current_cpu_import_compatibility": "UNKNOWN; no neural import",
        "single_copy_storage_strategy": "UNKNOWN; not implemented or measured",
        "missing_artifact_sha256": [r["file"] for r in files if r["sha256"] is None],
        "model_download_authorized_to_start": False,
        "inference_authorized_to_start": False,
        "historical_provisioning_peak": "UNKNOWN",
        "storage_caveats": [
            "File byte sizes are not measured installed allocation or transient peaks.",
            "One copy excludes any extra host/guest staging, cache or duplicate weight file.",
            "128 MiB is a planning allowance, not a measured upper bound.",
            "Device/inode accounting cannot determine APFS exclusive physical allocation.",
            "This script does not operate the VM or acquire artifacts, even if arithmetic fits.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(json.loads(args.snapshot.read_text()), json.loads(args.inventory.read_text()))
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
