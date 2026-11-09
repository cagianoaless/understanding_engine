# Reproduction and execution record

Parent: PR #13 `cff63071a1bc2762268be461e0b79579549b38c4`. This run uses the unchanged proposal at `../2026-11-09-cpu-packaging/archive-audit-proposal.json`, SHA-256 `81c9a936575a8376acb835c2d33949b81719e96dfbc1cf009b41cfae5026ff5e`. Its 103 artifacts total 379,580,121 expected bytes. No resolver, model API, new infrastructure test, image pull or package installation is involved.

`$REPO` denotes this checkout; `$ARCHIVE_RAW` is the newly created private temporary run directory **outside every Git ancestor**. The user's home can be a Git repository, so a sibling output directory under home is insufficient. All archives/notices/raw ZIP metadata remain outside Git; their original physical path is withheld from committed evidence. Root source URLs/hashes are public and committed.

## Environment and safeguards

- Existing `.venv/bin/python`: CPython **3.11.13**; no dependency installation. Audit uses Python standard library only. Existing uv **0.7.13**, pytest **8.4.2**; offline project dependencies and lock unchanged.
- Target remains Linux aarch64/Python 3.11; these are the previously resolved exact Linux wheel payloads, not macOS substitutes. Source versions/tags/edges were already checked in PR #13 and were not re-resolved.
- `storage-roots.json` is a host-specific raw file mapping the same labels in PR #13's `accounting.json` to their original runtime/cache/evidence roots, plus `$ARCHIVE_RAW`. Keep every original root, including prior metadata archives and installed Colima/Docker/Lima kegs. Do not move/clean them. Commit only measured/redacted labels in `resources.json`.
- Network access is limited to the exact allowlisted wheel URLs, sequential GETs, verified HTTPS, no proxy credentials, no redirects/retries/source substitutions. No Hugging Face or model URL is contacted. Each file is streamed to a fresh `.part`, length/SHA-256 checked, then renamed without copying.
- Before each request and during every <=1 MiB chunk: check available host space and allocations of all registered roots, including partials. Keep 20 GiB free and inclusive storage plus a 64 MiB work allowance <=4 GiB. Abort on mismatch/limit/timeout; do not broaden the scope. Socket timeout 30 s; overall stage timeout 1,200 s.
- Parse ZIP directories without full extraction. Read root wheel METADATA and candidate LICENSE/NOTICE/copyright texts only, <=2 MiB each and <=32 MiB total notice reads; retain deduplicated notice text under `notices/`. Source modules under e.g. `packaging/licenses/*.py` are excluded. No `sys.path` insertion, import, inference, sdist build or pip install.

## Actual commands

Commands below use redacted variables. The raw audit logs/source hashes/exit codes are preserved. The initial command used the initial inspector source captured as `archive_audit.initial.py` (hash in `execution.json`); the final checked-in source contains its documented correction.

```sh
git status --short --branch
git rev-parse HEAD
cat AGENTS.md
df -k /System/Volumes/Data
git switch -c feat/experiment-006b-wheel-audit
git -C "$ARCHIVE_RAW" rev-parse --show-toplevel  # Required to fail: outside Git.

UV_CACHE_DIR="$ARCHIVE_RAW/test-cache" /opt/homebrew/bin/uv run --frozen --offline \
  pytest tests/test_cpu_archive_audit.py -q

"$REPO/.venv/bin/python" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-09-cpu-archive-audit/archive_audit.py" \
  --raw "$ARCHIVE_RAW" --storage-roots "$ARCHIVE_RAW/storage-roots.json" \
  > "$ARCHIVE_RAW/acquisition.stdout.log" 2> "$ARCHIVE_RAW/acquisition.stderr.log"
```

Initial result: exit **3**, after **80 verified payloads**; `audit.json` records the inspector-only root/vendor METADATA identity error. There was no source/length/hash/resource failure. Preserve that result, resource samples and initial script unchanged. The final script restricts identity to the sole root `.dist-info/METADATA`; its new vendor regression passed. Then:

```sh
UV_CACHE_DIR="$ARCHIVE_RAW/test-cache" /opt/homebrew/bin/uv run --frozen --offline \
  pytest tests/test_cpu_archive_audit.py -q \
  > "$ARCHIVE_RAW/focused-after-fix.stdout.log" 2> "$ARCHIVE_RAW/focused-after-fix.stderr.log"

"$REPO/.venv/bin/python" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-09-cpu-archive-audit/archive_audit.py" \
  --raw "$ARCHIVE_RAW" --storage-roots "$ARCHIVE_RAW/storage-roots.json" \
  --continue-inspection-fix \
  > "$ARCHIVE_RAW/continuation.stdout.log" 2> "$ARCHIVE_RAW/continuation.stderr.log"

UV_CACHE_DIR="$ARCHIVE_RAW/test-cache" /opt/homebrew/bin/uv run --frozen --offline pytest \
  > "$ARCHIVE_RAW/pytest.stdout.log" 2> "$ARCHIVE_RAW/pytest.stderr.log"
```

Continuation: exit **0**; rehash/reinspect the 80 retained archives, download only the remaining 23. No payload GET repeats. Output: `continuation-audit.json` and `continuation-resource-samples.json`; the original result is not overwritten. Full offline suite: exit **0**, 324 passed in 7.98 s; focused corrected suite: 10 passed. Offline tests ran during part of the continuation; their external cache/evidence writes were included in the monitored roots. Acquisition timing is not a benchmark metric.

## Recompute sizes without downloads

For each verified archive, load its ZIP central directory (`zipfile.ZipFile(...).infolist()`), reject unsafe/duplicate member paths, symlinks/encryption, and sum non-directory `file_size`. Sum `ceil(file_size / 4096) * 4096` separately for the explicit file-allocation estimate. Compare per-package totals with `artifacts.json`; these sum to 1,250,768,241 logical and 1,318,440,960 rounded bytes. Do not extract all files or import the packages. Notice SHA-256 values are recoverable from the named wheel member; only bounded notice/root METADATA decompression occurred.

`archive_audit.py` exposes `allocation_snapshot(registered_roots)` and `check_limits(snapshot)` for the same bounded no-symlink-following measurement. It deduplicates real regular files by device/inode and sums `st_blocks * 512`; host availability comes from `statvfs('/System/Volumes/Data')`, cross-checked with `df -k /System/Volumes/Data`. Include current raw evidence, old runtime/cache roots and all `.part` files. VM disks already contain guest layers. Preserve APFS sharing/peak caveats.

Projection in `resources.json`: measured `H` + rounded `U` + frozen Heron `M` + explicit scratch/runtime/duplicate/work allowances `T/R/D/W`. Do not substitute compressed sizes for unpacked installation or treat the 512 MiB runtime allowance as measured. Archive-file allocation, payload length, guest file estimate and unknown actual installation peak are separate quantities.

## Re-execution boundary

The checked-in final inspector can reproduce a fresh acquisition in a new isolated directory **only with authorization for another download run and the same gates**. Never point it at old destinations or use the continuation flag to retry a failed payload: continuation requires a STOPPED identity-inspector failure with every previous download verified and no partial archive.

No command here authorizes a candidate installation, Heron weights, runtime image or inference. A **6 GiB storage proposal is not an active policy change**. Stop after this evidence; preserve all historical results and protected inputs.
