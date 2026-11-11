# Hybrid Interface v0 — contract 0.1.0

The prototype combines an unchanged extraction 1.0.0 with fallible structural
evidence. It neither changes Structure 0.2 nor runs Docling. It implements no
new segmentation, reading-order solver, recognition model or text correction.
The design follows inspection of PR17; examples on those pages are **post-hoc
interface demonstrations, not independent validation or new accuracy results**.

The three layers are explicit:

| Layer | Representation | Authority |
| --- | --- | --- |
| Source | Complete original extraction, including PDF SHA256, all pages/geometry, characters, original Unicode, backend indices, IDs and parser settings/dependencies | Original character records are the source of text/coordinates/identity. Backend order is not proven reading order. |
| Hypotheses | Provider/version, immutable input evidence, native hierarchy, item labels, boxes/origins, diagnostic model text, optional observed confidence and native order | Provider assertions, never unquestionable source truth |
| Associations | Per-evidence/per-page original-character owners, native memberships, contradictory claims, overlap pairs and region states | Explicit geometric links or native references; not reconstructed text alignment |

`source` embeds the **entire existing extraction contract**, rather than a new
copy of its schema. Its existing `derived` field remains derived/non-lossless;
only `characters` supplies authoritative Unicode. No source unit is filtered,
renumbered, normalized or rewritten. `source_canonical_sha256` hashes the
project's `json_bytes(source)`, **not arbitrary original file whitespace**. Keep
the original extraction-file hash in evidence provenance when that distinction
matters. The original extraction contract and parser provenance are reused.

Python contracts are in `hybrid_contract.py`; the serializable JSON contract is
`schemas/hybrid-0.1.schema.json`. Source-aware `validate_hybrid(document, original)`
checks the schema, original source and all deterministic derived links by
rebuilding them. JSON Schema alone cannot establish source conservation. Validate
loaded JSON against the independent original extraction before using it. The
returned JSON-compatible dictionaries are mutable caller data, not tamper-proof
objects; do not treat arbitrary unvalidated dictionaries as trusted hybrids.

Minimal API:

```python
import json
from understanding_engine.contracts import json_bytes
from understanding_engine.hybrid import build_hybrid, source_text, order_hypothesis
from understanding_engine.hybrid_contract import validate_hybrid

source = json.loads(extraction_bytes)
prediction = {
    "provider": "docling", "version": "2.148.0",
    "source_pdf_sha256": verified_execution_pdf_sha256,
    "status": "available", "error": None,
    "native": {"document": native_document_json, "items": exposed_items_json},
    "provenance": {"native_document_sha256": native_file_sha256,
                   "identity_basis": "verified execution ledger"},
}
hybrid = build_hybrid(source, [prediction])
validate_hybrid(hybrid, source)
payload = json_bytes(hybrid)
original_unicode = source_text(hybrid, page_number=6)
fallback = build_hybrid(source)  # Full source remains usable without a candidate.
```

There are only two explicit input formats, no plugin framework. Docling evidence
supplies the original exported document and optional exposed `items.json` from
PR17. Structure evidence supplies `provider="structure_0_2"`, `version="0.2.0"`
and `native={"document": structure_json}`. That output is validated with the
**existing** Structure 0.2 validator against canonical extraction bytes; v0
rejects Structure outputs bound to a different/noncanonical extraction-byte
hash rather than guessing an equivalent identity. No reconstruction runs inside
the builder. A failed candidate supplies `status="failed"`, `native=None` and an
explicit error. Additional metadata belongs in the caller's JSON `provenance`.

Docling's exported `version` is its document-schema version, **not the package
version**; its `origin.binary_hash` is **not SHA256**. Provider version, model/run
identity and original PDF binding must come from a verified external execution
ledger. The builder checks the claimed PDF SHA256 against the extraction; it
cannot authenticate an arbitrary caller's claim or rehash an absent PDF.
The retained demonstration verifies every consumed file against PR17 hashes and
binds the native document through the original successful execution ledger.

Every hypothesis retains its complete original input, content-qualified stable
ID and provider/version/provenance. Native pointer paths identify assertions in
that input. Item IDs/parent/children and group/root nodes are retained even when
they have no box. No table child is removed, and a native parent is **not required
to geometrically contain its child** (a table caption can lie outside its table).
All provenance boxes of a multi-box item retain the same native item ID and
distinct original provenance indices. Stable hybrid IDs qualify the entire
evidence artifact; changing diagnostic text/provenance can change them, never
the original source IDs.

Original model text lives only in the retained hypothesis input and optional
`diagnostic_model_text`. Confidence is null unless a finite native `confidence`
value is actually supplied, with its native pointer; it is not inferred from
coverage, calibrated, converted to a probability or fabricated for PR17.

