# Reproduce this metadata-only preflight

This is not authorization to install or acquire payloads. Start from commit `86832cf743ad03020fdfbe58ebb726edf3d2df85` on a clean feature branch; use existing Python 3.11.13 / uv 0.7.13 and select a new output directory outside Git. Never overwrite previous runs. Do not pull an image or install Python/Docling.

## Runtime/accounting recheck

Record `df -k /System/Volumes/Data` and preserve at least 20 GiB available. In the existing dedicated Docker configuration, inspect:

```sh
colima -p ue006b status --json
docker --context colima-ue006b info --format '{{json .}}'
docker --context colima-ue006b ps -a --format '{{json .}}'
docker --context colima-ue006b images --digests --format '{{json .}}'
docker context show
colima -p ue006b ssh -- sh -c 'uname -m; getconf GNU_LIBC_VERSION; getconf _NPROCESSORS_ONLN; python3 --version; cat /proc/swaps; cat /sys/fs/cgroup/cgroup.controllers; df -k / /var/lib/docker; cat /proc/mounts'
```

The original default Docker context must remain unchanged. DOCKER_CONFIG points only to the existing external runtime's dedicated configuration; do not use `docker context use` or edit configuration. Inspect generated Colima configuration without opening keys. Count actual allocated blocks for the VM state, retained setup/image/Homebrew caches, kegs/logs, existing Experiment006 raw/cache directory and the new preflight output. Do not sum guest layers again on top of VM files. Do not change disk, mount, CPU, memory or SSH settings.

The collected VM reports glibc 2.39 and system Python 3.12.3; this audit explicitly targets CPython 3.11.13, without provisioning or substituting interpreters.

## Supported resolver controls

```sh
uv --version
uv --help
uv pip compile --help
```

Help from the installed binary confirmed the flags below. `--only-binary :all:` forbids source builds; do not combine it with this version's mutually exclusive `--no-build`. Interpreter downloads are forbidden. A successful native macOS solve is not reused as Linux evidence.

## Guarded resolution

Replace UE_PREFLIGHT_RAW with a fresh external path; it must not already exist. The script uses the existing project interpreter, starts a loopback-only metadata gateway, and generates this exact resolver argv with its observed port and private paths retained only in local raw evidence:

```sh
.venv/bin/python evaluation/experiments/006b/runs/2026-11-09-linux-preflight/audit.py \
  --uv /opt/homebrew/bin/uv --python "$PWD/.venv/bin/python" \
  --output "$UE_PREFLIGHT_RAW/resolver"
```

Effective uv invocation:

```sh
uv --no-config --cache-dir "$UE_PREFLIGHT_RAW/resolver/resolver-cache" pip compile \
  "$UE_PREFLIGHT_RAW/resolver/requirements.in" \
  --python "$PWD/.venv/bin/python" --python-version 3.11.13 \
  --python-platform aarch64-manylinux_2_39 --only-binary :all: \
  --generate-hashes --default-index "http://127.0.0.1:$GATEWAY_PORT/simple" \
  --exclude-newer 2026-11-06T00:00:00Z \
  --output-file "$UE_PREFLIGHT_RAW/resolver/requirements.lock" \
  --no-python-downloads --keyring-provider disabled
```

The wrapper removes inherited UV_/PIP_ overrides from its child process and bypasses proxies only for loopback. It queries PyPI through HTTPS and rewrites wheel links to its local guard. It may request only official index JSON and `.whl.metadata` sidecars, checks redirects, refuses direct-URL dependencies and stops before forwarding any wheel/sdist body or range request. Bounds: four concurrent upstream requests, one retry for a transient metadata transport error, 256 MiB aggregate metadata wire bodies and decoded bodies, bounded per-response expansion, 300-second resolver watchdog. No `--no-deps`, dependency override, alternate CPU index or macOS tag fallback is used.

Resolution attempts 01/02 failed as documented; attempt 03 completed. These consumed 3,165,719 + 10,349,639 + 10,417,549 metadata body bytes. All are retained and counted. The source hash for each invocation is preserved externally; the final published classifier additionally marks unresolved custom LicenseRefs UNKNOWN. The resolver behavior and target selection are unchanged by that stricter label review.

If the guard detects an artifact request, stop and report it. Never remove the guard, allow whole-wheel fallback or switch sources silently. A missing sidecar is not permission to fetch a wheel.

## Inventory, licenses and pinned model metadata

```sh
.venv/bin/python evaluation/experiments/006b/runs/2026-11-09-linux-preflight/inventory.py \
  --resolution "$UE_PREFLIGHT_RAW/resolver/resolution.json" \
  --output "$UE_PREFLIGHT_RAW/inventory"
.venv/bin/python evaluation/experiments/006b/runs/2026-11-09-linux-preflight/inventory.py \
  --output "$UE_PREFLIGHT_RAW/model"
```

The first command validates version-specific artifact identity/size/hash against the index, records selected Linux tags/licenses and independently follows active Linux/CPython 3.11 requirements and extras. The second compares the fixed Experiment006 inventory against the exact pinned Hugging Face API and only README/config/preprocessor contents. Weight URLs and alternate revisions are forbidden; weight hashes are checked as LFS metadata, not as fetched content.

Retain raw metadata and logs outside Git; commit only the versioned inventories, response hashes/URLs, redacted commands and reports. Preserve prior setup consumption and metadata reservations before adding all new reads and projected future wheel/model/runtime/cache/temp costs. Null unpacked/installed values stay UNKNOWN. A declaration is not complete license clearance.

## Validation and stop

```sh
UV_CACHE_DIR="$UE_PREFLIGHT_RAW/test-cache" uv run --frozen --offline pytest
```

Observed result: 304 passed in 7.97s, exit 0, zero stderr. The existing environment was used without research dependency reinstall. Check all 218 original tracked file hashes and unchanged Colima configuration/context afterward. No extra Docker images, candidate installation, smoke test, OCR, model import, model-weight request or PDF benchmark is part of this replay.
