"""Recheck frozen selected-wheel identities against native host tags; metadata only.

Uses packaging already pinned in the project's development environment. Never
downloads wheels/weights, builds, installs, imports Docling or runs conversion.
Metadata changes create a new audit; they cannot edit the historical snapshot.
"""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    snapshot = json.loads((ROOT / "dependencies.json").read_bytes())
    tags = set(sys_tags())
    results = []
    for row in snapshot["records"]:
        request = urllib.request.Request(row["metadata_url"], headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError("Metadata response exceeds audit bound")
        data = json.loads(raw)
        name = row["selected_wheel"]["filename"]
        wheel = next((f for f in data["urls"] if f["filename"] == name), None)
        results.append({"name": row["name"], "version": row["version"],
                        "file_present": wheel is not None,
                        "compatible_native_tags": bool(parse_wheel_filename(name)[3] & tags),
                        "artifact_metadata_matches": wheel is not None and wheel["size"] == row["selected_wheel"]["bytes"]
                        and wheel["digests"]["sha256"] == row["selected_wheel"]["sha256"],
                        "metadata_response_sha256": hashlib.sha256(raw).hexdigest(),
                        "historical_metadata_response_matches": hashlib.sha256(raw).hexdigest() == row["metadata_sha256"]})
        (args.output_dir / f"{row['name']}-{row['version']}.json").write_bytes(raw)
    (args.output_dir / "audit.json").write_text(json.dumps({"results": results, "candidate_executed": False}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
