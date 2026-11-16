# Reproducible commands

The observed run is complete; its remote directory has been removed. These commands describe a **new, separately scheduled reproduction**, not an instruction to rerun this completed benchmark. `commands.json` preserves actual stage argument templates, exit codes, timing and raw evidence hashes, including failed diagnostics. Machine-specific command lines remain outside Git. `$HERE` is this directory, `$REMOTE` an authorized SSH alias, `$RUN` the new remote owned directory, `$RAW` a fresh local evidence directory, `$BASE_PYTHON` the existing read-only CPython3.12 interpreter and `$UV` the existing uv executable. No SSH/authentication configuration changes are required.

1. Read-only preflight used `uname`, `/etc/os-release`, CPU affinity/count, `/proc/meminfo`, `nvidia-smi`, scheduler-command discovery, `df`, `findmnt`, existing Python/uv and quota-tool discovery. Three GPU samples were5s apart. No scheduler was found; the user explicitly authorized sharing available capacity. Use the server's actual allocation rules, not a guessed reservation.
2. Create **one** fresh mode0700 directory under an appropriate user-writable local scratch filesystem. The observed run used local ext4 `/tmp`; do not reuse its deleted path or another user's directory. Bootstrap a `.experiment-owner.json` with exact canonical root, unique run_id, UID, owner, device/inode, filesystem and initial `statvfs` available bytes. The root basename must be `understanding-engine-pp-<run_id>`. Copy that marker locally as the expected identity before installation. Validate via `isolate.validate_root()`.
3. Transfer only inputs.json, base-constraints.txt, paddle-artifact.json, required scripts and the eight unchanged PNGs under `$RUN/crops/`. Verify crop hashes from inputs.json. Do not transfer PDFs or reference LaTeX. Use SSH options `BatchMode=yes`, `StrictHostKeyChecking=yes`, `UpdateHostKeys=no`, `ForwardAgent=no`, `ForwardX11=no`, `ClearAllForwardings=yes`; existing host/user details stay local.
4. Restore the private binary-only runtime through the write guard:

```sh
/usr/bin/python3 -S -B "$RUN/stage.py" --root "$RUN" --name prepare -- \
  /usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" -- \
  "$BASE_PYTHON" -I -B -X "pycache_prefix=$RUN/pycache" \
  "$RUN/prepare.py" --root "$RUN" --uv "$UV" --interpreter "$BASE_PYTHON"
```

The 2,021,398,367 B official Paddle CUDA12.6 CPython3.12 wheel has SHA-256 `b1500120002c2bf4542c841e25296cf10c52e0d395053aa395f79bd9c0303cce`. The initial run discovered/computed this hash before installation; the published preparation script additionally enforces that recorded identity in future reproductions. It is not represented as an independently supplied publisher checksum. Resolution is binary-only, rejects Torch/CPU-Paddle, records URLs/hashes and installs no-deps/require-hashes. `installed-artifacts.json` records the observed complete88-artifact final candidate closure; bootstrap seed versions are separately in runtime.json. No shared cache is writable.

5. Acquire exactly the three model files at the frozen revision. Direct server Hugging Face access was unavailable in the observed run. Acquisition instead used the previous run's `acquire.py` on the Mac in an external directory containing inputs.json. Verify expected bytes and SHA-256, transfer only those three files into `$RUN/model/`, then reverify remotely:

```sh
/usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" -- \
  "$RUN/runtime/bin/python" -I -B -X "pycache_prefix=$RUN/pycache" \
  "$RUN/verify_model.py" --root "$RUN"
```

6. Complete formula-specific dependencies **before inference** in a fresh reproduction. The observed history contains the first failed postprocessing attempt; do not reproduce it merely to make nine calls. `complete_decoder.py` resolves only ftfy6.3.1, checks that additional packages are limited to ftfy/wcwidth, hash-pins official wheels, rejects unexpected additions/replacements, runs pip check, and executes the exact official postprocessing method on neutral string `x`. In this run only ftfy was added because wcwidth was already present. tokenizers0.23.3 was installed by prepare.py.

```sh
/usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" -- \
  "$RUN/runtime/bin/python" -I -B -X "pycache_prefix=$RUN/pycache" \
  "$RUN/complete_decoder.py" --root "$RUN"
```

