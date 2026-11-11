# Local PDF Viewer v0

An offline inspection tool over **unchanged Source Selection v0**. It renders an
explicitly supplied original PDF, discovers every candidate at a click, and lets
the reader inspect a region using explicit geometric or native membership. It
does not parse the paper again, run Docling, explain mathematics or resolve order.

## Start the retained BERT demonstration

From the repository root, set `UE_VIEWER_PYTHON`, `UE_VIEWER_PDF`,
`UE_VIEWER_EXTRACTION` and `UE_VIEWER_HYBRID` to explicit absolute paths for the
existing compatible CPython 3.11 interpreter and retained BERT inputs. The local
evidence package includes an executable command with those machine-specific
values; they are deliberately kept out of Git. Reuse existing locked
site-packages (no installation, broken `.venv` launcher left untouched):

```sh
PYTHONPATH="$PWD/src:$PWD/.venv/lib/python3.11/site-packages" \
  "$UE_VIEWER_PYTHON" -B \
  -m understanding_engine.viewer \
  --pdf "$UE_VIEWER_PDF" \
  --extraction "$UE_VIEWER_EXTRACTION" \
  --hybrid "$UE_VIEWER_HYBRID" \
  --manifest evaluation/local_pdf_viewer_v0/bert-inputs.json --page 6
```

Use the **previously registered local evidence**, not newly parsed substitutes;
hashes/lengths must match the manifest. No private paths are embedded in the
Python API, UI or returned metadata. On a
working conventional project environment the equivalent prefix is
`uv run --frozen --offline python -m understanding_engine.viewer`.

Open the `http://127.0.0.1:<port>/#token=...` URL printed in the terminal. Keep it
private. The port defaults to an OS-assigned free port (`--port` can fix it);
there is no external bind option. Ctrl-C stops this server. Initialization runs
in the background with a visible loading message; first rendering takes about
16 seconds for this retained evidence on the measured Mac. Reopening/reloading
requires the original session URL because the fragment is removed immediately
and the token is kept in page memory only.

Click the page to see all hit original units and structural candidates. Yellow
boxes mark units; blue dashed/orange boxes distinguish Structure/Docling.
Expand a candidate to inspect its region or native membership explicitly.
Unicode/source IDs and hierarchy/order metadata are collapsible. Large character
lists display 20 then another 50 per action; candidate lists display 12 then
another 20. All matching outlines and the complete compact JSON remain available;
progressive display never truncates the result. Navigate all 16 BERT pages;
only page 6 has retained layout evidence, and others work with original source
characters alone. Point discovery does not snap to a word or pick a winner.

## Context and routes

`DocumentContext` verifies PDF/extraction/hybrid SHA256 and exact lengths, reads
the two JSON documents once, constructs one `SelectionIndex`, then retains the
immutable evidence. Input file size limits are 64 MiB PDF/128 MiB each JSON;
symlink final input components and non-regular files are refused. Page count and
PDF/source identity must agree. A two-page LRU caches rasters. A context lock
serializes PDFium rendering and index use; concurrent clients cannot mutate it.
No extraction or inference is reachable through HTTP.

| Route | Read-only result |
| --- | --- |
| `GET /` and four fixed asset paths | Embedded HTML/CSS/JS/SVG only |
| `GET /api/status` | Loading/failure or compact document/page metadata |
| `GET /api/page/N` | Validated geometry and raster identity |
| `GET /api/page/N/image` | Locally rendered original PNG |
| `POST /api/click` | Verified image/display transform → existing point selection |
| `POST /api/select` | Source Selection query → unchanged SelectionResult |

`POST` means submitting a read-only query, not writing data. Both selection
routes bind requests to PDF SHA256 and source canonical SHA256; click additionally
binds the page, raster SHA256 and natural pixel dimensions. The browser receives
**no full hybrid, complete extraction, original PDF download or local paths**.
The input-manifest format is `local-viewer-inputs.1`; SelectionResult keeps its
existing 0.1.0 contract. This is a local prototype, not a production API server.

