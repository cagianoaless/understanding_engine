# Minimal derived structure 0.1.0

Milestone 02a implements the reduced deterministic portion of the
[approved design](milestone-02-design.md). No production extraction behavior,
v1 schema, dependencies, existing experiments, or held-out documents change.
PR #1 was unmerged at implementation start; base commit is
`cef6e2bfc837cdbb95d252738d648276ed6d0422`, not the bootstrap on main.

## Usage and contract

```sh
uv run --frozen --offline python -m understanding_engine.structure \
  /path/to/extraction.json --output-dir /path/to/new-structure --pages 2
```

Omitting `--pages` selects all pages. `--config file.json` accepts a partial JSON
object of `StructureSettings` overrides; unknown settings are errors. Exit 0
means successful publication (including a valid empty text layer); exit 2 means
an input, settings, contract or publication error. Existing destinations are
never overwritten. A sibling lock and staged directory protect publication.
Like the original writer, this coordinates cooperative writers, not arbitrary
external programs or power-loss recovery. Stale locks require manual inspection.
Execution diagnostics go to stderr; there is no additional runtime dependency.

The packaged [JSON schema](../src/understanding_engine/schemas/structure.schema.json)
has `structure_schema_version=0.1.0`. `source` records the PDF hash, **exact input
extraction-file byte hash**, extraction schema version and complete parser
metadata/settings. Reformatting the input file changes the hash and overlay IDs.
`algorithm` records version, complete settings and a SHA-256 over the two
implementation modules and structure schema, without filesystem paths or times.
Keep the original extraction artifact alongside the overlay; it is never copied
into or changed by `structure.json`.

Each selected page copies the original geometry/status. Coordinates are exactly
[pdfplumber-native-v1](coordinates.md): `[x0,top,x1,bottom]`, y downward, possibly
nonzero origin, no applied crop or UserUnit scaling. Do not interpret `width`
as an origin. Source out-of-page glyphs are retained without clipping.

- `columns`: page partitions inferred from gutters, with stable IDs and boxes.
- `lines`: original character IDs, enclosing bbox, column (nullable), median size
  and heading evidence. Line array order is serialization, not reading order.
- `regions`: candidate paragraph/heading or explicit unknown, source character
  IDs, constituent line IDs, bbox, column and uncertainty/rule evidence.
- `relations`: accepted `before` edges and supporting geometric rules, a DAG.
- `ambiguities`: unresolved region pairs with reasons. Absence of an edge is
  not evidence of equivalence or a proven incomparable order.
- `unassigned_characters`: reserved explicit character/reason accounting. The
  current implementation assigns every source unit to a text/unknown region.
- `unresolved_content`: page-wide unknown-content notice with original image
  count. V1 has no graphic extents or formula roles: this is **not** localized
  figure detection, nor proof that a page contains a graphic. Vector graphics
  can exist even with image count zero. Equations remain unclassified text
  hypotheses with original glyph references, not discarded or reconstructed.

All character references retain **backend index order**, independently of layout
relations; no Unicode text is synthesized, normalized or repaired. IDs include
the source hash and algorithm/settings identity. `resolve_region(structure,
extraction_bytes, region_id)` returns the original units after source-aware
validation. Reverse mappings can be built from region character lists.
`validate_structure` checks schema, exact provenance, unique IDs, complete
character and line ownership, bounding unions, column partitions and membership,
order geometry, cycles and contradictory ambiguity relations. Validation proves
internal traceability, not visual/semantic correctness. Unsupported orientations
and degenerate units are retained in an unknown region.

## Rules, settings and limitations

Default settings are in `StructureSettings` and the experiment's
[frozen configuration](../evaluation/experiments/004/config.json). Positive finite
values are required; fractions are at most one and support/count settings are
integers. These are candidate rules, not calibrated probabilities:

1. Group horizontal, positive-area units by vertical overlap (`row_overlap=0.5`),
   then split fragments at a horizontal gap greater than `line_gap_em=1.2` times
   row median font size. Superscripts, close parallel baselines and overprinting
   can confuse rows. This does not infer spaces or alter the text layer.
2. Infer at most two columns from repeated row gaps and fragment projections
   (`gutter_min_support=3`, minimum side fraction 0.15). Candidate gutters are
   restricted to the central 20–80% of text extent; projection candidates allow
   at most 20% crossing fragments relative to the smaller side. Disjoint equally
   supported gutters produce an ambiguous layout. Unequal or complex columns,
   tables and diagrams can fool this page-wide heuristic.
3. Mark short lines (at most 100 units) as heading candidates at >=1.15 times
   the page median size, or >=70% bold font names and >=95% median size. Boldness
   uses the backend font name, not semantic classification. Captions, emphatic
   prose and figures can be false headings; short regular headings can be missed.
4. Group within each column, breaking at headings, gaps greater than 0.45 body
   font size, positive indentation changes greater than 0.9 body size, or vertical
   overlap exceeding 0.3 body size. Font size is a geometric proxy; bullets,
   hanging indents, superscripts and compact paragraphs can be split or merged.
   Spanning lines stay separate rather than joining across columns.
5. Accept vertically separated regions in the same column; a spanning heading
   may precede both columns. Do not assert a left-to-right column transition or
   any cross-page order. Uncertain/overlapping pairs are explicit ambiguities.
   Same-column vertical order itself is a hypothesis, particularly in diagrams.

Configuration changes alter the output identity. Remaining numeric constants are
fixed versioned rules above, not hidden per-paper tuning. Pairwise relations and
ambiguities can use quadratic space; row clustering/validation can also be
expensive on dense pages. No throughput or memory bound has been established.
No OCR, neural parsing, Docling/MinerU, semantic corrections, tables, formulas,
highlighting or UI is implemented. `(cid:80)` remains untouched.

## Evidence

Offline tests use existing licensed fixtures and temporary ReportLab PDFs with
authored geometry/text (new test content is dedicated to CC0-1.0). They cover
single/two columns, staggered baselines, spanning headings, three-column
ambiguity, overlapping units, paragraphs, Unicode, transformed pages, source
resolution, determinism and failed publication. They establish these cases only.

The [development probe](../evaluation/experiments/004/report.md) reports both
correct and incorrect decisions from three pages with frozen agent annotations.
It supplies no human-verified reference, held-out evidence, full-document score
or claim to satisfy the larger Milestone 02 design's quality gates.
