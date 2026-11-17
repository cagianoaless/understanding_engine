# Recorded execution and reproduction

Use the repository root and existing compatible Python3.11/project packages. Registered input identities are in attention-source-inputs.json and log2026-source-inputs.json. Exact machine-specific file paths and ready-to-run launchers are stored in the external evidence directory, not Git. No PDF/model/browser acquisition or dependency synchronization is needed.

1. Verify the original PDF, retained extraction and frozen graph by exact bytes/SHA-256. The observed paths came from the existing native-math input registry. The two original PNG crop hashes, CodeFormula artifact/canonical-record hashes and exact raw/cleaned strings were checked as well. Do not substitute another paper/revision or repair the graph.
2. Prepare a NEW external source-only bundle with prepare.py, as documented in [the launch guide](../../docs/formula-explorer-demo-v0.md). This reuses `build_hybrid(source, [])` and the existing atomic publisher; it does not invoke PDF extraction or recognition. Source-only hybrid SHA-256 values and sizes are in the public viewer/preparation manifests.
3. Start the explicit opt-in viewer with the verified PDF/extraction/hybrid/manifest, --formula-demo, --formula-graph and --formula-manifest. With no explicit --page, demo mode starts page4 from the graph; original mode still defaults to page6. Keep the printed session URL private.
4. For a reproducible automated check using an **already installed** Chromium-compatible browser and Node22+:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
node evaluation/formula_explorer_v0/browser_smoke.mjs \
  --browser "$EXISTING_BROWSER" --python "$PYTHON" \
  --launch "$EXTERNAL_BUNDLE/launch.local.json" \
  --work "$NEW_EXTERNAL_BROWSER_RUN"
```

The observed browser was the existing Brave executable, reporting Chrome146.0.7680.164 through CDP; Node24.2.0 was already installed. The Browser skill was read and its JavaScript execution tool was searched for, but it was not exposed. The fallback reuses the earlier local-viewer CDP approach, with an owned temporary profile, no personal profile access, no browser sandbox disabling, background integrations disabled and hostname resolution restricted to loopback. No package/browser/model installation occurred.

The harness starts its own loopback viewer, sees the actual PDF image, dispatches real pointer clicks, expands the fraction and verifies child highlights against the unchanged graph. It checks exact whole-crop SVG coordinates/rectangle count throughout navigation, original model text, child roles/diagnostics, rejection/uncertainty labels, return/reset and a synthetic non-BMP helper case in the actual browser. It records only normalized route metadata and never persists session tokens. Browser/server processes owned by the harness are closed; personal processes remain untouched. The two final runs have separate profiles/servers/evidence and both exit0.

The previous first-pass browser records/screenshots are retained externally; final evidence uses browser-attention-final and browser-log-final. Screenshots committed here are unmodified browser captures, not generated illustrations. The agent visually inspected the final Attention and LoG captures; independent human interaction/review remains unexecuted.

5. Run all offline tests with the retained interpreter and existing packages, leaving the broken host .venv launcher unchanged:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$EXTERNAL_TEST_CACHE" \
uv run --frozen --offline --no-project --python "$PYTHON" \
  "$PYTHON" -B -m pytest -q
```

`--frozen` does not synchronize with --no-project; no host installation is performed. The unchanged GitHub workflow independently runs the conventional frozen offline suite. Unit fixtures are explicitly authored synthetic PDFs/model hypotheses, not fabricated benchmark evidence.

6. Preservation checks compare the original621 tracked byte hashes: only viewer.py and viewer_assets.py may change. Every prior experiment, graph, source contract, character ID/geometry definition and dependency lock remains unchanged. Recheck original external PDF/extraction/crop hashes after testing. Bulk data, private paths, logs and browser profiles remain external with hash manifests.
