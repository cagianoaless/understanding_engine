# Reproduce the UI smoke check

Use the retained BERT files and existing interpreter described in
[`docs/local-pdf-viewer-v0.md`](../../docs/local-pdf-viewer-v0.md). Do not parse the
real PDF again or run inference. `bert-inputs.json` verifies every input byte.
`bert-anchors.json` identifies original source units/boxes, **not human labels**.

With an **already installed** Chromium-compatible executable and Node >=22:

```sh
PYTHONPATH="$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
node evaluation/local_pdf_viewer_v0/browser_smoke.mjs \
  --browser "$UE_VIEWER_BROWSER" --python "$UE_VIEWER_PYTHON" \
  --pdf "$UE_VIEWER_PDF" --extraction "$UE_VIEWER_EXTRACTION" \
  --hybrid "$UE_VIEWER_HYBRID" \
  --manifest evaluation/local_pdf_viewer_v0/bert-inputs.json \
  --anchors evaluation/local_pdf_viewer_v0/bert-anchors.json \
  --work "$UE_VIEWER_NEW_EXTERNAL_SMOKE_DIRECTORY"
```

`--work` must not exist and must be outside Git. The optional harness creates a
temporary isolated browser profile, an owned viewer subprocess, DevTools JSON
evidence and screenshots. It closes its own browser/server, never personal
processes. Existing browser security sandbox stays enabled; background integrations
are disabled and name resolution is restricted to loopback. Page requests must
stay on the local origin or its blobs. It requires permission for local sockets
and launching the existing browser. The plugin execution tool was unavailable in
the recorded session; this standalone fallback uses Node's built-in WebSocket,
not installed browser automation packages. **Node/browser are test tools only**;
the viewer needs neither at runtime beyond the user's browser.

Observed checks: visible initialization, actual PNG dimensions, session-fragment
removal, pointer dispatch at a known source center, original ID/Unicode, all
candidate outlines, actual SVG bounding rectangles, fit/75/150 scaling,
byte-equivalent repeated results, region inspection and progressive characters,
page-1 source-only selection, zero page errors/external page requests. Timings
include CDP and 100-ms polling; they are not pure backend query latencies.

The synthetic fixture has an authored two-line empty-model-text formula nested in
a table, plus a blue raster tile without glyphs. Generate only this new fixture:

```sh
PYTHONPATH="$PWD/src:$PWD/.venv/lib/python3.11/site-packages" "$UE_VIEWER_PYTHON" -B - <<'PY'
import json, os
from pathlib import Path
from evaluation.local_pdf_viewer_v0.fixtures import create
out = Path(os.environ['UE_VIEWER_NEW_EXTERNAL_FIXTURE_DIRECTORY'])
paths, manifest, source, hybrid = create(out)
page = source['pages'][0]
unit = page['characters'][0]
anchors = [dict(page=1, id=unit['id'], text=unit['text'], bbox=unit['bbox'],
                geometry=page['geometry']),
           dict(page=1, point=[150, 140], geometry=page['geometry'])]
(out/'anchors.json').write_text(json.dumps(anchors))
PY
```

Run the same harness with that directory's `authored.pdf`, `extraction.json`,
`hybrid.json`, `manifest.json` and `anchors.json`, using a new `--work` directory.
These hypotheses are authored fixtures; there is no model execution or accuracy
claim. Real BERT screenshots remain external because PDF redistribution rights
have not been established.

Full offline tests normally: `uv run --frozen --offline pytest`. In the measured
host's broken-launcher context, the exact no-install compatibility command was:

```sh
UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR="$UE_VIEWER_NEW_EXTERNAL_UV_CACHE" \
PYTHONPATH="$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
uv run --frozen --offline --no-project --python "$UE_VIEWER_PYTHON" \
  "$UE_VIEWER_PYTHON" -B -m pytest -q
```

uv reports that `--frozen` has no effect with `--no-project`; this invocation
executes the existing interpreter/packages read-only without syncing/installing.
The unchanged GitHub workflow independently uses the normal frozen environment.
No download/install is part of this local reproduction protocol.
