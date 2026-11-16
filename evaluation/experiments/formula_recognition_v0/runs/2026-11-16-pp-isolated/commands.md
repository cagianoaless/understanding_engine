# Recorded execution and offline reproduction

No automatic session creation/restart, model retry or environment repair is authorized by these instructions. `$HERE` denotes this run directory, `$RAW` its external local evidence directory. Remote old root: `/content/understanding-engine-formula-gpu`; new root: `/content/understanding-engine-formula-pp-clean`.

1. `colab --auth oauth2 status -s understanding-engine` verified the existing T4. `colab ssh ... -- nvidia-smi` later returned HTTP429 (occupied SSH); no other connection was killed. The official `exec` transport was reused after read-only checks showed no acquisition/start markers following disconnects.
2. Read-only source inspection found ModelScope logger's `if find_spec("torch") is not None` guard. Existing model/crop/runtime artifacts were inventoried; no CodeFormula inference ran.
3. Upload and execute the single correction script:

```sh
colab --auth oauth2 upload -s understanding-engine "$HERE/setup_clean.py" /content/ue-pp-clean-setup.py
# Inside the existing session through colab exec:
/usr/bin/python3 -B -u /content/ue-pp-clean-setup.py \
  --root /content/understanding-engine-formula-pp-clean \
  --old /content/understanding-engine-formula-gpu
```

The script exclusively creates its root/venv, re-verifies the retained 1,977,882,736 B Paddle wheel, uses `uv venv --seed` without system-site-packages, resolves only binary artifacts with previous-version constraints, rejects Torch/Docling additions, writes a full hash-pinned declared-base lock, and installs with `pip --no-deps --require-hashes --no-cache-dir`. `-I` and isolated env variables disable user/system Python inheritance. No LD_LIBRARY_PATH change is made. Exact subprocess commands are in setup-result.json; installed-base.lock preserves the executed lock. Its name is deliberately scoped: it proved incomplete for the formula decoder.

4. Upload only `inputs.json`, `acquire.py`, `pp_worker.py`, `pp_control.py`, `inference-freeze.json`. The eight original remote PNGs are reused read-only; neither reference LaTeX nor a PDF is uploaded.
5. After setup/import/tiny CUDA PASS, execute acquisition once:

```sh
/content/understanding-engine-formula-pp-clean/runtime/bin/python -I -B -u \
  /content/understanding-engine-formula-pp-clean/acquire.py \
  --root /content/understanding-engine-formula-pp-clean
```

Only inference.json, inference.pdiparams, inference.yml at the pinned revision are acquired. The weights match the frozen SHA-256; metadata files match their Git blob identities and newly computed SHA-256 values. No unrestricted revision/model variant is used.

6. Execute the first target through the external watchdog:

```sh
/content/understanding-engine-formula-pp-clean/runtime/bin/python -I -B -u \
  /content/understanding-engine-formula-pp-clean/pp_control.py \
  --root /content/understanding-engine-formula-pp-clean \
  --crop-root /content/understanding-engine-formula-gpu/crops --id attn_fraction
```

The worker uses official `FormulaRecognition(model_name="PP-FormulaNet-S", model_dir=..., device="gpu:0", enable_hpi=False, use_tensorrt=False, precision="fp32", enable_mkldnn=False, cpu_threads=4)`. Construction fails at missing tokenizers in UniMERNetDecode before `model.predict()` is invoked. The parent records exit1 and cleanup; all seven later targets remain unexecuted. The controller's prefix-success and exclusive start guards reject continuing after failure or repeating a target. No further package install, workaround or invocation occurred.

7. Export only small JSON/log/lock/script evidence, excluding runtime, setup cache and model payload directories. Download through the official CLI:

```sh
colab --auth oauth2 download -s understanding-engine \
  /content/understanding-engine-formula-pp-clean/evidence.zip "$RAW/evidence.zip"
```

Recorded ZIP: 765,401 bytes, SHA-256 `76e5668a9f33f710e304a8d0f45eded053b0464889d4ffb15263fdd97f7a6175`. Local verification rejected unsafe/duplicate paths, symlinks, per-member/total expansion excess and checked the archive hash. The 32 members expanded to 2,901,557 B. All raw failure text and metadata were downloaded before local comparison reporting.

8. Reproduce the failure accounting offline into a new output directory:

```sh
"$PYTHON" -B "$HERE/summarize.py" --evidence "$RAW/evidence" --destination "$NEW_OUTPUT"
```

This reads the preserved CodeFormula published scores without rerunning or modifying them. All PP quality fields remain null; source/annotation discrepancies are not corrected. No formula rendering is possible because no LaTeX was returned.

9. Run the complete offline suite using the existing compatible host CPython 3.11.13, leaving the broken .venv launcher unchanged:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
uv run --frozen --offline --no-project --python "$PYTHON" "$PYTHON" -B -m pytest -q
```

`--frozen` has no synchronization effect with `--no-project`; no host dependencies are installed. Exact-head GitHub CI is reported on the PR. Do not retry model construction or install tokenizers from these reproduction notes without the separate authorization required by the one-correction stop boundary. Do not call `colab stop`; the user's existing runtime remains running.
