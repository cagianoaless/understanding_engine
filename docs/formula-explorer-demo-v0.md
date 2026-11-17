# Formula Explorer Demo v0

An explicit opt-in extension of the existing offline viewer. It connects a verified original PDF/extraction/hybrid to **one identity-bound, frozen Formula Structure v0 graph**. There is no new recognition, PDF extraction, model installation, mathematical explanation or semantic AST. The default viewer remains source-selection-only.

## Start on the Mac

The observed Attention original/extraction and optional LoG original/extraction are available and verified. No matching hybrid was retained for these documents. This demonstration derives a **source-only hybrid** via the unchanged `build_hybrid(source, [])`, without creating layout predictions or changing source characters. These new bulk files and machine-specific launchers live outside Git.

If a matching hybrid is already available, reuse it with its own existing viewer identity manifest. Do not substitute a BERT hybrid or any other PDF revision. Graph/PDF mismatch fails initialization.

From the repository root, provide explicit paths to the registered original Attention PDF, retained extraction and compatible Python3.11 interpreter. Choose a fresh external output directory:

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
  "$PYTHON" -B evaluation/formula_explorer_v0/prepare.py \
  --pdf "$ATTENTION_PDF" --extraction "$ATTENTION_EXTRACTION" \
  --graph evaluation/experiments/formula_structure_v0/examples/attn_fraction.json \
  --identity evaluation/formula_explorer_v0/attention-source-inputs.json \
  --output "$NEW_EXTERNAL_BUNDLE"
```

Preparation verifies every supplied byte identity, validates the frozen graph, builds the explicitly source-only hybrid, and publishes the complete bundle atomically. It neither reparses the real PDF nor fabricates layout/model predictions. Existing output directories are refused.

```sh
PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
  "$PYTHON" -B -m understanding_engine.viewer \
  --pdf "$ATTENTION_PDF" --extraction "$ATTENTION_EXTRACTION" \
  --hybrid "$NEW_EXTERNAL_BUNDLE/source-only-hybrid.json" \
  --manifest "$NEW_EXTERNAL_BUNDLE/viewer-manifest.json" \
  --formula-demo \
  --formula-graph evaluation/experiments/formula_structure_v0/examples/attn_fraction.json \
  --formula-manifest "$NEW_EXTERNAL_BUNDLE/formula-manifest.json"
```

Open the private `http://127.0.0.1:<port>/#token=...` URL printed by the server. The token is removed from the address bar and retained only in memory; use the original session URL after reload. Ctrl-C stops this server. No Node/build tooling is required for ordinary use. The observed Mac uses the already retained compatible CPython3.11.13 plus existing project packages; its broken `.venv` launcher is not repaired. A working standard environment may instead prefix the command with `uv run --frozen --offline python`.

In demo mode, omitting `--page` starts the verified graph's page (4 for both examples). Outside demo mode the old default remains page6. `--formula-demo`, `--formula-graph` and `--formula-manifest` must be supplied together. The two manifest formats remain separate: `local-viewer-inputs.1` for document inputs and `local-formula-demo-inputs.1` for exact graph bytes/hash. Local launch.local.json files and ready-to-run shell launchers for this Mac are retained in the external evidence directory identified by the final report.

## Interaction

1. Click the outlined whole formula crop or **Go to formula**.
2. Inspect the exact frozen cleaned LaTeX; original raw output is in a separate disclosure.
3. Expand structural nodes with their disclosure arrows, or use **Expand all** / **Collapse all**.
4. Select **Numerator** or **Denominator**. Its exact model-LaTeX substring is marked, with stored code-point/token spans, node type/status, child roles and diagnostics.
5. **Return to PDF crop** scrolls back to the original whole region. **Reset selection** clears the active syntax/selection and restores ordinary source inspection; the inactive crop outline remains available.

The graph's global parsing/acceptance state and unverified provenance are separate from a node's syntactic support. Source Selection's original-character text remains in its existing lower panel. A source-only page badge describes the absence of Hybrid layout predictions, not absence of the separately supplied frozen formula graph.

**The PDF box never follows an individual node.** When the formula is active, only the original whole-crop box is drawn: selecting a denominator changes the HTML LaTeX mark and node details, not PDF geometry. No symbol boxes, PDF character links, function meaning or source verification are invented. Original source-unit overlays resume outside the formula selection/reset workflow.

Python spans count Unicode code points. The frontend uses `Array.from(text)` before slicing, checks the result against the backend's exact substring, and uses only text nodes/textContent. It does not apply UTF-16 indices directly, inject LaTeX as HTML, run a TeX engine or load MathJax/CDNs.

## Rejected LoG example

Use the exact registered LoG PDF/extraction, `log_eq2.json`, `log2026-source-inputs.json`, and a **different fresh external bundle** with the same preparation command. Launch with those explicit PDF/extraction/hybrid/manifests and the LoG graph. It is a separate document context, not a generic file browser or silent document switch.

The UI says **REJECTED AS A COMPLETE FORMULA; parsed fragments only**. Selecting the unresolved root or retained fragments never removes that overall rejection. Repetitive prose/incomplete model text remains unchanged. No parser grammar or prediction was repaired.

## Security and boundaries

The original numeric-loopback bind, constant-time bearer authorization, exact Host/origin checks, no-CORS behavior, CSP and bounded requests/responses are retained. New read-only routes are available only in opt-in mode:

- `GET /api/formula`: one already verified graph plus explicit crop-only provenance.
- `POST /api/formula/node`: a known node in that graph, bound to PDF/source/formula identities, with exact substring and stored token evidence.

No request accepts a local path; there is no PDF/model/file upload or arbitrary file-serving endpoint. Graph input is limited to1MiB and2,048 nodes; larger inputs fail explicitly. Unknown nodes, altered graph bytes/spans, stale identities, absent pages and unsupported crop/rotation/UserUnit frames are rejected. The actual PDF page frame is verified at initialization and rendering using existing geometry utilities. Graph/source/index validation occurs once per context, not per click. Source Selection, Hybrid and Formula Structure contracts are unchanged.

Caller-provided graph identity/provenance is recorded and checked for consistency, not independently certified as mathematical truth. Token spans provide model-text provenance, not one-to-one PDF glyph alignment. Only one frozen example is supported per context in v0.

## Verification

See `evaluation/formula_explorer_v0/report.md`, actual screenshots and browser evidence. Real Attention and LoG browser tests used an existing Brave/Chromium-compatible executable with an isolated temporary profile; the Browser plugin execution tool was unavailable. Node's existing CDP/WebSocket harness is test-only. No browser/package/model was installed. Human manual interaction remains unexecuted; agent screenshot inspection and automated browser assertions are reported separately.