All data routes require a constant-time checked 256-bit Bearer session token.
Host must be exactly the bound numeric loopback address/port; explicit foreign
origins and cross-site/same-site fetches are denied. Query POST requires the exact
same Origin. No CORS permission, credentials, cookies, telemetry or persistence.
CSP allows only local assets/connects and local blob images, denies embedding and
inline scripts. Fixed route dispatch has no file-browser root/path parameter;
unknown routes and query strings fail. Requests are limited to 16 KiB JSON,
responses to 4 MiB (explicit error, **no partial success**), 16 concurrent handlers,
five-second socket timeout, eight million render pixels. These are safeguards,
not a claim of exhaustive security testing or protection from same-user malware.

## Explicit mapping and renderer restrictions

Reuse existing PDFium 5.14.0 through `pypdfium2`; there is no added dependency or
PDF.js. Render scale is 1.5, additional rotation 0, forms/annotations disabled.
Before rendering, reuse Hybrid's strict native frame: origin zero, rotation and
raw rotation zero, UserUnit 1, complete equal media/crop/layout boxes. Cropped,
rotated or otherwise ambiguous pages are disabled/rejected, never guessed.

PDFium's installed size/box getters use IEEE754 `float32`. BERT's authoritative
595.276 × 841.89 points appears as 595.2760009765625 × 841.8900146484375 in those
getters. Accept **only the exact original value or its exact float32 cast**;
this is explicit backend numeric representation, not a generic geometry tolerance.
Original source dimensions/boxes remain untouched. Revalidate the actual PDFium
size, crop, media, bounding box and rotation before producing a raster.

Let the image's actual natural pixels be `(Iw,Ih)`, the actual displayed
`getBoundingClientRect()` be `(L,T,Dw,Dh)`, original page dimensions `(W,H)`,
and the pointer be `(clientX,clientY)` in the same CSS pixel frame:

```text
rx = (clientX - L) * Iw / Dw;   ry = (clientY - T) * Ih / Dh
pdfX = rx * W / Iw;            pdfY = ry * H / Ih
```

JavaScript and Python independently compute this transform and compare results.
The raster dimensions must equal the verified render; no nominal render scale,
device pixel ratio, guessed viewport offset or inferred zoom is substituted.
The image has no border/padding/rotation/object-fit; application zoom changes its
CSS width and the actual rectangle is reread on every click. Scroll offsets are
already represented by that rectangle. SVG uses the original `(W,H)` viewBox,
`preserveAspectRatio="none"` and the same actual displayed width/height, allowing
independent x/y raster rounding. Inclusive source boundaries remain unchanged.
OS/browser event pixel quantization can make a dispatched center differ slightly
from the mathematical center; every measured click still hit the original ID.

## Validation and limitations

[Measured smoke-test record](../evaluation/local_pdf_viewer_v0/report.md) includes
real browser events, source identity checks, response sizes, timings and visual
inspection. Offline tests cover transform round trips, known original centers,
scaled highlights, nested overlaps/empty model-text formulas, zero-glyph raster
objects, source-only fallback, stale/wrong identities, unsupported geometry,
traversal, Origin/Host/token rules and once-per-context initialization.

Only desktop headless Chromium was exercised, at DPR 1 and app zoom fit/75/150;
Safari/Firefox, OS display scaling, browser-level zoom and mobile/touch are
unverified. DOMRect mapping supports CSS scaling; this is not a general affine
viewport transform. Rendering PDF annotations/forms or arbitrary crop/rotation,
drag-to-select, text search, word expansion, keyboard PDF selection and lazy
document streaming are deferred. Initial JSON loading/validation remains costly
and memory proportional to the full retained evidence. Two pages/one real paper
are UI observations, not document-scale performance or quality validation.

Predicted labels and geometric links remain fallible. Nested table/text evidence,
cross-column multi-box order, empty model-text formulas and unmapped source glyphs
are exposed without correction; formula labels are not LaTeX transcriptions.
All frozen references remain `agent_visual_checked`; no human verification or
new benchmark result is claimed. Next: independent usability/coordinate checks on
explicitly selected additional layouts before broader viewer integration.