7. The **explicitly user-authorized** own-task exception in isolation-amendment.json is needed for CUDA. First create the synthetic `$RUN/test/allow` and `$RUN/test/deny/marker` (`preserve`) fixture. Run thread_metadata_probe.py through isolate.py with `--write-scope "$RUN/test/allow" --allow-self-task-metadata`. It must prove own thread writes and cuInit success, with denied persistent-sibling opens and child-process metadata writes. Each eventual CUDA process needs its own rule; a parent's task exception is not a child's exception. No `/proc`-wide rule or security-setting change is permitted.

```sh
/usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" \
  --allow-self-task-metadata -- \
  "$RUN/runtime/bin/python" -I -B -X "pycache_prefix=$RUN/pycache" \
  "$RUN/preflight.py" --root "$RUN"
```

Preflight validates actual cache paths, no system/user site or Torch, official tokenizer construction and one-element CUDA operation. Neural workers are guarded; `stage.py` and the stdlib benchmark supervisor only write owned logs/metadata. They do not import neural packages and do not need a parent Landlock exception that would prevent child-specific rules.

8. Run the prefix-gated sequence once, without references or model/crop tuning:

```sh
/usr/bin/python3 -S -B "$RUN/stage.py" --root "$RUN" \
  --name benchmark-decoder-complete -- \
  /usr/bin/nice -n19 /usr/bin/python3 -S -B "$RUN/benchmark.py" \
  --root "$RUN" --name decoder-complete
```

Each worker executes official `FormulaRecognition.predict()` on one PNG, FP32/GPU0/batch1, no HPI/TensorRT, four CPU-thread configuration and four-core affinity. Parent timer SIGKILLs only the owned process group after180s; nonzero exit, missing return, timeout, unsafe capacity or surviving process blocks further targets. Fresh output/freezes are exclusive; previous failed output is not overwritten. The eight-image denominator is preserved. The observed run had one failed first call plus eight post-correction calls, never a CodeFormula rerun.

9. Finalize with **Python3.12**, not the system3.10 interpreter (the finalizer uses hashlib.file_digest):

```sh
/usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" -- \
  "$RUN/runtime/bin/python" -I -B -X "pycache_prefix=$RUN/pycache" \
  "$RUN/finalize.py" --root "$RUN"
/usr/bin/python3 -S -B "$RUN/isolate.py" --root "$RUN" -- \
  /usr/bin/python3 -S -B "$RUN/package.py" --root "$RUN" \
  --name verified-final-results.zip
```

Download that ZIP and `verified-final-results.summary.json` before evaluation/cleanup. `verify_archive.py --archive ... --summary ... --destination ...` checks archive bytes/hash, safe bounded members, individual hashes and ZIP integrity. Keep model configurations, native predictions/resources, logs and package/identity manifests locally. The observed final archive/member hashes are in external-evidence.json.

10. Only after local verification, copy its acknowledgement as `$RUN/download-verified.json`. `cleanup.py --root "$RUN" --expected-json '<original identity JSON>' --archive-sha256 '<locally verified SHA>'` validates exact identity/mounts/owners, all recorded process exits and lsof handles, then unlinks descriptor-relative entries without following symlinks. It never terminates another process or broadens a target. Independent SSH then checked the directory absent and measured free space. The successful observed receipt is cleanup.json. Do not delete anything else or clean shared caches.
11. Local-only evaluation/rendering, after downloading raw outputs:

```sh
"$PYTHON" -B "$HERE/render.py" --evidence "$RAW/final-evidence" \
  --crops "$FROZEN_CROPS" --destination "$RAW/renders" --figure "$NEW_FIGURE"
"$PYTHON" -B "$HERE/compare.py" --evidence "$RAW/final-evidence" \
  --review "$HERE/adjudications.json" --rendering "$RAW/renders/render-results.json" \
  --destination "$NEW_LOCAL_SCORES"
```

Rendering uses existing Tectonic `--only-cached --untrusted`, common align* context for every unchanged body, and existing PDFium/Pillow. No fonts/packages or models are downloaded. comparison.png was visually inspected; malformed LoG bodies are never repaired. CodeFormula data is read directly from its preserved PR26 files and verified by SHA-256. Compare output regenerated byte-for-byte locally.

12. Full offline suite with the retained compatible Mac interpreter and existing site packages, without fixing the broken project launcher or installing dependencies:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
uv run --frozen --offline --no-project --python "$PYTHON" "$PYTHON" -B -m pytest -q
```

`--frozen` has no synchronization effect with `--no-project`; this uses the existing interpreter and site packages. CI uses the repository's unchanged locked setup and offline pytest workflow. No Colab command was run.
