# Reproduction and exact execution scope

Parent PR #14: `4104548e2779d8c44d9e000f2d364dc22271ecc8`. Source/model/selection/policy pins are alongside this file. A new run needs deliberate authorization and fresh named resources/output paths; **do not replay inference automatically**. No benchmark loop is provided.

`$REPO` is this checkout; `$SMOKE_RAW` is a fresh directory under `/private/tmp` outside every Git ancestor; `$EXISTING_PYTHON` is the already installed intact host CPython 3.11.13. Raw physical paths are withheld from Git. The host controller uses macOS standard-library Python only for I/O/subprocess supervision; the scientific candidate runs **Linux ARM64 CPython 3.11.13**.

## Source, licensing and resource admission

```sh
git status --short --branch
git rev-parse HEAD
cat AGENTS.md
git switch -c feat/experiment-006b-one-page-smoke
git -C "$SMOKE_RAW" rev-parse --show-toplevel  # Must fail: outside all Git roots.
df -k /System/Volumes/Data
colima -p ue006b status --json
colima -p ue006b ssh -- df -Pk / /var/lib/docker
docker context show
```

Snapshot every original tracked file SHA-256 before changes. Verify the original Attention PDF hash and freeze page 6 **before predictions**. Copy the retained-root mapping from PR #14's external `storage-roots.json` and append `$SMOKE_RAW`; include `.colima`, exact installed runtime kegs, old setup/metadata/archive/evidence/cache roots, never just this new directory. `Control.snapshot()` uses the old bounded no-symlink-following allocated-block collector, while `limits()` applies this run's prospective **6 GiB** policy and 128 MiB preventive margin. Guest root and Docker-data free capacity are checked separately, with a 256 MiB reserve plus prospective producer growth admission. No cleanup or resizing is part of admission.

Version-specific GitHub ref/tag dereferences and LICENSE/version-manifest sources are listed in `license-sources.json`. Source texts and original responses are retained externally; hashes identify every body. Reuse PR #14 native notices. `licensing.json` records the intended private-use decision and redistribution caveats; it does not demand universal SPDX metadata.

The small official OCI scout retained index/config/manifest bodies and hashes. It requested an anonymous `library/python:pull` registry token (not persisted), selected Linux ARM64/v8 from `python:3.11.13-slim-bookworm`, verified manifest/config SHA-256 and `PYTHON_VERSION=3.11.13`, and summed layer sizes. `image-lock.json` records every endpoint/digest; use that immutable image, not tag re-resolution, for reproduction. No layer/model was acquired by the metadata scout.

## Runtime and offline candidate

The external `configuration.json` supplies only local paths/unique resource names: `docker_host` for ue006b, existing dedicated `docker_config`, the retained PR #14 `archives` directory, `prefix`, fresh `volume`, pinned-model metadata cache and original `pdf`. The controller removes child DOCKER_CONTEXT/DOCKER_HOST overrides and uses `docker --host "$UE006B_SOCKET"`; it never changes the user's context/configuration. These machine-specific values stay outside Git.

```sh
/usr/bin/python3 -B -I -S "$REPO/evaluation/experiments/006b/runs/2026-11-10-one-page-smoke/control.py" \
  --raw "$SMOKE_RAW" --phase runtime
/usr/bin/python3 -B -I -S "$REPO/evaluation/experiments/006b/runs/2026-11-10-one-page-smoke/control.py" \
  --raw "$SMOKE_RAW" --phase install
```

All exact subprocess argv/exit codes/stdout/stderr are in the external `commands.jsonl`. The runtime command pulls only the digest in `image-lock.json`, with a bounded footprint reservation; runtime check verifies Python, architecture, actual glibc/wheel-tag compatibility, rootfs layer diff IDs and cgroup swap zero. No candidate/model is installed in this step.

Installation rehashes every retained wheel, creates one labelled volume, sets permissions only on that new volume, and creates a restricted UID 65534 container. All 103 source wheels are copied once into it. The actual pip command inside the networkless container is:

```sh
python -B -m pip --isolated install --target /ue/candidate \
  --no-deps --no-index --no-cache-dir --no-compile --only-binary=:all: \
  --require-hashes --find-links /ue/wheels --report /ue/install-report.json \
  -r /ue/requirements.cpu.lock
python -B /ue/validate_install.py
```

