# Milestone 02: document structure (design only)

Status: proposal for [issue #3](https://github.com/cagianoaless/understanding_engine/issues/3).
Contract review base: `62e47b3718aeaacce43f548aa02f3eb21165830e`, after issue #2.
No structure implementation or benchmark has run. All gates below are proposed.

## Scope and existing evidence

Detect columns, text blocks, paragraph boundaries, section headings, captions,
footnotes, and table/figure/equation **regions**. Infer supported reading-order
relations. Detection means locating and labelling a region; extraction means
recovering its contents; reconstruction means interpreting its internal structure.
Only detection/grouping/order belong here: no table cells, LaTeX, symbol recovery,
semantic interpretation, text correction, highlighting, RAG, tutoring, or UI.

The [v1 extraction schema](../src/understanding_engine/schemas/extraction.schema.json)
and [coordinate contract](coordinates.md) are the inputs, unchanged:

- `source_sha256`, `parser`, and `coordinate_system="pdfplumber-native-v1"` identify
  the PDF, environment/settings, and geometry convention.
- `pages[].characters[]` holds glyph-associated `id`, `backend_index`, original
  `text`, `bbox`, `backend_bbox_bottom_origin`, `matrix`, `doctop`, `upright`,
  `fontname`, and `size`. IDs have form `<pdf-sha>:p<1-based-page>:c<0-based-index>`;
  an ID does not imply a single Unicode code point or a reading position.
- `pages[].geometry` preserves native/raw page boxes, rotation, dimensions,
  pdfminer layout bounds, initial doctop and UserUnit. Native boxes are
  `[x0, top, x1, bottom]`, y increasing downwards; origins need not be zero.
  CropBox and UserUnit scaling are not applied. Preserve these facts rather than
  silently mapping into a zero-origin or cropped coordinate frame.
- `pages[].derived.{text,lines}` is lossy. Lines have nullable `bbox` and
  `source_character_ids`, but no IDs. Neither these lines nor backend indices
  establish reading order. V1 has `image_count`, not image/vector region boxes.

[Experiment 001](../evaluation/experiments/001/baseline.json) is the unchanged
student baseline. [002](../evaluation/experiments/002/report.md) measured spacing
on 25 selected agent-checked real samples and 54 authored synthetic lines:
relative 0.125 had zero measured space errors there; absolute 2 inserted 56
extra synthetic spaces. [003](../evaluation/experiments/003/report.md) had
identical outputs for all three candidates: 24/30 exact, six unscoreable
(four annotation errors and two representation mismatches). Its 285 explicit
space glyphs in 29 regions weakly stress inferred word gaps. Neither experiment
has human-verified real references. These are spacing observations, not evidence
of structure accuracy or parser superiority. Production remains `x_tolerance=3`.
Issue #2 repairs the registry test independently; historical experiment results
and their recorded test failure remain intact.

## Proposed derived contract

A separate, versioned `structure.json` (`structure_schema_version="0.1.0"`),
without extending v1 or replacing `extraction.json`:

| Field | Proposed meaning |
| --- | --- |
| `source` | PDF SHA-256, exact extraction-file SHA-256, extraction schema version, original parser/settings; resolve the original artifact by hash. |
| `algorithm` | Rule-set revision/commit and complete settings. Runtime paths/timestamps/timings belong in a separate structure run record. |
| `regions[]` | Stable ID, 1-based source page, native bbox, type, character IDs, optional original line references `(page, zero-based line index)`, rule/evidence, and uncertainty reasons. |
| `relations[]` | `contains`, `before`, or `caption_for`, referencing region IDs, with rule/evidence and acceptance/ambiguity status. |
| `ambiguities[]` | Explicit incomparable region pairs or mutually exclusive alternative relations/types, with reasons; never imply that all absent edges are proven incomparable. |
| `unassigned_characters[]` | Every unassigned source character ID and reason, including whitespace, rotated text, or unresolved grouping. |

Types: column, paragraph, heading, caption, footnote, table_region, figure_region,
equation_region, unknown. A region describes a page-local fragment; continued
paragraphs may later have an explicit continuation relation. Stable IDs derive
from the extraction hash, algorithm/settings hash and canonical region identity;
sorting IDs is serialization only. Uncertainty is categorical, not an uncalibrated
probability. Parent/child overlap is explicit; unrelated double ownership is an
error. Textless/failed pages retain an explicit status and unresolved reasons.

Accepted `before` edges form a partial-order DAG. A spanning heading may precede
two columns without ordering a floating figure against both. Alternative edges
are not included in its transitive closure; conflicting evidence produces an
ambiguity rather than an arbitrary total order. Cross-page edges require an
explicit rule, not just page-number concatenation. Cycles fail validation.

Character references resolve by ID plus extraction hash; optional JSON pointers
identify exact original entries. Build a reverse character-to-region index when
reading the structure. Keep source-unit order separately from proposed layout
order; no inferred space is assigned a fictional source character. Do not copy
rewritten text, normalize Unicode, join hyphens, or interpret equations.

Empty character references are legitimate for a non-text region hypothesis, with
`evidence=layout_gap` and uncertainty declared. V1 cannot establish true graphic
extents from `image_count`; geometry-only figure/table detection may abstain and
will incur missed-region errors. A future graphics source or specialized parser
must be a separately recorded input with an explicit coordinate transform,
never a fabricated character link or replacement authoritative extraction.

## Frozen development evaluation

Follow the existing [evaluation protocol](../evaluation/protocol.md). Use only
the registered Attention, BERT and Nature TabPFN byte hashes in the
[development manifest](../evaluation/development/manifest.json). Proposal:
12 pages, four per document, spread across the paper. Before any structure
candidate runs, inspect page renders and select one prose page, one page with
heading/footnote material, one caption/figure/table page, and one mathematical
page per document. Capture single/two-column layouts, spanning elements,
font-size variation and references; record unavailable strata explicitly.
Freeze page selection, native bboxes, annotation rules, expected relations,
metrics and settings by checksum. No selection using candidate successes/errors.

Budget: at most eight human hours (six annotation, two independent review and
adjudication), 180 region boxes, 120 paragraph-adjacency decisions and 120
reading-order pairs, balanced across documents. Include at least 12 mathematical
regions overall where available. Freeze bounded evaluation windows if a page
exceeds the budget; score all included predictions and references. Unreviewed
material stays unverified; insufficient verified coverage blocks an acceptance
claim rather than shrinking its denominator after seeing outputs.

Store PDF/extraction hashes, page/bbox, region type, referenced characters where
resolvable, pair/boundary labels, ambiguity reasons, reviewer and evidence.
Review at least 20% independently and every disagreement. An external teacher
may independently supply hypotheses with model/prompt/raw-response provenance;
this task makes no model calls. Keep `teacher_hypothesis`, `agent_visual_checked`
and `human_verified` cohorts separate. Only a recorded human check against the
PDF creates verified references. Old agent transcriptions do not become truth.
Freeze the human references independently of student/teacher agreement; retain
later corrections as new annotation versions, never overwrite baseline scores.

Later, register fresh papers/versions in the held-out split before analysis,
with permission/provenance checks. Freeze implementation and gates first; run
once without tuning on that set. No current held-out files change in this issue.
Three development papers do not establish generalization.

## Metrics and proposed gates

Report counts, per-document and per-category results, and document-macro scores.
Report frozen totals, excluded ambiguous counts/reasons, and scored denominators
for every metric. Candidate uncertainty, unsupported regions, parsing failures
and missing output are not reference ambiguities and cannot be excluded.

| Metric | Independently annotatable definition | Proposed gate |
| --- | --- | --- |
| Block detection | One-to-one maximum-IoU matching at fixed IoU >= 0.5, deterministic ID tie-break. Precision = matched/predicted; recall = matched/reference. Report location and type-conditioned scores separately. Unmatched outputs/references are FP/FN. | Text-block P and R >= 0.90 macro, each document >= 0.80; report table/figure/equation P/R separately without implying they passed. |
| Reading order | On the 120 preselected, reference-comparable block pairs, score the accepted DAG closure. Correct orientation / all such pairs; missing blocks, abstentions and inversions count as incorrect. Report inversions and missing relations separately. Human-ambiguous pairs have a separately reported excluded count. | Agreement >= 0.95, each document >= 0.90; zero cycles. |
| Paragraph boundaries | For frozen consecutive line pairs within a reference column, a break is positive and a join negative. Missing line alignment counts as an incorrect boundary decision; report unaligned positives/negatives separately. P = correct predicted breaks / predicted breaks; R = correct breaks / all reference breaks. | P and R >= 0.90; all 120 decisions accounted for. |
| Heading/caption labels | Confusion matrix and per-class P/R/F1 on reference-matched blocks; unknown is an abstention/error, not an exclusion. Also report end-to-end type-conditioned detection to expose missing blocks. | Heading/caption macro F1 >= 0.85 with at least ten verified examples per class; otherwise insufficient evidence. |
| Traceability/coverage | Resolved character references / all emitted references; unchanged source text/geometry; accounted-for IDs (assigned or explicitly unassigned) / all source IDs. Separately report assigned text-character coverage and unsupported graphic regions. | 100% valid references and accounting, zero silent source mutations or undeclared overlaps; >= 95% assigned text-character coverage in verified text windows. |

Undefined P/R (zero denominators) is `not_evaluable`, never 100%. For unaligned
paragraph decisions, count FN for reference breaks and FP for reference joins;
add no TP. Also report exact decision accuracy across all frozen pairs. All
quality gates require the planned verified annotation counts. Intrinsically
ambiguous references are excluded only before scoring and remain visible in
total counts; annotations exhausted by the budget are explicitly out of scope.

The first vertical slice is a page with a spanning heading, two columns and
paragraph breaks, producing source-linked regions and a partial-order graph.
Require traceability, reproducibility and synthetic layout tests before real
accuracy gates. It can pass this limited slice while figure/table/equation
regions remain unknown; full region-detection acceptance needs separately
pre-registered targets and sufficient verified samples, not a renamed success.

## Staged comparison and feasibility

**A, first:** standard-library geometry over existing characters. Separate
orientations, cluster baselines, propose gutters/columns, regroup lines within
columns, then use indentation/vertical gaps and local font-size distributions
for paragraph/heading/caption/footnote hypotheses. Keep thresholds explicit and
fixed per run. Use numbering patterns only as syntactic evidence; no semantic
correction. Existing derived lines may cross columns, so do not accept them as
paragraph truth. New runtime dependencies: none proposed.

**B, conditional:** Docling or another specialized layout parser, isolated from
production. Read-only PyPI metadata checked on 2026-11-05:
[Docling 2.148.0](https://pypi.org/pypi/docling/2.148.0/json) declares Python >=3.10,
<4 and MIT; its 5,333-byte wheel delegates to
[docling-slim[standard] 2.148.0](https://pypi.org/pypi/docling-slim/2.148.0/json)
(1,210,905-byte wheel). That extra includes torch, torchvision, scipy,
docling-ibm-models, docling-parse, rapidocr and multi-format dependencies.
These package-file sizes are **not** installed footprint or total downloads.
The [official FAQ](https://docling-project.github.io/docling/faq/#which-model-weights-are-needed-to-run-docling)
confirms the PDF pipeline needs model artifacts, even apart from OCR.

Local check: macOS arm64, Python 3.11.13, eight logical CPUs, approximately
15 GiB free disk; Docling, MinerU, torch and transformers are not installed.
RAM was not available through the sandbox's hardware query. Full dependency
closure, installed bytes, weight identities/sizes/licenses, peak RSS and CPU
runtime remain unknown. Therefore B is **not cleared for installation or a run**.
After separate authorization, first audit the complete locked CPU dependency
closure and weight manifests against available RAM/disk; reject an infeasible
candidate. Only then consider an isolated CPU-only trial with OCR, VLMs,
formula/code enrichment and remote services disabled. Keep its native output;
adapt boxes to v1 coordinates and measure character grounding, never accept its
text as a corrected extraction. No models/packages are downloaded in this design.

**C, optional later:** [MinerU 4.1.7 metadata](https://pypi.org/pypi/mineru/4.1.7/json)
declares Python >=3.11,<3.15, a 3,847,117-byte wheel, ONNX runtime, model-hub
clients and, on macOS arm64, the torch extra (torch/transformers). Its license
identifier is `LicenseRef-MinerU-Open-Source-License`; the
[upstream license](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)
adds terms to Apache 2.0. Record the exact release's terms and separate weight
licenses before considering it. Backend/weights, installed size, CPU/GPU needs
and local feasibility are unverified. Do not automatically install, download or
run it, or assume it is lighter/better than A or B.

For any future authorized comparison, preserve commit/lockfile, PDF/extraction
hashes, commands, settings, exit codes and stderr; exact package/weight revisions,
SHA-256, download/installed bytes and licenses; hardware, OS, explicit CPU device
and thread count (no GPU), cold/warm time per page, process-tree peak RSS and
failure/timeout counts. Keep raw native outputs and normalized region overlays,
coordinate transforms, unmatched character counts and grounding metrics. Weights
for A are `none`; B/C weights and all resource measurements are `not_measured`
today. A future trial must choose resource ceilings before running. No ranking
or performance estimate is justified by this metadata review.

## Risks, sequence and open choices

Fragmented equations can resemble columns; `(cid:80)` and superscript mappings
limit Unicode interpretation; rotated text/nonzero page origins complicate
geometry; spanning blocks cause column interleaving. Detect equation regions
without repairing their symbols. Publisher-supplied spaces may mask spacing
weaknesses without improving structure. None of these is solved by tuning word
gap thresholds. Code, model and document/image redistribution licenses require
separate provenance; keep large/raw licensed artifacts outside Git.

1. Freeze annotation rules and human references; implement a separate derived
   contract/validator and synthetic geometry fixtures after approval. Use existing
   schema/test tools; no new runtime packages or v1 schema changes.
2. Implement A's vertical slice and evaluate the frozen development set, then
   extend only to supported region rules. Keep source fingerprints and offline
   regressions; stop on traceability violations. Dependency burden: standard
   library plus existing extraction/test stack.
3. If verified structural failures justify more complexity, audit B's full
   footprint/licenses and local resource budget before proposing a separate
   installation/benchmark. C remains deferred. Burden is substantial and
   unresolved; no neural dependency is added to production by this plan.

Open choices for review: confirm annotation budget and provisional quality gates;
set later figure/table/equation acceptance targets; decide whether a graphics
geometry source is worth a separate contract; set resource ceilings and whether
any model-backed comparison is justified at all. These decisions precede such
work, not the current design deliverable.
