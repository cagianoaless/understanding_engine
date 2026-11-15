# Reproduction (offline; existing packages only)

Run from the repository root on the dedicated experiment branch. The actual
machine-specific commands/paths are retained outside Git in the local evidence
package. Set explicit paths; do not discover/substitute other revisions:

```sh
export UE_PYTHON=/absolute/path/to/existing/python3.11
export UE_PDF=/absolute/path/to/LOG2026_arxiv_final_preview.pdf
export UE_ZIP='/absolute/path/to/LOG2026_arxiv_final_preview-1,LOG2026_arxiv_final_preview-2,LOG2026_arxiv_final_preview-3.zip'
export UE_BROWSER='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'
export UE_RUN="$(mktemp -d /private/tmp/understanding-engine-svg-reproduction-XXXXXX)"
export PYTHONPATH="$PWD:$PWD/src:$PWD/.venv/lib/python3.11/site-packages"
```

The PDF filename differs from the original request. The user explicitly approved
the discovered **final_preview.pdf**. `source_clean_preview.pdf` is absent; no
comparison against that other revision was performed. Stop on hash mismatch.
No CloudConvert request, upload, font/model download, OCR or inference is involved.

## Original character extraction / reuse

Reuse the retained `extraction.json` only after checking its file SHA256 against
`input-manifest.json`, its PDF identity and parser/settings provenance. The runner
validates its contract and verifies target characters directly against PDFplumber.
Alternatively regenerate this isolated extraction with the unchanged parser:

```sh
"$UE_PYTHON" -B - <<'PY' >"$UE_RUN/extraction.stdout.log" 2>"$UE_RUN/extraction.stderr.log"
import hashlib, os
from pathlib import Path
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.contracts import json_bytes
pdf, archive = Path(os.environ['UE_PDF']), Path(os.environ['UE_ZIP'])
assert hashlib.sha256(pdf.read_bytes()).hexdigest() == 'ad6d6d00a432f2f7e2e3b1c77a5e4ef80ecf2080300713d1c680de1f3fd79060'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'ae089bf6db882d2f023fb0d6386ebd412a4d3f4705bd781f3d0df3f9ea0b4f8d'
out = Path(os.environ['UE_RUN'])/'extraction.json'
assert not out.exists()
out.write_bytes(json_bytes(extract_pdf(pdf)))
PY
```

This is deterministic PDF extraction, not inference. Preserve its warnings;
do not repair fonts, geometry or text. Full extracted paper text stays external.

## Reconstruct, then evaluate

The reference and heuristic configuration are frozen in `freeze.json`. Regions
carry only selected boxes and explicit, hash-bound comparability approval. No
reference labels enter `reconstruct.build`. The runner saves/hashes predictions
**before loading the component reference**. Unapproved or mismatched regions are
rejected/unscoreable; all reference denominators remain present.

```sh
"$UE_PYTHON" -B -m evaluation.experiments.svg_math_feasibility.experiment \
  --pdf "$UE_PDF" --zip "$UE_ZIP" --source "$UE_RUN/extraction.json" \
  --regions evaluation/experiments/svg_math_feasibility/regions.json \
  --reference evaluation/experiments/svg_math_feasibility/reference.json \
  --out "$UE_RUN/analysis" \
  --pdf-sha256 ad6d6d00a432f2f7e2e3b1c77a5e4ef80ecf2080300713d1c680de1f3fd79060 \
  --zip-sha256 ae089bf6db882d2f023fb0d6386ebd412a4d3f4705bd781f3d0df3f9ea0b4f8d \
  >"$UE_RUN/analysis.stdout.log" 2>"$UE_RUN/analysis.stderr.log"
```

No archive member is extracted to a filesystem path. Expanded XML and source data
are retained only as external experimental evidence. The runner refuses an
existing output directory. It does not have a cleanup/retry/download mechanism.

## Actual SVG rendering / small figures

The optional visual check uses an **existing** Chromium-compatible browser and
Node >=22's built-in WebSocket. Neither is a new project dependency. It launches
only its own isolated profile, keeps the browser sandbox enabled, blocks network
assets/font acquisition with CSP and name resolution, records actual fallback
fonts/glyph extents and closes its own browser. The plugin execution tool was not
exposed in the recorded session, so this standalone fallback was used.
Only the validated flat text/path page 4 is rendered; complex other pages are not
silently treated as safe or geometrically interpreted.

```sh
"$UE_PYTHON" -B - <<'PY'
import os, json, base64
from pathlib import Path
from evaluation.experiments.svg_math_feasibility.svg_inspector import read_archive, inspect
member = read_archive(Path(os.environ['UE_ZIP']))[3]
page = inspect(member['root'])
out = Path(os.environ['UE_RUN'])/'render-input.local.json'
assert not out.exists()
out.write_text(json.dumps(dict(safety_checked=True, tags=list(page['statistics']['tags']),
                              svg_base64=base64.b64encode(member['payload']).decode())))
PY
node evaluation/experiments/svg_math_feasibility/render_svg.mjs \
  "$UE_BROWSER" "$UE_RUN/render-input.local.json" "$UE_RUN/browser-render"
"$UE_PYTHON" -B -m evaluation.experiments.svg_math_feasibility.figures \
  --pdf "$UE_PDF" --source "$UE_RUN/extraction.json" \
  --predictions "$UE_RUN/analysis/predictions.json" \
  --svg-render "$UE_RUN/browser-render" --out "$UE_RUN/figures"
```

Rendering is platform/font dependent; geometry/Unicode inspection is independent
of those browser font metrics. Reproduction may show other fallback faces. Pixel
accuracy is deliberately null, not a promised cross-platform screenshot hash.

## Native font diagnostic and small evidence export

This reads bounded, static Type1 header encodings and existing PDF CMaps; it does
not execute PostScript or change extraction/Unicode/candidate predictions:

```sh
"$UE_PYTHON" -B -m evaluation.experiments.svg_math_feasibility.font_evidence \
  --pdf "$UE_PDF" --source "$UE_RUN/extraction.json" --out "$UE_RUN/font-evidence.json"
"$UE_PYTHON" -B -m evaluation.experiments.svg_math_feasibility.publish \
  --run "$UE_RUN/analysis" --source "$UE_RUN/extraction.json" \
  --svg-render "$UE_RUN/browser-render" --font-evidence "$UE_RUN/font-evidence.json" \
  --reference evaluation/experiments/svg_math_feasibility/reference.json \
  --figures "$UE_RUN/figures" --out "$UE_RUN/public-evidence"
```

The export contains only selected equation evidence, inventory/statistics and two
small figures. Do not copy the original PDF, archive, full SVGs, page rasters,
full extraction or raw predictions into Git. Do not overwrite committed results
when reproducing; compare new external hashes/relation sets explicitly.

## Tests and local environment caveat

Normal project/CI command: `uv run --frozen --offline pytest`.
On the measured host the existing `.venv` launcher remains broken and untouched;
the intact installed CPython 3.11.13 and existing locked site-packages were reused:

```sh
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$UE_RUN/test-cache" \
uv run --frozen --offline --no-project --python "$UE_PYTHON" \
  "$UE_PYTHON" -B -m pytest -q
```

uv warns that `--frozen` has no effect with `--no-project`; this invocation never
syncs/installs dependencies. The unchanged CI workflow independently uses its normal
locked environment. Only existing loopback HTTP tests require local socket access.
