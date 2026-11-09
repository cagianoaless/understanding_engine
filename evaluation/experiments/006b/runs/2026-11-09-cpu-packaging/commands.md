# Reproduction — metadata only

Use parent PR #12 commit `1fba0d4834ee20697529c2b79e18a61cf814bf53` plus the files in this follow-up. Preserve historical runs. The amended download policy is in `policy.json`; 4 GiB inclusive storage and 20 GiB host reserve remain mandatory.

`$REPO` means this checkout. Set `$CPU_RAW` to a **new empty directory under `/private/tmp`**, outside every Git ancestor (the user's home directory can itself be a Git checkout). Interpreter: the existing pinned project `.venv` CPython 3.11.13; uv 0.7.13, packaging 26.3. No dependency installation is needed. Do not reuse existing output destinations.

## Commands actually executed

Machine-specific arguments are redacted, with the exact argument vector, target, cutoff and HTTP request ledger in `resolution-evidence.json`.

```sh
git status --short --branch
git rev-parse HEAD
df -k /System/Volumes/Data
git -C "$CPU_RAW" rev-parse --show-toplevel  # Must fail: not a Git checkout.

"$REPO/.venv/bin/python" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-09-cpu-packaging/cpu_packaging.py" \
  --output "$CPU_RAW/resolver" \
  --python "$REPO/.venv/bin/python" --uv /opt/homebrew/bin/uv

"$REPO/.venv/bin/python" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-09-cpu-packaging/cpu_packaging.py" \
  --resolution "$CPU_RAW/resolver/resolution.json" --output "$CPU_RAW/inventory"

UV_CACHE_DIR="$CPU_RAW/test-cache" /opt/homebrew/bin/uv run --frozen --offline pytest \
  > "$CPU_RAW/pytest.stdout.log" 2> "$CPU_RAW/pytest.stderr.log"
```

The focused test file also passed before resolution. The full suite exited 0: 314 passed in 7.47 s. Existing project environment and lock remain unchanged. No inference imports are required by the packaging harness.

The initial source scout used GET on `https://download.pytorch.org/whl/cpu/torch/` and `/torchvision/`, parsed compatible wheel names and public versions, read only their `.whl.metadata` sidecars, and issued HEAD to selected wheel URLs. Its request/size/hash ledger is included in `resolution-evidence.json`. This scout is informational; the reproducible resolver independently fetches both indices and their selected sidecars, so rerunning the scout is unnecessary.

## Resolver contract

The harness reuses the prior immutable Linux tag, marker/extra dependency-edge, sidecar verification and license helpers. It routes only `torch`, `torchvision`, `torchaudio` to official CPU sources. Other names use PyPI exclusively. All public versions from PR #12 are constraints; disappearing CUDA nodes are not forced dependencies.

The actual uv invocation is equivalent to:

```sh
uv --no-config --cache-dir "$CPU_RAW/resolver/resolver-cache" pip compile \
  "$CPU_RAW/resolver/requirements.in" \
  --constraints "$CPU_RAW/resolver/constraints.in" \
  --python "$REPO/.venv/bin/python" \
  --python-version 3.11.13 --python-platform aarch64-manylinux_2_39 \
  --only-binary :all: --generate-hashes \
  --exclude-newer 2026-11-06T00:00:00Z \
  --default-index "http://127.0.0.1:$GATEWAY_PORT/simple" \
  --output-file "$CPU_RAW/resolver/requirements.lock" \
  --no-python-downloads --keyring-provider disabled
```

The gateway port is ephemeral. The harness starts it, discards inherited PIP_/UV_ overrides, and supplies loopback NO_PROXY. **Do not replace the gateway with an unrestricted direct resolver**: it refuses wheel/sdist/range payload forwarding before network acquisition, and stops on unexpected payload demand. The per-response/aggregate metadata bounds are safety guards for this metadata-only task, not a reinstated 2 GiB download ceiling. There were zero blocked payload requests or gateway errors in this observed solve.

The selected CPU artifact sizes come from official HEAD responses, hashes from official indices, and sidecar bodies were verified against advertised hashes. Unchanged PyPI wheel declarations are reused only after fresh index artifact hashes and sidecar hashes match PR #12. `requirements.cpu.lock` pins every selected hash; **it is not an installation command**, and its CPU local versions require the explicitly recorded source policy/exact URLs in `dependencies.json`. No default PyPI install fallback is authorized.

## Storage and accounting reproduction

Run `df -k /System/Volumes/Data`. For only the registered roots in `accounting.json`, use `du -sk` and a bounded no-symlink-following walk of regular files summing `st_blocks * 512`, deduplicating device/inode pairs. Record logical `st_size` separately. Previously registered runtime, VM, exact installed Homebrew kegs, old evidence/cache directories and this external run stay included; do not remove or move them. VM images already include guest Docker layers. APFS exclusive sharing and historical peaks cannot be inferred from these snapshots.

Measured current roots: 2,049,421,312 allocated bytes. All CPU archives: sum `records[*].selected_wheel.bytes` = 379,580,121. Pinned minimal Heron files from unchanged prior evidence: 171,662,708 bytes. New planning allowance: 67,108,864 bytes. Forecasts and unknown runtime/unpacked/temp/duplicate terms are explicit in `accounting.json`; no compressed size is substituted for them.

Preservation: compare every path in `preservation.json` against its recorded SHA-256 and inspect `git diff` relative to the parent. None of the 237 prior tracked paths may change. Raw external-file hashes and sizes are in `external-evidence-manifest.json`; raw physical paths are intentionally not committed. A host free-space snapshot is not a historical/continuous peak measurement.

## Proposed next stage — NOT executed

`archive-audit-proposal.json` is the exact 103-artifact URL/SHA-256/size allowlist and acquisition guards. It proposes wheel archives plus bounded license/ZIP inspection only. **Do not execute any payload download, install, model acquisition, image pull or inference from these instructions without separate authorization.** Neither the withdrawn download ceiling nor this generated lock authorizes those actions.
