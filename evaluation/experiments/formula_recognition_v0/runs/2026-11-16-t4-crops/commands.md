# Recorded commands and reproduction

Do not overwrite the completed remote run, repeat inference or allocate a new session merely to reproduce this report. `ROOT=/content/understanding-engine-formula-gpu`; `$HERE` is this tracked run directory; `$RAW` is a new external local evidence directory. References are deliberately absent from inference inputs. The completed predictions can be evaluated offline without Colab.

## Existing-session inspection

```sh
colab --auth oauth2 status -s understanding-engine
colab --auth oauth2 ssh -s understanding-engine -- nvidia-smi
```

The first returned the existing T4 session. The second returned HTTP429 (another SSH connection active). No SSH connection was killed. Official CLI `exec` was used instead:

```sh
colab --auth oauth2 exec -s understanding-engine --timeout 60 <<'PY'
import sys, torch, subprocess, importlib.metadata as md
print(sys.version, torch.__version__, torch.version.cuda)
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
print(subprocess.run(['nvidia-smi'], capture_output=True, text=True).stdout)
PY
```

`colab version` reported 0.8.0. No credentials, key files or authentication configuration were read/copied/edited. The CLI uses its normal existing OAuth authentication and logging.

## Isolated setup

Remote root was created exclusively. Standard `python -m venv` failed because ensurepip was unavailable. Existing uv created a separate environment:

```sh
uv venv --no-python-downloads --system-site-packages --python /usr/bin/python3 \
  /content/understanding-engine-formula-gpu/cf-runtime
```

Before installation the constrained dry-run preserved the preinstalled CUDA stack:

```sh
/content/understanding-engine-formula-gpu/cf-runtime/bin/python -m pip install \
  --dry-run --report /content/understanding-engine-formula-gpu/cf-resolution.json \
  --constraint /content/understanding-engine-formula-gpu/preserve-cuda.txt docling==2.148.0
```

Constraints were `torch==2.14.1+cu130`, `torchvision==0.29.1+cu130`, `transformers==5.22.1`. The uv resolver attempt failed to recognize the preinstalled vendor build; pip found it. The accepted pip report was converted to `name==version --hash=sha256:...` for each addition. No Torch/Transformers replacement was allowed.

```sh
/content/understanding-engine-formula-gpu/cf-runtime/bin/python -m pip install \
  --no-deps --require-hashes --no-cache-dir \
  --report /content/understanding-engine-formula-gpu/cf-installed.json \
  -r /content/understanding-engine-formula-gpu/cf-added.lock
```

The exact addition lock is retained as codeformula-added.lock; full package URLs/hashes and active/imported versions are in runtime.json and the external pip reports. This is a GPU-specific environment, not the old ARM64 dependency lock. Source SHA-256 values tie the used Docling engine/stage/preset to 2.148.0.

## Authorized transfers and pinned acquisition

Only these four small files and eight PNGs were uploaded:

```sh
colab --auth oauth2 upload -s understanding-engine "$HERE/inference-inputs.json" "$ROOT/inference-inputs.json"
colab --auth oauth2 upload -s understanding-engine "$HERE/gpu_worker.py" "$ROOT/gpu_worker.py"
colab --auth oauth2 upload -s understanding-engine "$HERE/gpu_control.py" "$ROOT/gpu_control.py"
colab --auth oauth2 upload -s understanding-engine "$HERE/acquire_model.py" "$ROOT/acquire_model.py"
# Sequentially, for the eight exact paths/hashes in the frozen input manifest:
colab --auth oauth2 upload -s understanding-engine "$ORIGINAL_CROP" "$ROOT/crops/$ID.png"
```

Original source paths are in the external local crop map; no path is derived from an unrestricted filesystem listing. Every local and uploaded crop hash/length matched. No PDF, reference LaTeX, local archive, credential or unrelated document was uploaded.

Executed on Colab after all crop checks:

```sh
/content/understanding-engine-formula-gpu/cf-runtime/bin/python -B -u \
  /content/understanding-engine-formula-gpu/acquire_model.py \
  --root /content/understanding-engine-formula-gpu
```

This downloads only the eleven exact pinned model files. All expected lengths/SHA-256 values are checked before inference; no unrestricted Hugging Face revision or remote code is loaded. Hashes were checked again by each worker.

## Inference

First ID was `attn_fraction`:

```sh
/content/understanding-engine-formula-gpu/cf-runtime/bin/python -B -u \
  /content/understanding-engine-formula-gpu/gpu_control.py \
  --root /content/understanding-engine-formula-gpu --id attn_fraction
```

