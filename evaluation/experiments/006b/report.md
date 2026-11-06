# Experiment 006b — frozen references complete; Linux prerequisite NO-GO

Issue #8 has a valid partial outcome: Stage A is complete; B is blocked because
no existing usable local Linux runtime was discovered; installation, smoke test
and comparison (C/D) were not run. This is not a model-memory or accuracy result.
See `preflight.md` for the measured discovery and its bounded scope.

The branch starts at PR #7 `0cebd59980b156499a60aee24d625f9203676cf8`.
Structure 0.2 remains pinned to `ba82b2c7f71604d5bcc2859b1a05de112723107d`;
its default configuration is recorded in `baseline-settings.json`. Docling
2.148.0 and the fixed Heron revision/inventory are unchanged. No production code,
dependency, extraction contract, Structure 0.2, historical experiment or held-out
document is modified. All 161 previously tracked files are hash-protected.

## Completed references and independent review package

Source-only annotations were frozen locally in commit
`555e4d4c582fdb6a7ce35d66739760b63a4bed36` before runtime investigation.
No structure predictions were inspected or generated for these pages.

| Development document | Physical pages | Layouts | Regions | Known order pairs | Paragraph decisions |
|---|---|---|---:|---:|---:|
| Attention, arXiv v7 | 6, 9 | Single-column math and tables | 18 | 11 | 7 |
| BERT, arXiv v2 | 6, 10 | Spanning table, two-column prose/math, references | 21 | 12 | 8 |
| Nature TabPFN | 15, 19 | Four chart panels, split caption, full-width table | 9 | 1 | 3 |
| Total | 6 pages | Scoped development windows | 48 | 24 | 18 |

`selection.json` records exclusions. These pages do not overlap Experiments
004/005, their training pages, or the earlier spacing samples. The PDFs were
already available locally; all three SHA-256 values match the unchanged registry
and Experiment 006. `source-inputs.json` records their exact bytes, URLs, local
paths and the original cached authoritative extraction used only for provenance
and paragraph-probe geometry. No original PDF was repaired or substituted.

All references are **agent_visual_checked**. **Human-verified count: zero.**
The independent human-review form is entirely pending and has no invented reviewer.
This is a package ready for human review, not a completed independent human review.

The external ZIP contains six raw pages, six overlays, scored-window crops,
geometry, annotations, scoring plan and review form. It is 4,744,612 bytes with
SHA-256 `b1ed02b722fb73e8c0dce480403c95a74a4b414e207663e2d645fba7c6552ab6`.
Location and member hashes are in `review-package.json`. A second build was
byte-identical. Copyrighted PDFs/renders remain outside Git; the ZIP is a local
artifact, not a publicly hosted download. `review_protocol.md` instructs an actual
human to inspect raw pages independently before comparing the agent's boxes and
relations, and to submit corrections as a new version without overwriting v1.

## Source traceability and scoring scope

Page boxes use native pdfplumber top-origin PDF points. Original media/crop boxes,
rotation, UserUnit and page dimensions are preserved in `page_geometry.json`.
For these six pages rotation is zero, UserUnit is one and crop/media coincide.
Raster transforms use actual pixel dimensions, including independent x/y rounding;
the review builder explicitly rejects unaudited transformations.

All 18 paragraph probes resolve to original source-character IDs and agree with
the annotated paragraph regions (`annotation-source-audit.json`). This checks
reference integrity, not candidate source-grounding accuracy. Prediction grounding
valid/missing/many-to-many/contradictory counts are **null, not_run**. No glyph IDs
or text were invented, and model text never replaced authoritative extraction.

`plan.json` fixes IoU 0.5 one-to-one region matching, label mapping, heading/caption
scores, selected order constraints and paragraph probes, failure denominators,
per-document/layout and macro reporting before predictions. Chart panels are four
separate localization units; table cells and chart labels are not nested truth
regions. One table-note classification is explicitly ambiguous; its localization
is retained. Optional image/table/caption order and some cross-column relations
remain unresolved. Windows exclude unannotated material rather than claiming
exhaustive page coverage. Existing parser text and Unicode are untouched.

## Unexecuted comparison and limitations

| Quantity | Structure 0.2 | Docling |
|---|---|---|
| Planned/executed pages | 6 / 0 | 6 / 0 |
| Region, heading, caption, paragraph and order metrics | not_run / null | not_run / null |
| Source-grounding measurements | not_run / null | not_run / null |
| Cold/warm runtime, peak memory, effective threads, output bytes | not_run / null | not_run / null |

All six planned pages remain registered; there are no executed samples and no
fabricated zero-accuracy scores, false-negative counts or resource measurements.
Host disk availability and eight logical CPUs do not establish enforceable
container limits. RAM access was denied; actual cgroup/swap/disk/CPU/timeout
enforcement was not testable. Synthetic gate tests cannot establish those gates.
Linux dependency sizes, installed/cache footprint, license compatibility,
offline isolation and model behavior remain unverified. No model or base image
was acquired. Experiment 006's macOS limit failure and 006b's missing Linux
runtime are separate blockers; neither is evidence that Docling exceeds 4 GiB.

The references themselves are small, agent-estimated and partially scoped. BERT
reference and Nature chart/table granularity may need human correction. Mathematical
Unicode recovery (including `(cid:...)`), OCR, formula recognition, table content
reconstruction and whole-document reading order are not assessed. These six
development pages cannot establish generalization or independent human accuracy.

## Validation and next step

`validation.json` and `logs/` record the full offline regression command/results;
`publication.json` records the dedicated PR and GitHub CI (for its explicitly
identified tested commit; subsequent publication metadata does not change code). The new tests check
freeze integrity, prior-file preservation, identifiers/source references, geometry,
fresh page selection, pending-human status, finite cgroup limits and boundary cases,
byte budgets, timeout/failure denominators and honest not_run reporting. Ordinary
tests import no neural stack and run without PDFs, a runtime or the review ZIP.

Before the freeze, source boxes/probes were checked against raw renders and the
review builder's unsupported PdfPage context-manager use was corrected. A uv
default-cache permission failure was resolved by selecting the existing writable
temporary cache, with frozen offline dependencies. Focused checks passed 19/19
at the freeze; the first complete suite subsequently passed 252/252. The final local run passed **255/255 tests**, with exit 0 and no stderr;
GitHub CI evidence is recorded separately in `publication.json`. No candidate failure was repaired.

An existing suitable Linux environment must be supplied or made available by the
user before resuming the model-free gates. Do not install a runtime or relax any
limit automatically. Independently review the frozen package; preserve this
NO-GO and any subsequent annotation revisions separately. No merge was performed.
