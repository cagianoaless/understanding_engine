# Structure 0.2.0: explicit compact order and geometric robustness

Milestone 02b is an opt-in follow-up to PR #4. The 02a producer, validator and
schema remain byte-identical at `af590135a81ac3f76508d9b81f0389ea54d1b74e`.
The original PDF parser, extraction v1, dependencies and Experiments 001–004
are unchanged. No model or OCR integration is included.

```sh
uv run --frozen --offline python -m understanding_engine.structure_v2 \
  /path/to/extraction.json --output-dir /path/to/new-structure --pages 4
```

The new directory contains `structure.json`, with `structure_schema_version`
**0.2.0**. `--config` accepts partial `RobustSettings` overrides. The original
`python -m understanding_engine.structure` continues to produce 0.1.0. Exit codes
are 0 for validated publication and 2 for errors; existing directories are never
overwritten. Cooperative locking and staging retain the original writer's
filesystem limitations. Failed publications do not leave a successful destination.

## Reviewed weaknesses in PR #4

1. Every region pair creates either an accepted edge or an explicit ambiguity:
   `n*(n-1)/2` records even for simple prose. Per-ambiguity graph walks further
   amplify validation cost. This is avoidable output growth, not additional
   evidence about the PDF.
2. Gutter inference does not feed back into fragmentation. A narrow gutter can
   remain inside an already merged line; page-wide row median font size also
   makes mixed-font columns sensitive to the larger type.
3. Literal `bold` in font names is not a reliable style signal for opaque PDF
   font names. The new rule treats font identities as categorical observations.

## Order semantics and migration

The separate [0.2 schema](../src/understanding_engine/schemas/structure-0.2.schema.json)
adds a required page-level declaration:

```json
{
  "ordering": {
    "accepted": "transitive_closure",
    "otherwise": "unresolved_for_every_distinct_region_pair",
    "unresolved_reason": "overlap_or_column_transition_unproven"
  }
}
```

`relations` stores the transitive reduction of accepted `before` edges. Its
closure carries the accepted constraints. For every distinct pair with no path
in either direction, the ordering is explicitly unresolved under the declaration
above. This does not assert that the elements are semantically incomparable or
interchangeable. `ambiguities` can hold specific unresolved notes; its absence of
entries no longer means an exhaustive empty set of unknown pairs. Consumers must
check the schema version, follow the declaration, and never infer a total order
from array order. No cross-page order is inferred. `order_status(page,a,b)` queries
validated pages; self queries return `same_region`.

For unchanged regions, column assignments and geometric rules, compact ordering
preserves **all** 02a accepted and unresolved constraints. Synthetic tests compare
every distinct pair at 50, 100 and 300 regions, plus overlaps, spanning headings
and unsupported regions. That equivalence applies to representation only:
changed grouping and heading hypotheses can legitimately change the graph's
nodes and constraints in a new extraction run.

The builder uses temporary integer bitsets and pair comparisons. CPU and temporary
reachability can still grow quadratically. A general DAG's transitive reduction
can itself require quadratic edges. Common chains and separated two-column prose
produce linear accepted edges and a constant-size unresolved declaration.
The validator computes reachability once, rejects cycles, duplicate/redundant
edges, invalid geometric justifications and contradictory explicit ambiguities.
The query helper computes a closure per call; bulk consumers should cache it.

## Structural rules and traceability

Coarse rows retain 02a's vertical-overlap grouping. Fine gaps use
`gutter_split_gap_em=0.5` times the **smaller adjacent font size** to supply gutter
evidence. At an inferred gutter, such gaps split coarse lines even when below the
ordinary `line_gap_em=1.2` threshold. Coarse wide-gap evidence is retained so a
spanning heading does not erase the body gutter. Continuous spanning text is
retained when its word gaps do not meet the gutter split rule. Inference still
supports at most two columns; equally supported disjoint gutters remain ambiguous.

Heading candidates use column-local size, font-identity frequency and geometric
isolation. Short lines qualify at >=1.12 times local median size, or >=80% rare
nonmodal font identity with >=95% local size and a neighboring gap >=0.3 local
font size. Rare means at most 35% of column characters. Font names are never
searched for `bold` or interpreted as semantic labels. Column-local contexts also
scale paragraph gap/indent rules for mixed fonts. All defaults and full settings
are serialized; these are hypotheses, not calibrated probabilities.

Page geometry, source glyph IDs, backend ordering, Unicode and exact extraction
hashes retain the [original coordinate/source contract](coordinates.md).
References copy no corrected text. Every unit is assigned once to a candidate
region or explicit unknown. Source-aware validation checks provenance, bbox unions,
ownership and region/line/column references. `resolve_region` in
`structure_v2_contract` resolves original units against the exact input bytes.
The algorithm identity includes code/schema fingerprints, settings, Python and
jsonschema version; paths, timestamps and timings stay out of `structure.json`.

## Limits and evidence

Rare italic text, figure labels and page furniture can resemble headings; same
font/size headings may be missed. Spanning headings with unusually large gaps
can be fragmented. Superscripts, hanging indents, mathematics and diagrams still
confuse rows and paragraphs. Non-text graphic extents/formula roles remain a
page-wide unknown notice, not localized detections. `(cid:80)` is never repaired.

[Experiment 005](../evaluation/experiments/005/report.md) separates development
checks from frozen new evaluation pages, compares both implementations, and reports
regressions and resource measurements. Experiment 004 remains exposed evidence,
not independent validation. No human-verified or held-out accuracy claim follows.