The controller calls the actual Docling `CodeFormulaVlmModel.engine.predict_batch` crop interface, records its `generate()` tokens/events, and externally kills only the owned worker process group after 180 seconds. Exclusive start markers prevent duplicate calls. It sets offline artifact flags, deterministic seed/configuration and four CPU threads; it does not claim a Colab cgroup or network namespace.

After the first return, the exact same command ran sequentially for:

```text
attn_heads
attn_ffn
attn_positional
nature_weights
nature_softmax
log_eq2
log_eq4
```

A transport disconnect occurred before the remaining-loop code started. A read-only marker check found only attn_fraction.started.json. The next command launched only the seven unstarted IDs. No generation was repeated or accuracy-tuned. `cf-completion.json` uses “completed” to mean a returned process; evaluation separately identifies seven EOS returns and one incomplete native repetition stop.

## Optional Paddle setup — do not retry the failure

After all eight CodeFormula calls returned, bounded official-index/ZIP-metadata inspection selected the CUDA-13 CPython-3.13 Paddle 3.3.1 wheel. Its full payload was acquired only on Colab and independently SHA-256 hashed. A separate `pp-runtime` system-package-sharing venv received only the hash-pinned additions in paddle-added.lock. Whole-wheel publisher SHA-256 was unavailable; the recorded actual hash pins the acquired file.

```sh
/content/understanding-engine-formula-gpu/pp-runtime/bin/python -m pip install \
  --no-deps --require-hashes --no-cache-dir \
  --report /content/understanding-engine-formula-gpu/pp-installed.json \
  -r /content/understanding-engine-formula-gpu/pp-added.lock
```

Paddle imports and sees the GPU, but importing `FormulaRecognition` fails at ModelScope's Torch import with `undefined symbol: ncclCommResume`. The fatal import stopped this candidate: **no PP model acquisition, prediction or environment workaround followed**. The complete traceback/metadata reports are external. CodeFormula's original versions and a tiny CUDA operation were verified in its separate process afterward; no model rerun occurred.

## Evidence transfer and local-only evaluation

Remote ZIPs were constructed from explicit small evidence file types/locations, excluding all environments, package wheels, model weights and original PDFs. Downloaded artifacts:

```sh
colab --auth oauth2 download -s understanding-engine "$ROOT/cf-evidence.zip" "$RAW/cf-evidence.zip"
colab --auth oauth2 download -s understanding-engine "$ROOT/pp-setup-evidence.zip" "$RAW/pp-setup-evidence.zip"
colab --auth oauth2 download -s understanding-engine "$ROOT/runtime-active.json" "$RAW/runtime-active.json"
colab --auth oauth2 download -s understanding-engine "$ROOT/nvidia-smi.final.txt" "$RAW/nvidia-smi.final.txt"
```

Both ZIP hashes, member types, paths, individual sizes and total expansion were validated locally before extracting. Native predictions, every generated token ID, start markers, stdout/stderr, resource samples and configuration were preserved. Model configurations (small files only) are included. No remote payload is executed on the Mac.

Each unchanged cleaned prediction was embedded in the same article/amsmath `align*` display wrapper, then rendered locally with the existing tool:

```sh
tectonic --only-cached --untrusted --keep-logs --outdir "$RAW/renders" "$RAW/renders/$ID.tex"
```

The sandboxed renderer initially failed at macOS SystemConfiguration; a normal approved native invocation succeeded without font downloads. Six bodies compiled; two failed and were not repaired. Generic alignment context is documented in render-results.json. Full-resolution artifacts stay external.

```sh
"$PYTHON" -B "$HERE/evaluate.py" --evidence "$RAW/cf-evidence" \
  --pp-evidence "$RAW/pp-evidence" --renders "$RAW/render-results.json" \
  --destination "$NEW_OUTPUT_DIRECTORY"
"$PYTHON" -B "$HERE/visualize.py" --evidence "$RAW/cf-evidence" \
  --crops "$ORIGINAL_CROP_DIRECTORY" --renders "$RAW/renders" --output "$FIGURE"
```

Evaluation is local and uses the unchanged frozen references/scorer. The agent adjudication sidecar is distinct from automated spelling comparisons and remote inputs. No prediction correction or reference edit occurs. The output was reproduced byte-for-byte in a second fresh destination.

## Offline tests and stop

On this Mac, use the existing compatible CPython 3.11.13 and existing site-packages; leave the broken .venv launcher untouched:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
uv run --frozen --offline --no-project --python "$PYTHON" "$PYTHON" -B -m pytest -q
```

`--frozen` has no synchronization effect with `--no-project`; no installation occurred. Existing GitHub CI retains the normal locked/offline test command. Exact-head status is recorded on the PR after publication.

Do not call `colab stop`, restart the kernel, allocate another session, repeat crops, or run detection from these instructions. The user's existing session remains alive; remind them to release it after reviewing the downloaded results.
