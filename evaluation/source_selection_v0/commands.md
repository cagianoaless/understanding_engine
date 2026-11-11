# Source Selection v0 reproduction

Parent PR18: `87894c4034cb4f05b29eb6663d1ac2c7cd7d42a7`.
`$REPO` is the checkout, `$RAW` a new private external evidence directory,
`$PYTHON` the existing intact CPython 3.11.13. `$HYBRID_EVIDENCE` and
`$STAGE_D_EVIDENCE` are the already-retained PR18/PR17 directories. Exact expanded
local paths stay in external command/location records, not query responses.

```sh
git switch -c feat/source-selection-v0
export PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.11/site-packages"
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
  /opt/homebrew/bin/uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest

"$PYTHON" -B evaluation/source_selection_v0/demo.py \
  --hybrid-root "$HYBRID_EVIDENCE" --source-root "$STAGE_D_EVIDENCE" \
  --work "$RAW" --output "$RAW/measurements" --repeats 10
```

Observed full suite: **452 passed in 8.81 s**. `--frozen` has no effect with
`--no-project`; existing project dependencies are used read-only. No package
installation, synchronization, resolution or launcher repair occurs.

The demo checks both complete input file sizes/hashes against the published
prior input/evidence manifests. It reads no annotation/scoring files, executes
no model, and performs no runtime/Colima operations. Its synthetic PDF is authored
locally with existing reportlab. It reuses the prior demo's atomic new-directory
publisher and never overwrites an existing measurement directory. Use a fresh
work directory so its newly authored synthetic fixture is also kept separately.

Each of 11 queries is constructed once, then repeated ten times. Query and
serialization wall times are separate; byte equality is checked on every repeat.
One-time full validation is timed separately from per-page cached query work;
input loading/decoding is outside that timer. Timings are nondeterministic run
metadata and are not added to deterministic SelectionResult JSON. No inferred
model accuracy or whole-document scalability statistic is computed.

The external output directory contains all 11 full results plus measurements;
the public example is only the small point result. Source PDFs, source extraction,
hybrid and raw candidate outputs remain in their existing locations. No old run,
model, annotation, held-out file or generated artifact is cleaned or removed.
