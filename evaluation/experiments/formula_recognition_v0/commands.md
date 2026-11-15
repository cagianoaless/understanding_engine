# Reproduction of this blocked run

All commands run from the repository root. No command below acquires weights,
installs a dependency, starts Colima or executes inference.

```sh
git status --short
git rev-parse HEAD
df -k /System/Volumes/Data
colima -p ue006b status
docker context show
```

The raw evidence package keeps command exit statuses, original output, registered
storage roots/private paths, source-only review render and the exact upstream
source/config documents. Public SHA256/Git blob manifests bind that evidence.
Official Docling source is pinned to
`0fa0918d16de7769d942f9b06ca18cb673cbbc2e`; model metadata is pinned to
`ecedbe111d15c2dc60bfd4a823cbe80127b58af4`. A mutable `main` response must not
replace this inventory in a continuation. No API received a PDF.

Reproduce the captured resource decision into a **new external destination**:

```sh
export UE_FORMULA_OUT="$(mktemp -d /private/tmp/understanding-engine-formula-check-XXXXXX)"
"$UE_PYTHON" -B -m evaluation.experiments.formula_recognition_v0.preflight \
  --snapshot evaluation/experiments/formula_recognition_v0/storage-final.json \
  --inventory evaluation/experiments/formula_recognition_v0/model-inventory.json \
  --out "$UE_FORMULA_OUT/resources.json"
```

`UE_PYTHON` is the existing compatible CPython 3.11.13 interpreter. This replays
historical captured numbers, **not a fresh resource measurement**. Recheck disk
and registered allocations before any future acquisition. The helper never grants
inference permission from a fitting projection; unknown current runtime/storage
gates remain unknown. SHA256-null metadata entries stay explicit and cannot be
treated as verified payloads. No automatic resource cleanup is provided.

The allocation snapshot reused the unchanged function `allocation_snapshot` in
`evaluation/experiments/006b/runs/2026-11-09-cpu-archive-audit/archive_audit.py`,
with the prior Stage-D roots and additional retained evidence roots. Its private
root mapping is outside Git. Guest layer bytes are already in the host sparse disk;
do not add guest `du` again to the physical-host total.

Normal CI suite: `uv run --frozen --offline pytest`. For the existing broken host
launcher, reuse the already-installed interpreter/packages without repairing it:

```sh
export PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages"
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$UE_FORMULA_OUT/test-cache" \
uv run --frozen --offline --no-project --python "$UE_PYTHON" \
  "$UE_PYTHON" -B -m pytest -q
```

`--frozen` has no effect with `--no-project`; this host invocation performs no sync,
resolution or installation. CI uses the unchanged normal locked environment.
Existing loopback HTTP regressions need local socket access.

No inference command is published as tested: the candidate worker and component
scorer were not implemented/executed after the resource stop. Do not interpret
the frozen plan or static crop API evidence as a runnable, validated model test.
