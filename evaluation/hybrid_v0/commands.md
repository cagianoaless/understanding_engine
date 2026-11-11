# Offline reproduction

Parent: PR17, `efdac22d4567c40eb162910ecdf55ae8a258963a`.
`$REPO` denotes this checkout; `$PYTHON` the existing intact CPython 3.11.13;
`$RAW` a new private directory outside every Git repository. No dependency
installation or launcher repair is part of these commands.

```sh
git switch -c feat/hybrid-interface-v0
export PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.11/site-packages"
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
  /opt/homebrew/bin/uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest
```

Observed final result: **415 passed in 8.52 s**. `--frozen` has no effect together
with `--no-project`; existing packages are reused read-only, with no project
sync/resolution or package download. The original launcher is left untouched.

For the retained-data demonstration, `$STAGE_D_EVIDENCE` is the existing private
PR17 evidence directory. It must contain the hashes/files listed in the committed
PR17 manifest; PDFs and models are not needed. `$NEW_OUTPUT` must not exist and
must be outside Git. Publication stages all files then renames the directory
atomically, guarded by a new exclusive lock; it never overwrites an existing run.

```sh
"$PYTHON" -B evaluation/hybrid_v0/demo.py \
  --evidence-root "$STAGE_D_EVIDENCE" --output "$NEW_OUTPUT"
```

The actual run used the persistent PR17 root and two distinct new temporary
output directories while hardening atomic publication. Both full outputs have
the same SHA256; the current source-aware validator also rechecked the final
output. These are repeated deterministic JSON constructions, **not inference
or benchmark repetitions**. The code reads no annotations and calls no scorer.

Generated files:

- `hybrid.json`: complete versioned source/evidence/associations, 58,496,673 bytes.
- `demonstration.json`: actual source conservation and provenance checks.
- `inspection-excerpt.json`: explicitly partial portable inspection view.

A verified copy of the final files/test logs lives under the new private
`$HYBRID_EVIDENCE` root outside Git. Its actual path is in the local
`evidence-location.local.json`; portable hashes are in `evidence-manifest.json`.
Only the small excerpt and report/check metadata are committed. Storage snapshots
count the retained temporary/full output copies along with earlier experiment
resources; no artifact cleanup, model/container operation or runtime change ran.

No command downloads a model, runs Docling, changes source PDFs/annotations,
recalculates benchmark scores, modifies held-out data, or starts a subsequent
evaluation. Independent human review and any new evaluation require separate
activity/authorization.