**Geometry and associations.** Docling's native page dimensions must match the
original exactly. v0 accepts only verified zero rotation, UserUnit 1, origin-zero
media/crop/pdfminer/page frames (raw crop may be absent). BOTTOMLEFT becomes
`[left,H-top,right,H-bottom]`; TOPLEFT stays unchanged. Boxes must be finite,
positive-area and inside the original frame. No clipping, rescaling, tolerant
matching or guessed crop/rotation transforms occur. Structure boxes already
use the source frame and retain their separately validated geometry.

Each original character center inside/on a region's box is associated, in
original backend-index order. This is the same **inclusive center rule** as
PR17, not a newly tuned threshold. Overlapping parent/child regions can both own
the same character. Geometric ownership is assessed **within each evidence
artifact**; different providers are not combined into an apparent ownership
conflict. No winner, parent preference or confidence arbitration is introduced.

| Recorded state | Meaning |
| --- | --- |
| Native membership | Existing validated Structure source ID; distinct from geometric ownership |
| Unambiguous geometry | One region in this artifact covers the original center; not a glyph-to-model-text alignment |
| Ambiguous geometry | Multiple regions cover the center, including nested regions |
| Unmatched | No geometric owner, or a nonvisual text region has no source centers |
| Contradictory claim | Unsupported/foreign/duplicate/outside-box native claim; retained separately without inventing a source unit |
| Zero-character visual | A valid box with predicted picture/table/formula role and no original centers; **not** verified object identity or recovered content |

Docling has no native source-character crosswalk in these inputs. Any purported
`source_character_ids` on a Docling node are retained as **contradictory**, even
if a string coincides with a real ID; they never become native membership.
Invalid Structure-native references reject that evidence through its existing
contract. Original characters are always kept independently. Native membership
and geometric ambiguity coexist: explicit native membership does not make
overlapping boxes unambiguous. Positive-area box intersections are also recorded
when no character center exists. Spatial containment never invents hierarchy.

`source_text` reads only source units and orders an explicit selection by backend
index; duplicate/foreign selections fail. It does not read model text, insert
spaces or claim reading order. Consumers must not concatenate every region's
source string blindly: nested/overlapping links intentionally repeat ownership.

**Order and failure behavior.** Native Docling traversal is checked against the
native body tree and its exposed items; group nodes remain containers, not
invented order tokens. With no exposed traversal, order is unavailable. Structure
keeps its native compact DAG/unresolved policy; reachability reuses its existing
implementation. `order_hypothesis` returns a provider-qualified hypothesis, never
authoritative order. Same-item boxes **always remain unresolved**, including
cross-column continuations. Native provenance-array order is not promoted to
reading order. Missing positions/paths remain unresolved; no quadratic expansion
of all unknown ordering pairs occurs.

Corrupt source contracts fail before construction. A well-formed candidate with
a mismatched PDF, invalid native references, inconsistent traversal, or unsupported
geometry becomes `rejected` with a visible reason and original evidence retained;
no partial normalized regions escape. Failed/missing evidence leaves complete
source data and explicit `source_only_pages`. Invalid envelope/schema or non-JSON
data (including NaN) fails closed rather than fabricating serializable values.
Call `build_hybrid(source)` for the explicit standalone fallback. No original
parser/Structure production behavior is changed.

**Limits and next validation.** This is not a text alignment, parent selection,
reading-order consensus or mathematical reconstruction algorithm. `(cid:...)`
units remain unchanged; authority means the extracted source of record, not a
claim that backend Unicode decodes every mathematical glyph correctly. Raster
objects remain textless. Unknown labels/containers are retained, not semantically
repaired. A bad page transform rejects the complete supplied artifact. Partial
Docling traversal, noncanonical Structure cache bindings, confidence formats
other than native numeric `confidence`, and shifted/rotated Docling frames need
explicit future contracts, not guesses in v0.

Source/native inputs are copied and retained for traceability, increasing JSON
size. Center association costs O(characters × regions) per supplied page; explicit
intersection reporting is O(regions²) worst case. This small offline prototype
has no full-document scalability claim. Runtime provenance should contain stable
portable identifiers/hashes; callers must keep paths/secrets/timings in separate
execution evidence. No tests depend on a private PDF/model/container or network.

First independently validate **association validity and honest abstention**, not
claim improved detection from the unchanged predictions. Under a separately
approved protocol, freeze v0 and select new unexposed development pages before
predictions; have an independent human annotate native membership versus spatial
association, overlap/zero-glyph cases and supported order constraints from source
PDFs first. Freeze annotations before constructing hybrids, include every failed
page, and report valid links, ambiguous/contradictory/unmatched cases, conservation
and order coverage separately. Include tables, multi-box continuations, formulas
and raster objects; do not tune on PR17 pages and call them independent. Preserve
held-out data. Existing 48/24/18 references can receive a separate versioned human
review, but remain agent-only here; that review is not fresh model validation.

See [the offline demonstration](../evaluation/hybrid_v0/report.md) and
[human-review checklist](hybrid-v0-human-review.md). No next evaluation, inference,
annotation edit, GUI or downstream scientific explanation is authorized here.
