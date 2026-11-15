# Reproduction (no installation)

Use the unchanged existing CPython 3.11.13 and PR #24 runtime. `$RAW` is a new isolated external directory; `$HERE` is this run's directory. Paths below are placeholders, never credentials. Existing raw evidence includes commands.jsonl and the private configuration mapping. Do not blindly rerun inference: the observed run has already exhausted its permitted first-failure path.

Executed sequential diagnostic commands:

```sh
"$PYTHON" -B "$HERE/diagnose.py" --raw "$RAW" --phase setup
"$PYTHON" -B "$HERE/diagnose.py" --raw "$RAW" --phase 64
# --phase 256 NOT executed: max64/execution.json was never returned.
```

`diagnose.py` reuses the prior controller's storage accounting, existing image and restricted container arguments. configuration.json/storage-roots.json map existing external assets; diagnostic_prefix must identify a fresh owned output volume. The new controller never mutates existing volumes, dependencies or model files. It fails on reused output markers. Freeze controller/worker hashes before invocation; see diagnostic-code-freeze.json. No acquisition or PP inference command is authorized by this failed admission run.

Metadata acquisition used official PyPI version JSON, the Paddle CPU index, pinned Hugging Face model API/card and versioned official repository source. Their URLs/hashes and exact metadata selections are in pp-admission.json, pp-model-inventory.json, pp-source-hashes.json and the external raw package. For each artifact row:

```sh
"$PYTHON" -B "$HERE/wheel_metadata.py" --metadata "$METADATA_JSON" --filename "$EXACT_WHEEL" --out "$NEW_ZIP_INVENTORY"
"$PYTHON" -B "$HERE/report_data.py" --raw "$RAW" --out "$NEW_REPORT_DIRECTORY"
```

For the vendor-only Linux wheel, the metadata row is assembled from official index URL plus exact HEAD/Range length, digests.sha256=null; it is not a PyPI result. wheel_metadata.read_range accepts only exact bounded HTTP206 responses from the official allowlisted hosts, with no package installation/extraction. `report_data.py` is offline and exclusively creates its destination; recorded authoritative generated outputs were exported into a fresh `export-verified` directory.

Full offline regression command on this host (compatible existing interpreter, broken .venv launcher left untouched):

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest -q
```

615 passed in 19.74 s. `--frozen` has no synchronization effect with `--no-project`; no install/sync occurred. Existing CI uses the unchanged standard project/offline test command in .github/workflows/tests.yml. CI status is reported on the PR after publication, not assumed from local success.
