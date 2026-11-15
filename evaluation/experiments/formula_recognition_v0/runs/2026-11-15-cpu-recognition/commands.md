# Recorded bounded continuation

Run from the repository root using the existing compatible CPython 3.11.13 and
installed packages. No dependency resolution/sync/install is required. The actual
local paths/configuration, Docker argv/logs and input mapping are in the external
run package; no private paths or tokens are committed.

These are the stages actually executed. **Do not rerun against retained destinations**:
setup/acquisition/output creation is exclusive. A fresh inference run needs its
own external directory/volume and applicable authorization. The first-failure
stop rule remains in force; no later target/page command was executed.

```sh
export PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages"
export UE_FORMULA_CODE=evaluation/experiments/formula_recognition_v0/runs/2026-11-15-cpu-recognition
"$UE_PYTHON" -B "$UE_FORMULA_CODE/control.py" --raw "$UE_RUN" --phase setup
"$UE_PYTHON" -B "$UE_FORMULA_CODE/control.py" --raw "$UE_RUN" --phase acquire
# The transfer expired after exactly 417333248 weight bytes; initial log preserved.
"$UE_PYTHON" -B "$UE_FORMULA_CODE/complete_transfer.py" --raw "$UE_RUN"
"$UE_PYTHON" -B "$UE_FORMULA_CODE/control.py" --raw "$UE_RUN" --phase prepare
"$UE_PYTHON" -B "$UE_FORMULA_CODE/control.py" --raw "$UE_RUN" \
  --phase invoke --label crop-attn_fraction
```

The final command's controller exit code is not the model result. It collects the
container state even on failure. Its record shows `timeout=true`, container exit
137, `OOMKilled=false`; no successful worker `execution.json` exists. Any
subsequent invocation requires a SUCCESS worker record and successful generate
return; absent evidence fails closed before Docker execution. Do not loop over
tasks based only on a successful controller command.

The frozen input task is `/run/tasks/crop-attn_fraction.json`; the network-disabled
candidate executes `python -B -u /run/worker.py --task ...`. Old candidate volume
is read-only at `/ue`, new owned volume at `/run`; no home bind or Docker socket.
Image identity remains
`python@sha256:18ce9b03d18802119f4f9270d10a1ceb45d0acb768c305b7fbbd7c6b5b5a020b`.
The external watchdog is inherited unchanged from Stage D's `Run.job`; only the
prospective storage/reserve checks are overridden in the new continuation class.
The initializers only set permissions on the newly created volume.

Replay **analysis only** into a new external destination, without model imports,
network, document conversion or Docker calls:

```sh
export UE_ANALYSIS="$(mktemp -d /private/tmp/understanding-engine-formula-analysis-XXXXXX)"
"$UE_PYTHON" -B "$UE_FORMULA_CODE/summarize.py" \
  --raw "$UE_RETAINED_RAW" --out "$UE_ANALYSIS/results"
```

It checks the frozen code/selection/reference hashes, actual event sequence and
container exit evidence. It refuses to manufacture this timeout report if a
completed generation is present. Golden references are opened only in this
separate analysis stage. Scoring has no influence on prediction input or configuration.

Full normal suite: `uv run --frozen --offline pytest`. Existing broken host launcher
remains unrepaired; the measured host uses the already-installed interpreter and
locked packages read-only:

```sh
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$UE_RUN/test-cache" \
uv run --frozen --offline --no-project --python "$UE_PYTHON" \
  "$UE_PYTHON" -B -m pytest -q
```

uv warns that `--frozen` has no effect under `--no-project`. No resolution or
installation occurs. Unchanged CI uses the normal frozen Python 3.11.13 workflow.
Existing viewer regressions require loopback socket access. No tests import the
neural stack, acquire models or execute inference.
