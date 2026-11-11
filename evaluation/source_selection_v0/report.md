# Source Selection v0 — offline record, 2026-11-11

Implemented on `feat/source-selection-v0`, stacked on PR18 commit
`87894c4034cb4f05b29eb6663d1ac2c7cd7d42a7`. This is a read-only application API,
not a new model evaluation. No inference, scoring, annotation edits, package/model
downloads, runtime/Colima operations, viewer, or mathematical reconstruction ran.

The [contract/semantics](../../docs/source-selection-v0.md) were defined before
tests. The original pre-test text/hash is preserved in external evidence; later
documentation adds API usage without changing those boundary rules. The API uses
existing `validate_hybrid`, `source_text`, Hybrid geometry primitives, association
records and native order evidence. It does not duplicate `order_hypothesis`'s
solver; pair queries remain in that existing API.

Four queries return schema **0.1.0** `SelectionResult`:

- Original character IDs, without new positions or word-boundary inference.
- Native-frame rectangles: inclusive original character centers, positive-area
  structural intersections.
- Existing regions: explicit geometric/default or valid native-membership basis.
- Points: every containing glyph/region box, boundaries inclusive, unranked.

Original IDs, Unicode, full original unit boxes and backend indices remain intact.
Text is exact backend-order source text, never model text or a verified human
reading order. Model confidence does not rank a winner. Overlapping/nested owners,
contradictory claims, unmatched units and textless visual hypotheses stay explicit.
Empty native membership for a Docling region does not falsely make it a textless
object. No formula text is described as verified LaTeX.

Responses include relevant providers/native item/box IDs, ancestor hierarchy,
native confidence only when supplied, and a **subset** of exposed positions/direct
DAG edges. They omit raw predictions, model text, complete source documents,
full-page text and implicit descendant expansion. Multiple provenance boxes keep
their common item identity and unresolved within-item order. Source-only image
pages do not acquire invented visual regions.

**Measured retained evidence.** The existing 58,496,673-byte BERT hybrid and its
independent original extraction were verified against PR18/PR17 content hashes.
The full original source has 16 pages; query page **6** has **3,690 units / 164
structural boxes** across both providers. No frozen annotation or benchmark-score
file is loaded by the API or demonstration. Previously exposed evidence is used
only for contract/functionality and selection resource observations, **not fresh
independent validation or comparative quality measurements**.

| Query | Source units / candidates | Canonical response bytes | Warm query median | Serialization median |
| --- | --- | ---: | ---: | ---: |
| Synthetic four explicit units | 4 / 1 | 5,406 | 0.629 ms | 0.103 ms |
| Synthetic center rectangle | 4 / 1 | 5,213 | 0.603 ms | 0.090 ms |
| Synthetic point | 1 / 1 | 4,245 | 0.511 ms | 0.074 ms |
| Synthetic merged formula, empty model text | 4 / 1 | 5,296 | 0.646 ms | 0.092 ms |
| Synthetic zero-glyph picture | 0 / 1 | 3,990 | 0.486 ms | 0.069 ms |
| BERT five explicit original units | 5 / 3 | **12,359** | **1.470 ms** | 0.200 ms |
| BERT unit rectangle | 5 / 3 | 12,191 | 1.912 ms | 0.192 ms |
| BERT point | 1 / 3 | **8,969** | **1.402 ms** | 0.156 ms |
| BERT first box of multi-box continuation | 149 / 2 | 104,731 | 7.925 ms | 1.367 ms |
| BERT complete table region | 345 / 118 | **558,382** | **38.630 ms** | 6.810 ms |
| BERT body paragraph region | 432 / 2 | 285,719 | 21.017 ms | 3.698 ms |

Values are actual UTF-8 bytes from the project's indented `json_bytes`, not HTTP
traffic/compressed sizes. Ten identical warm queries per case produced identical
response bytes. Query timing includes request/result schema checks, source text,
lookup/scans, metadata assembly and detachment; serialization is measured
separately. Raw samples, first-query timings, query shapes and response hashes are
in [measurements.json](measurements.json). Measurements are one local Darwin ARM64 /
CPython 3.11.13 run, not latency bounds or statistical generalization.

One-time validation/index construction: synthetic **0.002966 s**, retained BERT
**14.423907 s**. These exclude file reads/JSON decoding and reuse the existing full
Hybrid source-aware validation. Page lookup maps are lazy. The first synthetic
query took **16.387 ms**, including initial selection-schema setup; later cases
share that process/cache. BERT's first explicit-unit query took **2.847 ms**.
These are not independent cold-process trials.

The point/five-unit interactions avoid returning the 58.5 MB document. Larger
requests remain proportional to requested units and relevant evidence: the table
returns 118 candidates, including nested children, rather than silently choosing
a parent or truncating results. This is not a hard response-size cap. Repeated
geometry queries scan one indexed page linearly; source text still uses the
existing per-page helper. No new spatial tree or full-document scalability claim.

[example.json](example.json) is a **complete compact SelectionResult**, not a
partial hybrid. It contains one original BERT unit and all three matching layout
candidates, with actual geometry/IDs and relevant hierarchy. The full table and
paragraph responses stay outside Git along with all other query outputs and logs;
[external-evidence-manifest.json](external-evidence-manifest.json) gives hashes.
The large existing hybrid was read in place, never copied or reserialized as an
interaction response. Synthetic PDF and external artifacts are newly generated
and historical artifacts were not deleted or overwritten.

**Validation and preservation.** Full offline suite **452 passed**, zero
failures/skips, **8.81 s**; **37 new tests**. Coverage includes backend order,
original unclipped boxes, boundary ties, overprinted units, nested table/groups,
conflicting labels/confidences, merged/empty-text formulas, raster objects,
multi-box continuation, native memberships, source-only/failed layouts, Unicode,
invalid frames/coordinates/pages/identities, compactness, determinism, detached
results, tampering detection, and validation once rather than per query. No
private evidence or neural package is needed for unit tests.

Tests reuse the already installed compatible host 3.11.13 plus unchanged project
packages read-only. The broken launcher remains unrepaired. `uv --no-project`
makes `--frozen` ineffective; no sync/resolution/install occurred. Existing GitHub
CI separately uses its normal locked environment; the observed outcome is
reported with the PR. [validation.json](validation.json) and
[preservation.json](preservation.json) record checks; all prior tracked files,
frozen annotations, production parser, Structure 0.2, Hybrid v0, dependencies and
historical experiments remain unchanged.

**Remaining ambiguities and viewer recommendation.** The index borrows immutable
validated input: caller mutation while it lives is unsupported; rebuild the
context after evidence changes. Full upfront validation is too expensive for
every interaction and should run outside a future UI's event loop. The measured
page does not establish whole-document memory/scalability. Point results are
candidate units, not automatically selected words; explicit IDs can select words
when the caller knows their original units. Inclusive boundaries, overprints,
table children/parents and conflicting labels remain unresolved. Geometry links
are not native glyph-to-model-text alignment; `(cid:...)` stays unchanged.

Use one immutable document/context per verified PDF identity; request compact
queries and render highlights from original boxes. Check PDF/page/evidence IDs
before applying asynchronous results. Show all candidate choices and distinguish
native membership from geometry, source Unicode from labels, and absent layout
from empty source text. A later explicit, verified screen-to-PDF transform is
required; v0 rejects screen coordinates and unsupported crop/rotation assumptions.
No GUI, coordinate conversion, word reconstructor, new benchmark, explanation or
LaTeX feature is implemented. **Stop after Source Selection v0.**
