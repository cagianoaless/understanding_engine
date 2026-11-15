# Offline reproduction

Run from the repository root. No dependency installation or source extraction is
needed: reuse the three registered original PDFs and hash-verified existing caches.
`input-manifest.json` records the exact identities/lengths; the local evidence
package supplies machine-specific paths and an exact command outside Git.

Set `UE_PYTHON` to the existing compatible CPython 3.11.13, and `UE_NATIVE_INPUTS`
to a local JSON with this shape (absolute paths only; hashes are checked against
the committed manifest, not accepted from this local file):

```json
{
  "documents": [
    {"id":"log2026","pdf":"/absolute/LOG2026_arxiv_final_preview.pdf","source":"/absolute/retained-log-extraction.json"},
    {"id":"attention","pdf":"/absolute/1706.03762v7.pdf","source":"/absolute/attention-extraction.json"},
    {"id":"tabpfn_nature_2025","pdf":"/absolute/s41586-024-08328-6.pdf","source":"/absolute/tabpfn_nature_2025-extraction.json"}
  ],
  "retained_svg_rules":{"path":"/absolute/PR21/analysis-reviewed/predictions.json"}
}
```

Do not substitute another manuscript or arXiv/publisher revision. The LoG source
is the final-preview file explicitly approved in PR #21; the absent clean-preview
revision is not used. Retained SVG evidence must match the existing PR #21 artifact
hash; no CloudConvert API or new SVG is involved.

```sh
export PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages"
export UE_NATIVE_RUN="$(mktemp -d /private/tmp/understanding-engine-native-reproduction-XXXXXX)"
"$UE_PYTHON" -B -m evaluation.experiments.native_pdf_math_evidence_v0.run \
  --inputs "$UE_NATIVE_INPUTS" --out "$UE_NATIVE_RUN/run-001" \
  >"$UE_NATIVE_RUN/run-001.stdout.log" 2>"$UE_NATIVE_RUN/run-001.stderr.log"
"$UE_PYTHON" -B -m evaluation.experiments.native_pdf_math_evidence_v0.run \
  --inputs "$UE_NATIVE_INPUTS" --out "$UE_NATIVE_RUN/run-002" \
  >"$UE_NATIVE_RUN/run-002.stdout.log" 2>"$UE_NATIVE_RUN/run-002.stderr.log"
```

Each output directory must be new and outside Git. Never overwrite historical
results. Compare `predictions.json`, both result files and the six native/glyph
sidecars between runs; timing files intentionally differ. The runner hashes parent
algorithm/scorer/reference/configuration files and the new frozen selection.
Source contracts and every selected-page character are checked against the original
PDF. Font diagnostics are separate and never fed to reconstruction. Predictions
are written before the reference component file is opened.

To export only small selected equation evidence and a visual review sheet:

```sh
"$UE_PYTHON" -B -m evaluation.experiments.native_pdf_math_evidence_v0.evidence \
  --run "$UE_NATIVE_RUN/run-001" --out "$UE_NATIVE_RUN/export"
"$UE_PYTHON" -B -m evaluation.experiments.native_pdf_math_evidence_v0.review \
  --inputs "$UE_NATIVE_INPUTS" --predictions "$UE_NATIVE_RUN/run-001/predictions.json" \
  --out "$UE_NATIVE_RUN/review"
```

The review uses the existing PDFium renderer and original embedded PDF fonts.
Do not commit full PDFs, caches, full page sidecars, private paths or raw predictions.
Committed references/results are provisional agent checks, not human ground truth.
Reproduction does not overwrite those committed artifacts.

Normal project/CI tests: `uv run --frozen --offline pytest`. On the measured host,
the project launcher remains broken and unrepaired; use the existing interpreter
with the installed locked packages read-only:

```sh
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$UE_NATIVE_RUN/test-cache" \
uv run --frozen --offline --no-project --python "$UE_PYTHON" \
  "$UE_PYTHON" -B -m pytest -q
```

uv warns that `--frozen` has no effect with `--no-project`; this invocation never
syncs/reinstalls packages. The unchanged CI workflow uses its normal locked Python
3.11.13 environment. Existing loopback HTTP tests require local socket access.
