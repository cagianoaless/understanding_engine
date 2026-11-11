# Local PDF Viewer v0 — observed UI demonstration, 2026-11-11

**A usable local viewer over retained source evidence; no new model evaluation.**
Stacked on PR #19 / `5d91e49966f6acb43b04f9aabbb8e9d1f0a159c7`.
All 406 pre-existing tracked files were checked against their initial SHA256 and
remain byte-identical, including Selection/Hybrid/Structure contracts, dependencies,
CI configuration, historical experiments, annotations and held-out manifests.
The current user request explicitly authorizes this UI despite the older generic
AGENTS rule. No old rule/file was rewritten.

## Delivered

Standard-library HTTP server bound exclusively to numeric loopback, embedded plain
HTML/CSS/JS, existing PDFium renderer, one immutable document/SelectionIndex context,
background initialization, authenticated bounded routes, verified raster identities,
explicit client/server coordinate mapping and a two-page image cache. Page navigation,
app zoom, all-candidate outlines, original source-unit highlights, Unicode/IDs,
provider labels, association/hierarchy/order evidence and full compact JSON are
available. Table/region selection has an explicit native/geometric basis.

The UI labels structural predictions as hypotheses, exposes ambiguity and warns
that backend order is not verified reading order and formula labels are not LaTeX.
Large results expand progressively; nothing is silently truncated. An over-limit
request gets an explicit error, not a partial success. There is no file browser,
unrestricted filesystem endpoint, PDF parsing/inference endpoint or external asset.

[Architecture/startup](../../docs/local-pdf-viewer-v0.md) ·
[Reproduction commands](reproduce.md) · [Measurements](summary.json) ·
[Input identities](bert-inputs.json) · [External artifact hashes](artifacts.json).
The local evidence package provides a runnable `start-viewer.sh` with explicit
verified paths. Paths, original PDFs, rasters, screenshots and complete raw
SelectionResults remain outside Git.

## Retained source and renderer checks

BERT arXiv v2: 775,166 bytes, SHA256
`5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e`.
Complete retained extraction: 48,738,778 bytes, SHA256
`9618216d3b52fab8a59949eeacd3f740f78f7166964f9cae3d61ce68522ab79b`.
Retained Hybrid v0: 58,496,673 bytes, SHA256
`448464901ab56611dcbde6e8a2621ad17118508d0936415f06acc4408a2a7649`.
All were verified at startup, not reparsed/rebuilt. Sixteen source pages are
available; only page 6 contains retained Structure/Docling hypotheses.

Existing CPython 3.11.13, pdfplumber 0.11.8, pypdfium2 5.14.0 and Pillow 13.0.0
were reused without installation. PDFium rendered pages 6 and 1 at **893 × 1263**
pixels, scale 1.5, annotations/forms disabled. Original dimensions remain
595.276 × 841.89 PDF points. PDFium's float32 getter values are accepted only as
the exact float32 cast of those original values; page size, media/crop/bbox and
rotation are checked. Strict Hybrid geometry rules reject unsupported transforms.
No guessed crop/rotation/zoom or replacement source coordinates.

## Actual browser evidence

The Browser plugin's required execution tool was unavailable. The fallback used
the **already installed Brave/Chromium 146.0.7680.164**, headless, 1280 × 1000,
DPR 1, in a new isolated external profile with the browser sandbox enabled.
Node 24's built-in WebSocket drove real pointer events; no test packages were
installed and no personal browser session/state was used.

Observed and asserted against original source boxes/IDs:

- Initialization/loading was visible. BERT server startup to ready rendered page:
  **16.133 s**, including verification, reading, validation and rendering.
- At page 6's original `:p6:c0` unit (`S`), fit/75/150 app zoom returned that
  original ID and three matching regions: Structure paragraph, Docling table and
  nested text. Every candidate was outlined; no winner was selected implicitly.
