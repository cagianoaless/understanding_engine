"""Representation-only benchmark; no PDFs, models, network, or dependencies."""

import argparse
import hashlib
import inspect
import json
import platform
import resource
import statistics
import sys
import textwrap
import time

from understanding_engine.contracts import json_bytes
from understanding_engine import structure as legacy
from understanding_engine.structure_order import compact_order


def legacy_order_function():
    # Execute the actual unmodified 02a block, not an independently rewritten approximation.
    source = inspect.getsource(legacy.reconstruct)
    start = source.index("        relations, ambiguities = [], []")
    stop = source.index('        result["pages"].append', start)
    block = textwrap.dedent(source[start:stop])
    namespace = {}
    exec("def generate(regions, columns):\n" + textwrap.indent(block, "    ") +
         "    return {'relations': relations, 'ambiguities': ambiguities}\n", namespace)
    return namespace["generate"], hashlib.sha256(block.encode()).hexdigest()


def synthetic_regions(n, layout):
    columns = [{"id": "column0"}] + ([{"id": "column1"}] if layout == "two_column" else [])
    per_column = n // len(columns)
    regions = []
    for i in range(n):
        col = min(i // per_column, len(columns) - 1)
        row = i % per_column
        x = 30 + col * 300
        regions.append({"id": "0" * 64 + f":p1:region{i}", "type": "paragraph", "column_id": columns[col]["id"],
                        "bbox": [x, row * 24 + 20, x + 200, row * 24 + 30]})
    return regions, columns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", type=int, required=True)
    parser.add_argument("--layout", choices=["single_column", "two_column"], required=True)
    parser.add_argument("--representation", choices=["original", "compact"], required=True)
    args = parser.parse_args()
    regions, columns = synthetic_regions(args.regions, args.layout)
    original, block_hash = legacy_order_function()
    generate = original if args.representation == "original" else compact_order
    timings = []
    for _ in range(3):
        started = time.perf_counter()
        payload = generate(regions, columns)
        serialized = json_bytes(payload)
        timings.append(time.perf_counter() - started)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({"region_count": args.regions, "layout": args.layout,
                      "representation": args.representation, "seconds_median": statistics.median(timings),
                      "seconds_runs": timings, "output_bytes": len(serialized),
                      "accepted_edges": len(payload["relations"]), "explicit_ambiguities": len(payload["ambiguities"]),
                      "peak_process_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
                      "original_order_block_sha256": block_hash, "python": platform.python_version(),
                      "platform": platform.platform(), "repeats": 3,
                      "scope": "order construction and canonical serialization only; fresh subprocess per row; peak RSS includes imports and all three repetitions, not incremental allocations"}))


if __name__ == "__main__":
    main()
