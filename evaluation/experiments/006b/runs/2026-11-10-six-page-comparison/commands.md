# Commands and reproduction scope

These record the completed authorized Stage D, not permission to run more pages.
No command installs/resolves packages, downloads weights, pulls images, changes
settings, edits references or cleans prior artifacts. Exact expanded local argv,
exit statuses, stdout/stderr and container inspections are in the external
`commands.jsonl`, per-page logs and content-hash manifest.

`$REPO` is the repository; `$RAW` the new external temporary evidence directory;
`$INPUT_MAPPING` the user-authorized complete local overlay; `$SMOKE_RAW` the
retained PR15 evidence root. Physical locations remain in local manifests.
`$PYTHON` is the already installed intact CPython 3.11.13, not the broken project
launcher. `$RUN` is `evaluation/experiments/006b/runs/2026-11-10-six-page-comparison`.
The dated driver deliberately binds the user's specified registered overlay; a
different machine must explicitly reproduce/remap that location, never substitute
PDF identities. Docker configuration/socket are read from the retained external
configuration, never user context changes.

Initial read-only checks included:

```sh
git status --short --branch
git rev-parse HEAD
git diff ba82b2c7f71604d5bcc2859b1a05de112723107d -- src pyproject.toml uv.lock
df -k /System/Volumes/Data
```

The clean parent was `47882d327629fa90c0bdea47930f30d1696dcea4`.
Branch creation:

```sh
git switch -c feat/experiment-006b-six-page-comparison
```

Create a fresh directory under `/private/tmp`, verify `git rev-parse
--show-toplevel` fails there, save SHA-256 of every pre-existing tracked file,
and copy the retained PR15 `configuration.json` and registered `storage-roots.json`
as **new local manifests**. Add the PR16 restored-input/evidence directories and
new output directory to allocation roots; do not reset older consumption. No
previous run was reused as a writable output directory. The preserved
`preexisting-tracked.json`, `parent.json`, `storage-roots.json` and
`configuration.json` record the actual preparation.

Executed host commands, with only local path variables substituted:

```sh
export PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.11/site-packages"
"$PYTHON" -B "$REPO/$RUN/prepare_sources.py" \
  --raw "$RAW" --mapping "$INPUT_MAPPING" \
  > "$RAW/prepare.stdout.log" 2> "$RAW/prepare.stderr.log"

"$PYTHON" -B -m pytest tests/test_006b_comparison.py -q \
  > "$RAW/adapter-tests.stdout.log" 2> "$RAW/adapter-tests.stderr.log"

"$PYTHON" -B "$REPO/$RUN/run.py" --raw "$RAW" --phase predictions \
  > "$RAW/predictions.stdout.log" 2> "$RAW/predictions.stderr.log"

"$PYTHON" -B "$REPO/$RUN/run.py" --raw "$RAW" --phase score \
  > "$RAW/scoring.stdout.log" 2> "$RAW/scoring.stderr.log"

UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RAW/test-cache" \
  /opt/homebrew/bin/uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest \
  > "$RAW/pytest.stdout.log" 2> "$RAW/pytest.stderr.log"

"$PYTHON" -B "$REPO/$RUN/reporting/derive.py" \
  --raw "$RAW" --output "$RAW/derived-reproduction"
cmp "$REPO/$RUN/summary.json" "$RAW/derived-reproduction/summary.json"
cmp "$REPO/$RUN/resources.json" "$RAW/derived-reproduction/resources.json"
```

`uv --no-project` avoids touching the existing broken launcher/environment;
`--frozen` has no effect in this mode. The host interpreter and project packages
already exist; no resolution, synchronization or dependency installation occurs.
The existing CI separately uses its normal locked environment. Tests import only
the stdlib adapter; no neural import/inference occurs in regression tests.

`prepare_sources.py` hashes every freeze member, verifies PDF bytes/page trees,
regenerates exact full caches, validates original source IDs/strips/geometry, and
requires the original cache hashes. Native parser outputs are never changed.
The prediction driver freezes its five top-level Python file hashes first.
Native outputs are frozen separately before scoring. Re-running either phase
on the same output directory fails rather than overwriting results.

Each measured worker uses the retained digest-pinned image with `--pull=never`:

```text
docker --host "$DOCKER_HOST" create --pull=never --name "$OWNED_PAGE_NAME"
  --network none --read-only --user 65534:65534
  --memory 4294967296 --memory-swap 4294967296
  --cpus 4 --cpuset-cpus 0-3 --pids-limit 256 --cap-drop ALL
  --security-opt no-new-privileges
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777
  --mount type=volume,source="$EXISTING_CANDIDATE_VOLUME",target=/ue,readonly,volume-nocopy
  --mount type=volume,source="$NEW_OUTPUT_VOLUME",target=/run,volume-nocopy
  <explicit offline/cache/thread environment in run.py>
  python@sha256:18ce9b03d18802119f4f9270d10a1ceb45d0acb768c305b7fbbd7c6b5b5a020b
  python -B /run/<baseline_page.py|docling_page.py>
  --source /run/<sources/original-extraction.json|input/original.pdf>
  --page <one frozen original page> --output /run/output/<engine-page>
docker --host "$DOCKER_HOST" start -a "$OWNED_PAGE_NAME"
docker --host "$DOCKER_HOST" inspect "$OWNED_PAGE_NAME"
docker --host "$DOCKER_HOST" cp "$OWNED_PAGE_NAME:/run/output/<engine-page>" "$RAW/native/<engine-page>"
```

The exact 12 create/start/copy command vectors and flags are in `commands.jsonl`.
An independent host timer starts with each page job and kills **only its owned
container/process group** at 120 seconds. It did not fire. Storage/host reserve
are checked during work; guest `df` and `sync` are capacity/accounting checks,
not repeated runtime provisioning tests. No containers/images are pruned.

Baseline workers copy **unchanged project source only**, not new dependencies,
into the new volume and use existing Linux validator packages. Six original-host
runs provide exact full-page semantic equivalence checks; both native ID sets
are preserved. Only the measured Linux containers contribute comparative cost.
The host `RLIMIT_AS(4GiB,4GiB)` control probe failed before prediction with
`ValueError: current limit exceeds maximum limit`; no host setting was changed.

`reporting/derive.py` is supplementary arithmetic over already immutable scores,
added after scoring. It reproduces document macros, explicit fractions and
resource summaries byte-for-byte. It never runs a model or changes any score.
Explanatory examples are post-score selections, not new evaluation annotations.

After verification, a bounded hash-checked copy of the new raw directory was
saved in a fresh mode-0700 `/Users/Shared` directory outside every Git root. Both
copies, new public evidence and Git metadata are in subsequent allocation roots.
The copy's actual manifest, local locations and per-copy resource samples remain
external. No large PDF/cache/native artifact or secret is committed.

Source/scoring reproduction should consume frozen native files and the same
`comparison.py`; **no further inference is authorized by this report**. Native
outputs, original raw summary and re-derived report summary have separate hashes.
Do not modify annotations to repair disagreements. All references remain
agent-checked; independent human validation is still outstanding.
