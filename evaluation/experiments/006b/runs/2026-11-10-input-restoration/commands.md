# Reproducible input verification and retrieval

This is an input-only run stacked on PR #15 (`9b0e329d294434dcbfe5699953aebd8f696703ea`). Preserve the authoritative registry/selection; do not run Docling, a runtime preflight, dependency/model acquisition or the benchmark.

## Offline verification of the restored input set

`$INPUT_ROOT` is the new private external directory; its exact absolute path is recorded locally in `input-remapping.complete.local.json`. `$REPO` is this checkout. `$EXISTING_PYTHON` is the already-installed intact host CPython **3.11.13**; project `.venv` packages, including **pypdf 6.1.1**, are read-only. The old `.venv` launcher was not repaired or synchronized.

```sh
PYTHONPATH="$REPO/.venv/lib/python3.11/site-packages" \
"$EXISTING_PYTHON" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-10-input-restoration/restore_inputs.py" \
  --verify-local "$INPUT_ROOT/input-remapping.complete.local.json"
```

Expected recorded result: `all_inputs_ready=true`, **3 verified documents**, **6 selected page pairs**, **0 inference invocations**. This re-reads bytes/hashes and page trees only; it does not download, render, extract text, modify sources or produce predictions. It refuses an incomplete accepted-document set. Scientific fields always come from the unchanged registry whose SHA-256 is hard-pinned in the helper.

## Targeted offline regression command

```sh
PYTHONPATH="$REPO/src:$REPO/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$RESTORATION_RAW/test-cache" \
uv run --offline --no-project --python "$EXISTING_PYTHON" \
  "$EXISTING_PYTHON" -B -m pytest tests/test_input_restoration.py -q
```

Actual result: **14 passed in 0.14 s**, zero failures/skips. No environment sync, interpreter download or research dependency reinstall. Only relevant verification tests were manually run; existing CI configuration remains unchanged.

## Actual retrieval sequence

Before retrieval: inspect AGENTS, clean HEAD and PR #15; create `feat/experiment-006b-restore-inputs`; snapshot all **323** previous tracked hashes. Check registered file/cache existence and exact-name candidates in known experiment artifact roots; bounded workspace filename search found no missing-original copies. Check `/Users/Shared` is outside Git. Create fresh external evidence under `/private/tmp` and append it to the unchanged existing allocated-root map. Resource guards use the already established **6 GiB inclusive / 20 GiB host reserve**, without Docker/Colima API calls.

The initial command used the saved initial source hash in external evidence:

```sh
PYTHONPATH="$REPO/.venv/lib/python3.11/site-packages" "$EXISTING_PYTHON" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-10-input-restoration/restore_inputs.py" \
  --raw "$RESTORATION_RAW" --input-parent /Users/Shared
```

It created one fresh mode-0700 persistent input root, verified/copied Attention, retrieved/verified BERT, and rejected Nature's 3,038-byte HTML response. Exit **3**, incomplete input mapping preserved. An ordinary publisher transport continuation (`--resume-publisher-html`) reused Attention/BERT without recopying; its second HTML response was also rejected, exit **3**. These are delivery failures, not accepted PDF mismatches or scientific source replacements.

A native standard-library bounded GET prefix inspection stopped at 65,537 bytes; the prefix was discarded and no complete hash/type was captured. Native HEAD then returned `application/pdf` with the exact expected length through the publisher's anonymous redirect flow. The following existing system client performed the successful full transfer, with exact length/hash guards and no page parsing:

```sh
/usr/bin/python3 -B -I -S \
  "$REPO/evaluation/experiments/006b/runs/2026-11-10-input-restoration/native_publisher_get.py" \
  --raw "$RESTORATION_RAW"
```

Observed transport: existing macOS **Python 3.9.6 / LibreSSL 2.8.3**, HTTP 200, exact 16,957,699 bytes and expected Nature SHA-256. No new software, credentials/cookie store or browser session was used. The canonical recorded URL starts the request; only HTTPS publisher-owned redirects are accepted. No server-rendered/re-exported alternative is requested.

Independent metadata acceptance then used the pinned existing Python and pypdf:

```sh
PYTHONPATH="$REPO/.venv/lib/python3.11/site-packages" "$EXISTING_PYTHON" -B \
  "$REPO/evaluation/experiments/006b/runs/2026-11-10-input-restoration/restore_inputs.py" \
  --raw "$RESTORATION_RAW" --accept-native
```

This rehashed the native partial, checked Nature's page tree, reverified the accepted Attention/BERT files, and renamed only the verified bytes to the original filename. It emitted `input-remapping.verified.local.json`. A final independent all-three verification emitted the canonical **`input-remapping.complete.local.json`**, retaining earlier mappings and attempt evidence; the complete mapping contains current identities/page counts and the final allocated-root snapshot. Both identity manifests pass `--verify-local`; the complete one is the explicit future location overlay.

Initial checks: byte-for-byte hash identity before page parsing; `PdfReader(..., strict=True)` page count plus selected `/Page` entries; no PDF modification or repair. File destinations are exclusive `.part` files until verified, original accepted paths are not overwritten, and wrong versions/hashes fail closed. Socket timeout is 45 s with an elapsed transfer bound of 180 s; exact expected-byte bounds and filesystem guards apply throughout. Rejected HTML/partial evidence is never accepted as a PDF.

Raw provenance, code snapshots, logs, exact local mappings and any opaque publisher query values remain outside Git. Public source URLs and hashes are in committed manifests; redirected query values are represented by names and exact URL hashes only. No PDF is committed. Final mapping changes file locations only; do not edit frozen registry identities/pages to point at a different document.

**Stop:** PDFs are ready; no inference, scoring, annotation change, baseline regeneration or six-page execution is authorized by these instructions. Another retrieval run requires a fresh destination and appropriate authorization; offline verification needs neither downloads nor runtime access.
