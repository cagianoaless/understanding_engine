# Experiment 005 — Structural robustness

**Result:** opt-in structure 0.2.0 substantially reduces order payload size and
improves agreement on the frozen text windows. It does **not** establish robust
whole-document structure. Mathematics and charts still produce false headings
and fragmented regions. The original 0.1 producer remains available unchanged.

All visual annotations are `agent_visual_checked`, with **zero human-verified
references**. These are development results on selected pages from familiar
papers, not independent document-level or held-out validation.

## Review, implementation and versioning

PR #4 was reviewed at `af590135a81ac3f76508d9b81f0389ea54d1b74e`; it has no
review comments and remains unmerged. Its pair generator creates exactly one
record per region pair; its validator repeats graph walks per ambiguity. An
inferred gutter does not split an already merged line, while literal `bold`
font-name matching misses opaque font identities. See
[implementation and migration details](../../../docs/structure-0.2.md).

[PR #5](https://github.com/cagianoaless/understanding_engine/pull/5) is a separate
branch stacked on PR #4; no merge is performed. The tested implementation is
[`c83d08b`](https://github.com/cagianoaless/understanding_engine/commit/c83d08b38157cdfa993acd63862eb16d6b8520e4),
tree `45664f5aae95ebe14313c1dc628f86014388d85b`. It was published before the
controlled comparison. No implementation/settings changes followed evaluation.

The new `structure-0.2.schema.json` explicitly declares accepted order as the
transitive closure of reduced edges and **every remaining distinct pair as
unresolved**. Explicit ambiguity entries become optional notes within that
exhaustive default, rather than enumerating the default repeatedly. Consumers
must branch on version; treating the empty 0.2 ambiguity array as an absence of
uncertainty is incorrect. This preserves 02a's order constraints for unchanged
regions/rules. It does not assert semantic incomparability or total reading order.

Tests compare every accepted/unresolved pair on 50/100/300-region layouts, plus
overlaps, unknown regions and spanning headings. Integer-bitset reachability is
computed once during validation; cycles, redundant edges and contradictions fail.
Common prose output becomes linear, but pair comparisons/temporary bitsets remain
potentially quadratic, and some DAG reductions inherently have quadratic edges.

Layout changes use smaller-adjacent-font-relative gaps at an inferred gutter,
retain coarse wide-gap evidence, and use column-local size/style statistics.
Heading evidence uses categorical font identity/frequency and isolation; it never
interprets substrings in font names. No Unicode/text correction occurs. Source
characters, native coordinates and v1 extraction remain unchanged.

## Freeze and development separation

The PDF hashes match the existing development registry:

| Document | Development-check page | Frozen evaluation page/layout | PDF SHA-256 |
| --- | ---: | --- | --- |
| Attention, arXiv v7 | 3 | 4: single-column prose with mathematics/figures | `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697` |
| BERT, arXiv v2 | 3 | 4: two columns, standalone and inline headings | `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e` |
| Nature TabPFN, publisher PDF | 2 | 5: two-column prose below charts | `6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013` |

PDF renders were inspected and [annotations.json](annotations.json) frozen before
modified code or evaluation predictions. SHA-256:
`8add8847a4576d66585a27121800ddc342ca6df68129e94fdabf71ac5c9f0bd2`, verified by
[freeze.json](freeze.json). The local freeze commit was `ad5653d`; its identical
published tree is in [`2c86657`](https://github.com/cagianoaless/understanding_engine/commit/2c8665704f4fdd20994500f1e7e56cf6d99115fb).
Publication metadata changed commit hashes, not frozen content.

One synthetic-informed configuration was used. [config.json](config.json) and
[plan.json](plan.json) were committed before evaluation; there was no threshold
grid or post-evaluation tuning. Training-page inspection found improved main
headings/prose but fragmented subscripts/diagrams and false figure-label/page
headings. A spanning-heading synthetic failure exposed lost coarse-gap evidence;
that was fixed before the controlled comparison. Final synthetic checks passed.

Experiment 004's Attention 2, BERT 2 and Nature 3 pages were **not** used for
tuning or new validation and were not rerun. Their known failures motivated the
hypotheses only. Experiments 001–004 and held-out material remain byte-identical.
The new pages are fresh relative to Experiment 004, not fresh papers: these
documents have prior development/spacing exposure. Training and evaluation
pages are disjoint; neither cohort is held-out ground truth.

## Representation scalability

`evaluation/structure_benchmark.py` extracts and executes the actual unmodified
02a pair-generation block. Each size/layout/representation uses a fresh process,
three repetitions, and canonical JSON serialization. Time below is the median
for order construction plus serialization. Output is **order payload only**,
excluding glyphs, source validation and the original expensive ambiguity validator.
Peak RSS is the whole process including imports and all repetitions, not
incremental allocations. Final measurements ran after paired evaluation completed
on a shared macOS arm64 host, Python 3.11.13, eight logical CPUs. No dedicated
CPU, cross-machine significance or universal speedup claim follows.

| Layout; regions | Original / compact ms | Original / compact bytes | Original / compact peak RSS MiB |
| --- | ---: | ---: | ---: |
| Single; 50 | 3.334 / 0.520 | 308,255 / 12,560 | 34.50 / 32.30 |
| Single; 100 | 12.915 / 1.869 | 1,246,455 / 25,160 | 41.00 / 32.53 |
| Single; 300 | 121.402 / 16.028 | 11,359,055 / 75,959 | 126.20 / 32.89 |
| Two columns; 50 | 3.695 / 0.471 | 322,632 / 12,308 | 34.48 / 32.44 |
| Two columns; 100 | 15.960 / 1.586 | 1,303,957 / 24,908 | 41.56 / 32.47 |
| Two columns; 300 | 142.264 / 14.237 | 11,876,557 / 75,705 | 127.67 / 32.94 |

At 300 two-column regions, 22,350 accepted edges and 22,500 explicit ambiguity
records become 298 reduced edges plus the unresolved declaration: 99.36% fewer
order bytes, with identical known/unknown pair semantics. This does not measure
or guarantee whole-pipeline memory reduction. Full-contract synthetic tests also
construct real 50/100/300-region PDF pages and validate their 0.2 overlays.
[scalability.json](scalability.json) retains raw repeats, block fingerprint and
units. Preliminary timing runs remain outside Git; final measurements were
rescheduled after the paired workers to avoid our own background CPU activity.

## Paired evaluation

Both engines receive identical cached v1 extraction bytes from the unchanged PDF
parser. PDF hashes and extraction provenance are checked before execution and
input hashes again afterward. Cached extraction avoids regenerating source units;
the complete source bytes/settings are preserved. Each engine reconstructs one
selected page in a fresh worker with a predeclared 300-second limit. All six
workers returned 0. No failed output or annotation was repaired.

The unmodified Experiment 004 scorer is reused: greedy one-to-one IoU >=0.5,
all predicted centers in frozen windows, accepted-edge transitive closure, and
frozen point-to-line alignment. It is not globally optimal matching. All 18
region references, 15 order pairs and 11 paragraph decisions stay in denominators;
there are no post-hoc exclusions. Heading TP/FP/FN additionally counts missing,
mislabelled and spurious heading regions. Undefined precision is reported as n/a.

| Document/layout | Regions matched / predicted / reference, 02a → 02b | Location precision / recall, 02a → 02b | Heading TP / predictions / references, 02a → 02b |
| --- | --- | --- | --- |
| Attention, single/math | 5/5/5 → 5/5/5 | 1.000/1.000 → 1.000/1.000 | 0/0/2 → 2/2/2 |
| BERT, two-column prose | 4/4/5 → 5/5/5 | 1.000/0.800 → 1.000/1.000 | 0/0/2 → 2/2/2 |
| Nature, publisher/charts | 5/11/8 → 8/8/8 | 0.455/0.625 → 1.000/1.000 | 2/2/3 → 3/3/3 |
| Aggregate windows | 14/20/18 → 18/18/18 | 0.700/0.778 → 1.000/1.000 | 2/2/7 → 7/7/7 |

Heading recall is 0/2 → 2/2, 0/2 → 2/2 and 2/3 → 3/3 respectively; original
precision is n/a on Attention/BERT, 2/2 on Nature. Proposed precision is 2/2,
2/2 and 3/3. Type agreement across all reference regions rises 11/18 → 18/18.
These are agreements with selected **agent** labels, not established accuracy.

| Document/layout | Correct order / pairs, 02a → 02b | Correct paragraph decisions / pairs, 02a → 02b | Source units retained once, both |
| --- | --- | --- | ---: |
| Attention, single/math | 4/4 → 4/4 | 2/3 → 2/3 | 2,107 |
| BERT, two-column prose | 2/4 → 3/4 | 4/4 → 4/4 | 4,039 |
| Nature, publisher/charts | 2/7 → 6/7 | 3/4 → 3/4 | 6,369 |
| Aggregate | 8/15 → 13/15 | 9/11 → 9/11 | 12,515 |

Both engines have zero observed inversions; two proposed cross-column transition
pairs remain unresolved and count as incorrect. Paragraph TP=3, FP=1, FN=1 for
both engines (precision/recall 3/4), with two unaligned probes retained as errors.
No paragraph improvement is established.

### Runtime, complete overlay size and memory

One measurement per engine/document, not a timing study. Source reading is outside
the timer; parsing/validation of the full cached extraction, page reconstruction,
contract validation and serialization are timed. RSS includes the entire worker,
imports and scoring. Full cached documents differ in size, so these are not
isolated per-page throughput measurements. No original PDF parsing is timed.
Early paired timings also overlapped preliminary benchmark workers on the shared
host. Treat these as execution records, not causal speedup estimates; the final
representation-only table was measured after all paired workers completed.

| Document | Seconds, 02a → 02b | Complete JSON bytes, 02a → 02b | Peak worker RSS MiB, 02a → 02b |
| --- | ---: | ---: | ---: |
| Attention | 10.742 → 6.168 | 472,584 → 424,023 | 221.59 → 228.84 |
| BERT | 10.280 → 10.345 | 808,821 → 796,333 | 333.06 → 333.11 |
| Nature | 18.958 → 18.648 | 4,967,650 → 1,422,935 | 550.55 → 554.94 |

Nature accepted edges fall 4,487 → 305 and explicit ambiguity records 7,916 → 0
(unknown pairs remain represented by the universal rule). Geometry also changes,
so this whole-overlay comparison does not isolate representation alone. BERT is
slightly slower and all proposed workers have slightly higher observed peak RSS.
These are reported regressions/limits of the measurement, not evidence of a
statistically established slowdown. Full-source JSON validation/allocation still
dominates resource use. Order-only savings do not imply full-pipeline savings.

## Errors, regressions and interpretation

- In the frozen windows, all proposed regions/types match the annotations. BERT's
  opaque-font headings and Nature's narrow-gutter prose improve; cross-column
  order is still deliberately unasserted. Correct matches and all failed original
  decisions are retained in [review-decisions.json](review-decisions.json).
- Two frozen paragraph probes cannot align under the fixed rule. Attention's
  `(200,660)` and `(200,670)` choose the same line. Nature's `(200,515)` lies beyond
  the short line's right edge (173.82) plus the 15-unit allowance. These are
  measurement/annotation limitations, not corrected or rescored results.
- Post-evaluation overlays expose **false heading candidates on Attention's
  equation tokens**, outside the frozen windows, from rare mathematical font
  identities. Those false candidates are absent from the original producer's
  corresponding equation area: an observed qualitative regression, not covered
  by the favorable window heading score. No new gold labels were invented.
- Nature has 141 whole-page candidate regions and eight heading candidates;
  chart panel letters and page furniture can be false headings. Eleven line
  fragments are spanning/unassigned, some legitimate. No verified chart-region
  or complete-page annotation exists, so these counts are not accuracy metrics.
- Training-page overlays also show fragmented subscripts, hanging-indent/list
  splits and diagram labels treated as ordinary paragraphs. Continuous spanning
  headings pass synthetic tests, but unusually large word gaps can still split
  them. Rare italic prose and same-font/same-size headings remain problematic.
- All glyph-associated units, unusual mappings and unknown orientations remain
  source-linked. Traceability validation establishes internal retention, not
  correctness of the PDF's Unicode mapping or visual interpretation. No `(cid:80)`
  repair, equation recognition, table reconstruction or semantic correction occurs.

The selected results support the new opt-in representation and bounded text-layout
changes. They do **not** justify silently replacing 0.1, claiming full-document
robustness, or calling the familiar development papers independent validation.

## Reproduction and checks

[commands.json](commands.json) records the exact executed parent/worker commands.
Use the same local PDFs and original cached extraction artifacts (hashes in
[summary.json](summary.json)); regenerate caches with the unchanged v1 parser
and pinned environment if needed, checking hashes before comparison.

```sh
uv run --frozen --offline python evaluation/experiments/005/run.py \
  --pdf attention=/local/1706.03762v7.pdf \
  --pdf bert=/local/1810.04805v2.pdf \
  --pdf tabpfn_nature_2025=/local/s41586-024-08328-6.pdf \
  --extraction attention=/local/attention-extraction.json \
  --extraction bert=/local/bert-extraction.json \
  --extraction tabpfn_nature_2025=/local/tabpfn_nature_2025-extraction.json \
  --output-dir /tmp/structure-005-new
```

The destination must be new. Full JSONs, PDFs, renders, raw worker results and
preliminary benchmark runs remain outside Git; [artifact-manifest.json](artifact-manifest.json)
records hashes/sizes. Compact summaries, decisions, source hashes, logs, frozen
settings and [environment.json](environment.json) are committed. Timing outputs
are execution metadata, never deterministic `structure.json` fields.

Full local suite: **171 passed**, zero failures/skips, Python 3.11.13/pytest 8.4.2,
7.52 seconds. [Full GitHub CI on the frozen implementation](https://github.com/cagianoaless/understanding_engine/actions/runs/42141195103)
also passed **171 tests**, Ubuntu 24.04/Python 3.11.13, 15.85 seconds. The original
136 tests remain passing with 35 new robustness/scalability cases. Final report
revisions trigger the same unchanged workflow. Test times are not PDF benchmarks.
[validation.json](validation.json) verifies 50 protected hashes, original 02a
code/schema, the PDF parser/extraction v1, Experiments 001–004 and held-out files.
No dependencies, original source units, old experiments or CI configuration changed.

## Proposed controlled model comparison (not implemented)

Complex chart/math layouts remain inadequate despite the selected prose-window
improvements. A small, separate layout-model comparison is reasonable **after
human reference checks and a footprint/license audit**. It is not an integration
decision or a superiority claim.

Candidate to audit: Docling 2.148.0, standard PDF layout path, CPU only, with OCR,
VLMs, remote services and formula/table reconstruction disabled. Its
[versioned package metadata](https://pypi.org/pypi/docling/2.148.0/json) delegates
to a standard dependency extra; the [official FAQ](https://docling-project.github.io/docling/faq/#which-model-weights-are-needed-to-run-docling)
states PDF model artifacts are required. We have **not** measured its installed
footprint or demonstrated that it fits the following proposed caps:

- Separate environment/lockfile; no production dependency changes. Preflight
  inventory of the complete dependency graph and installed sizes, then explicit
  package/weight names, revisions, SHA-256 and separate licenses.
- At most **2 GiB combined downloads**, **4 GiB installed/cache disk**, **4 GiB
  process-tree RSS**, **four CPU threads**, **120 seconds/page**, six new development
  pages (two per paper), with separate cold-load and warm measurements. No GPU.
  Reject/stop at a cap instead of silently expanding it; these are budgets, not
  claims that the candidate meets them. Audit metadata before any authorized
  download, install or run; require sufficient available host RAM/disk.
- Freeze new human-checked region/order annotations and configuration before
  outputs. Keep existing 004/005 pages exposed; no tuning/held-out reuse. Compare
  the frozen deterministic candidate and model on identical source bytes,
  including missing results and resource failures in denominators.
- Retain native model output, exact coordinate transforms and source-character
  grounding failures. Model text is not a corrected extraction or unquestionable
  truth. Require demonstrable layout gains without loss of traceability before
  considering adoption. If footprint, licensing or grounding fails, retain the
  deterministic baseline and report the failed comparison.

No such parser/model, OCR engine, neural package or weights were downloaded,
installed or executed in Milestone 02b.
