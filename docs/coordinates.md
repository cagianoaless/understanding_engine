# Coordinate contract: pdfplumber-native-v1

This contract describes pdfplumber 0.11.8 with the pdfminer.six version recorded
in each extraction. The application copies native values; it does not introduce
a new normalization or apply CropBox clipping. Consult the installed backend
source when changing versions:
[pdfplumber page.py](https://github.com/jsvine/pdfplumber/blob/v0.11.8/pdfplumber/page.py)
and [pdfminer process_page](https://github.com/pdfminer/pdfminer.six/blob/20251107/pdfminer/pdfinterp.py).

## Native page and character values

- `bbox`, `mediabox`, and `cropbox`: `[x0, top, x1, bottom]`. Positive x points
  right; positive top/bottom points down. Bounds are axis-aligned. Edge equality
  is allowed. Units are backend PDF user-space units, normally points
  (1/72 inch for UserUnit=1).
- `width = bbox[2] - bbox[0]`; `height = bbox[3] - bbox[1]`. Rotation 90/270
  swaps the effective dimensions. The native page bbox is the native MediaBox.
  Its origin is not necessarily `(0, 0)`.
- Character `bbox` copies `[char.x0, char.top, char.x1, char.bottom]`.
  Coordinates outside the page are retained and warned about, not clipped.
- `backend_bbox_bottom_origin` copies `[char.x0, char.y0, char.x1, char.y1]`.
  The y coordinates are pdfminer's bottom-origin layout coordinates; x values
  have already received pdfplumber's MediaBox offset. This is a diagnostic
  backend representation, **not the original PDF-space bounding box**.
- `matrix` is the backend LTChar affine tuple `[a, b, c, d, e, f]`, where
  `x' = a*x + c*y + e`, `y' = b*x + d*y + f`. It includes backend page/text
  transforms. It is not advertised as a complete inverse map to original PDF
  glyph outlines. `size`, `fontname`, and `upright` are also copied.
- `doctop = initial_doctop + char.top`; `initial_doctop` accumulates preceding
  page heights. `backend_index` is the position in `page.chars`, not a content
  stream byte offset or reading-order index.
- Derived line bboxes enclose their referenced native character bboxes. A line
  containing only inferred characters has a null bbox. Source references apply
  to glyph-associated units and do not identify the origin of inferred spacing.

## Raw page metadata

`raw_mediabox` and `raw_cropbox` preserve resolved original PDF rectangle values
in original PDF bottom-origin user space, before pdfplumber's normalization.
`raw_cropbox` is null when absent. A PDF rectangle may specify opposite corners
in reverse order; raw corner order is retained. `raw_rotation` records the
resolved Rotate value; `rotation` is the normalized clockwise degree value
modulo 360. Nonmultiples of 90 are rejected. `user_unit` records UserUnit or 1
when absent; no physical scaling is applied. Nondefault values produce a warning.

For the pinned backend, pdfplumber sorts each raw rectangle's coordinate pairs,
swaps x/y pairs for 90/270 rotation, then vertically inverts it using the
normalized MediaBox height `H`:

```text
(x0, y0, x1, y1) -> (x0, H - y1, x1, H - y0)
```

This produces native page boxes. For a raw MediaBox `[10, 20, 310, 220]`, the
native MediaBox is `[10, -20, 310, 180]` and dimensions remain `300 x 200`.
Do not infer a zero origin from page dimensions.

pdfminer first transforms original page content using the raw MediaBox
`(x0, y0, x1, y1)` and rotation:

| Rotation | Page CTM `(a,b,c,d,e,f)` |
| --- | --- |
| 0 | `(1,0,0,1,-x0,-y0)` |
| 90 | `(0,-1,1,0,-y0,x1)` |
| 180 | `(-1,0,0,-1,x1,y1)` |
| 270 | `(0,1,-1,0,y1,-x0)` |

`pdfminer_layout_bbox` records its resulting layout bounds. pdfplumber then adds
the native MediaBox x offset to layout x values, and computes character vertical
positions using native MediaBox top `T` and page height `H`:

```text
top    = H - backend_y1 + T
bottom = H - backend_y0 + T
```

The application preserves raw boxes, native boxes, layout bounds, rotation,
UserUnit, per-character matrices, and both character coordinate representations
to make later transformation debugging possible. No overlay/viewer coordinate
mapping is implemented in this milestone.

## Validation and evidence

Every output is checked against JSON Schema and semantic invariants. Non-finite
or inverted native boxes/transforms and invalid dimensions are fatal. Zero-area
character boxes and boxes outside page bounds are warnings. This checks numeric
consistency, not the correctness of glyph placement relative to a rendered page.

Regression fixtures cover standard positions with independently computed
Helvetica bounds, all four rotations, an explicit crop with text outside it,
and a translated/nonzero-origin page with UserUnit=2. These fixtures do not
establish correctness for all combinations of PDF transforms or unusual fonts.
