# Source Selection v0 — contract 0.1.0

Selection is a read-only view of an independently validated Hybrid v0. Original
characters/Unicode/boxes remain authoritative. No word segmentation, text repair,
model execution, mathematical reconstruction or reader UI is implemented.

These rules were defined before the selection tests:

| Query | Original character selection | Structural candidates |
| --- | --- | --- |
| Explicit IDs | Exact, unique IDs from one source page, returned in backend extraction order; duplicates/foreign IDs fail | Regions linked to any selected ID through existing native, geometric or contradictory associations |
| Rectangle | Original character centers on or inside all four boundaries (inclusive, as in Hybrid v0) | Every region with positive-area intersection with the rectangle, plus regions linked to selected IDs |
| Point discovery | Every original character box containing the point, boundaries inclusive; degenerate boxes are not discarded | Every containing region box, boundaries inclusive, plus existing links to hit character IDs |
| Existing hybrid region | Explicit `geometric` basis (default) or `native` valid-membership basis; no automatic preference/fallback | The requested region and all other regions linked to selected source IDs |

No query snaps to words, adds spaces, selects a smallest box, drops table children
or resolves ambiguous owners. A point is **candidate discovery**, not a resolved
word selection. Its text is the backend-order concatenation of *all hit units*,
clearly labelled as candidate text. Empty selections are valid, not parse failures.
Requesting native membership on Docling can return no characters despite existing
geometric glyphs; that is **not** evidence of a textless visual object.

Spatial calls require explicit `coordinate_system="pdfplumber-native-v1"`.
They reuse Hybrid v0's strict origin-zero, crop/media, zero-rotation, UserUnit-1
checks and original page bounds. Rectangle boxes must be finite, positive-area,
ordered and within bounds; points must be finite and within bounds. There is no
clipping, tolerance, guessed zoom/crop/rotation, or viewport conversion. ID and
prevalidated-region queries do not require a new coordinate transform and remain
available for source-only documents with other valid original geometries.

Results contain only selected original units and relevant structural metadata:
PDF/source identities, page geometry, selection rule, source text, provider and
native item/box IDs, explicit association evidence, relevant ancestor hierarchy,
and exposed reading-order evidence. No raw prediction, model text, complete source
document, complete page text, or descendant expansion is returned implicitly.
Returned fields are detached from the index and can be serialized deterministically.
No inferred LaTeX or verified human reading order is claimed.

The index validates once using `validate_hybrid` against the independent original
extraction, bound to an explicitly expected PDF SHA256. It borrows that validated
document read-only and lazily builds per-page ID/region/association lookups. The
caller must keep the document unchanged for the lifetime of the index and replace
the index when evidence changes. This avoids duplicating or serializing the large
hybrid for every interaction; it is not a new persistent database or spatial tree.

```python
from understanding_engine.selection import SelectionIndex
from understanding_engine.selection_contract import validate_selection

index = SelectionIndex(hybrid, original_extraction,
                       expected_pdf_sha256=verified_original_pdf_sha256)
units = index.by_character_ids(6, original_character_ids)
area = index.by_rectangle(6, [72, 60, 290, 100],
                          coordinate_system="pdfplumber-native-v1")
candidates = index.at_point(6, [150, 80],
                            coordinate_system="pdfplumber-native-v1")
region = index.by_region(6, evidence_id, hybrid_region_id, basis="geometric")
native = index.by_region(6, evidence_id, hybrid_region_id, basis="native")
validate_selection(units, index)  # For externally loaded/untrusted response JSON.
```

`index.select(query)` accepts the same versioned schema's JSON query shapes;
Python convenience methods accept lists/tuples for ID and coordinate arrays.
Query provenance retains the supplied ID order, while returned units/text always
use backend order. Same requests on the same immutable evidence produce identical
canonical JSON. Expected PDF identity, foreign IDs/regions, unknown pages and
invalid coordinates are rejected with `ExtractionError`; malformed source/hybrid
validation is delegated to existing contracts. No screen coordinate system or
transform argument is accepted. Serialized responses are source-aware validated
by replaying their query on an independently validated context.

Ambiguity is assessed per evidence artifact, not by treating two providers as
one ownership pool. Status flags distinguish point glyph ambiguity, existing
geometric overlap, contradictory claims, unmatched units, source-only fallback
and zero-character visual hypotheses. Multiple disjoint selected regions are not
automatically called ambiguous. A region's inherited association status is kept
separate from whether this *selection* hits an ambiguous unit.

Reading-order output is a **subset**: exposed positions for matched native items,
direct native DAG edges whose endpoints are matched, and explicit within-item
abstention. Missing subset edges do not mean no transitive path exists. Use the
existing `hybrid.order_hypothesis` for an explicit pair query; this API does not
duplicate its solver or expand all candidate pairs. Hierarchy includes matched
items and their ancestors, with total child counts and only relevant child links.
Other provenance boxes of the same native item are referenced by ID, not silently
expanded into source text or ordered by their array position.

Runtime/size measurements belong in separate execution evidence, never in the
deterministic SelectionResult. Responses scale with the requested selection;
there is no silent truncation. Full-page/full-table queries can be large. No
full-document scalability or independently validated selection accuracy is claimed.

Unresolved cases include overprinted glyphs, inclusive-boundary ties, nested and
overlapping regions, geometry/native-membership disagreement, source encoding
such as `(cid:...)`, raster objects without text and multi-box continuations.
Original source text is a source-of-record view, not proof of correct decoding.

The minimal future viewer should keep one immutable validated document/index,
bind every interaction to PDF SHA256/page/evidence IDs, explicitly map viewport
coordinates through a verified transform, highlight every candidate, and let a
person choose among overlaps. It should render source Unicode separately from
fallible labels and unresolved order. Zoom/rotation mapping and a UI remain future
work; no integration or additional evaluation is authorized by this milestone.
