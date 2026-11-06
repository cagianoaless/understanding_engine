"""Atomically publish an external rebuild of the frozen v1 review ZIP."""

import argparse
import json
import os
from pathlib import Path
import tempfile

from review_pack import build

ROOT = Path(__file__).resolve().parents[3]


def rebuild(pdf_paths, output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Copyrighted review images must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix=".review-staging-", dir=output.parent) as tmp:
        complete = Path(tmp) / "complete"
        complete.mkdir()
        result = build(pdf_paths, complete / "human-review")
        result["archive"] = str(output / "human-review.zip")
        (complete / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        # The complete bundle and ZIP become visible together. Failed builds
        # remain private in the disposable staging directory and are removed.
        if output.exists():
            raise FileExistsError(output)
        os.rename(complete, output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(rebuild(json.loads(args.pdf_map.read_text()), args.output), indent=2))