No source resolution, CUDA fallback or new package download can occur. The validator checks target distribution equality, all wheel hashes and pip report file URLs/hashes, then exercises the recorded imports. Retain bootstrap runtime packages separately from the exact 103-package target. Container `PYTHONPATH` explicitly selects `/ue/candidate`; no host environment is used inside it.

The original run encountered a controller log collision **before pip**. The prepared volume/source was preserved; `--phase finish-install` performed the first pip installation with corrected distinct logs. A later 64 MiB step estimate stopped verification on delayed VM writeback, not the user cap or OOM. After `colima -p ue006b ssh -- sync`, `--phase check-imports` repeated only hash/import verification with a 512 MiB admission reservation within the unchanged 6 GiB cap. Original sources/failure logs remain externally hashed; `setup-interruptions.json` explains both. The final controller supports an uninterrupted fresh `--phase install`; continuation flags require existing owned resources and must not be used as a dependency-repair retry.

## Minimal model and one actual page

Proceed only after runtime/install/license gates PASS:

```sh
/usr/bin/python3 -B -I -S "$REPO/evaluation/experiments/006b/runs/2026-11-10-one-page-smoke/one_page.py" \
  --raw "$SMOKE_RAW" --phase model
/usr/bin/python3 -B -I -S "$REPO/evaluation/experiments/006b/runs/2026-11-10-one-page-smoke/one_page.py" \
  --raw "$SMOKE_RAW" --phase smoke
```

Model acquisition reads the frozen minimal-file inventory from the unchanged Linux preflight. Cached config bodies are reused only after exact hash checks; the only new model GET is the pinned weight URL. It validates exact byte length/SHA-256 before atomic rename, accepts only HTTPS Hugging Face/CDN redirects, persists no signed URL queries or user token, and checks host allocation/reserve during <=1 MiB chunks. The three files are copied/verified in the guest; no model executes in this acquisition step.

The smoke step creates an exclusive `single-attempt.json` before launch; it cannot automatically run twice. Its fresh container has memory/swap `4294967296/4294967296` (actual swap.max **0**), CPU quota **4**, affinity **0–3**, pids limit **256**, network **none**, UID **65534:65534**, dropped capabilities, no-new-privileges, read-only root, one experiment volume and no host mounts/socket/GPU. HF offline flags and all thread settings are recorded in the command ledger; no home/SSH-agent forwarding occurs.

`smoke_page.py` validates actual cgroups before neural imports, configures the frozen CPU/disabled-feature options and local Heron path/revision, and calls `DocumentConverter.convert(original_pdf, page_range=(6,6))` once. It wraps only the model batch entry point to reject any second/wrong/multiple-page prediction, otherwise delegates without changing pixels/options/results. It preserves native document, Markdown, order/items, layout and kernel samples in `/ue/output`. A separate host Timer arms an owned-container kill at **120 seconds**, independently of the polling supervisor. The successful run finished before expiry; there was no inference retry.

The host copies the stopped container's output to `$SMOKE_RAW/page-output`. `execution.json` identifies timing scopes, actual kernel memory/cpu counters and container status. `page-structure.json` is a compact native-output projection; complete native outputs/hashes remain external. No scientific scoring or Unicode correction is performed.

## Tests and final preservation

The old project launcher fails because its original temporary CPython base lacks stdlib source files. It was not repaired. Use the already installed intact **3.11.13**, existing source/site-packages **read-only**, and no sync/download:

```sh
PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$SMOKE_RAW/test-cache" \
uv run --frozen --offline --no-project --python "$EXISTING_PYTHON" \
  "$EXISTING_PYTHON" -B -m pytest
```

Observed: **343 passed**, zero failures/skips, 8.11 s; all 22 installed project distributions checked against uv.lock match their locked versions. uv warns that `--frozen` has no effect with `--no-project`; no resolution, synchronization or installation occurred. Existing CI separately executes the normal `uv run --frozen --offline pytest` under pinned Python 3.11.13.

Final checks: guest `sync` and `df -Pk / /var/lib/docker`; bounded allocated-block snapshot of every registered root; context still `default`; Colima config SHA-256 matches its prior value; original 281 tracked SHA-256 values and Attention source hash match. All owned containers are stopped; retain every volume/image/archive/model/evidence artifact. A bounded filename search found no replacement copies for the absent registered BERT/Nature temporary paths. Do not silently download/substitute them.

**Stop after this page and publication.** Six-page authorization and the exact missing input locations are separate next requirements; no cleanup, tuning, model/version change, additional PDF inference or host-launcher repair follows.