- Actual SVG highlight bounds differed from their independently projected source
  boxes by at most **0.000022 CSS pixels** in the measured BERT cases. Dispatched
  pointer centers differed by at most **0.636 PDF points**, within one displayed
  pixel because browser MouseEvent coordinates are quantized. Synthetic mathematical
  round trips separately passed at 1e-12 PDF-point tolerance.
- Repeating the same pointer interaction produced identical SelectionResult data.
- The table's inspection button returned **345 original units / 118 regions**;
  first 20 then 70 unit entries were displayed on request, all outlines retained.
- Page navigation selected page 1's original `:p1:c0` (`B`) with **zero layout
  candidates**, explicit source-only state and a correctly rendered source page.
- A separate authored fixture exposed a nested table and two-line formula with
  empty diagnostic model text, while preserving original `x` glyphs. Clicking
  its raster tile returned zero units, an explicit textless visual object and
  the picture hypothesis. These are authored tests, not inferred paper labels.
- Zero browser page errors and zero external **page** requests were observed.
  This is not a claim that every OS/browser background process was network-audited.
  Each owned server exited 0 and its isolated browser was closed.

Screenshots of loading, both source pages, all zoom levels, table inspection and
the synthetic raster selection were retained externally. BERT fit/table screenshots
were visually inspected: the original page, source highlights, overlapping table/text
outlines, controls and selection panel were visible and aligned. BERT page images
are not committed without established redistribution permission.

| Interaction | Captured compact JSON UTF-8 | Observed interaction time |
| --- | ---: | ---: |
| BERT page 6 point, fit | 6,091 B | 106.195 ms |
| Same original point, 75% | 6,090 B | 105.062 ms |
| Same original point, 150% | 6,091 B | 104.847 ms |
| BERT page 1 source-only point | 2,557 B | 104.240 ms |
| Complete BERT table selection | 404,652 B | not separately measured |

Bytes are `JSON.stringify` of captured results; pretty-printed HTTP payloads are
larger. Times include CDP, UI work and 100-ms polling, **not isolated backend
latency**. The 58.5-MB full hybrid is neither serialized nor returned per click.
These few interactions do not establish full-document scalability.

## Tests, failures and unverified behavior

**488 tests passed, zero failures/skips, in 19.15 s**, including 36 new viewer
regressions. Exact environment/commands are in
`summary.json` and `reproduce.md`; logs are hashed in `artifacts.json`.
The existing compatible interpreter/project packages were used read-only; the
broken host launcher was not repaired. uv's documented no-project/frozen caveat
is recorded. The unchanged GitHub workflow independently tests its locked Python
3.11.13 environment; the PR exposes its exact-head CI result.

Development renderer probing initially attempted an unsupported PdfPage context
manager; the actual implementation uses explicit `finally` closure and subsequent
render/browser tests passed. No extraction, source, layout or model output was
repaired. There were no observed UI smoke failures in the final runs.

Unsupported crop/rotation/UserUnit pages fail safely. Safari/Firefox, browser-level
zoom/OS scaling, touch/mobile, keyboard selection, drag rectangles, PDF forms and
annotations remain unverified or deferred. Initial full JSON validation is costly;
memory still scales with retained evidence. A single local context is intended
for a trusted user's inspection, not remote/multi-tenant deployment. HTTP security
tests are targeted safeguards, not an exhaustive security audit.

Source Unicode may retain unresolved encodings; no fabricated spacing, OCR,
LaTeX, word snapping or semantic correction. No new inference, benchmark rescoring,
annotation edits, dependencies, downloads, runtime/Colima changes or previous
artifact cleanup occurred. Frozen labels remain **agent_visual_checked, zero
independent human verifications**. No quality/generalization conclusion is drawn.

Next recommended work is independent desktop usability and coordinate review on
explicitly selected layouts, then scoped keyboard/rectangle interaction if approved.
No explanations or further inference are implemented here.
