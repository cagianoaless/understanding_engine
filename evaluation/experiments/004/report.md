# Experiment 004: minimal document structure, three development pages

Milestone 02a supplies a separate deterministic structure overlay. **This is an
initial development implementation, not a validated full-document layout system.**
All comparisons below use `agent_visual_checked` annotations; there are **zero
human-verified references**, no teacher-model invocation and no held-out run.

## Implementation and dependency

PR #1 was unmerged and main contained only the bootstrap when work began. The
implementation therefore starts at its approved current commit
`cef6e2bfc837cdbb95d252738d648276ed6d0422`, on
`feat/milestone-02a-structure`. [PR #4](https://github.com/cagianoaless/understanding_engine/pull/4)
is stacked on PR #1's branch; it must be retargeted after that dependency is
merged by a human. Neither PR is merged automatically.

The [contract and algorithms](../../../docs/structure.md) add no dependencies.
The original PDF parser, `x_tolerance=3`, v1 schemas, lockfile and historical
experiments remain unchanged. Structure contains no rewritten text: it references
original glyph-associated units and preserves page geometry. Figure/equation
roles are unclassified; page-wide unresolved-content notices acknowledge that
v1 cannot locate non-text graphics. These notices are not detected figure boxes.

The reproducible published implementation is
[`8babb4c`](https://github.com/cagianoaless/understanding_engine/commit/8babb4c9042cda40a1dfd9cafac7b4d19dda70ce),
Git tree `2466a56c5aa31a77e2cc881be0c05ad6e2ad6b4f`, implementation fingerprint
`878e1cdecc6a759c8400ea56be58f477ef21b4b1d3d6c8c9c57fb0f446f5d253`.
Execution used local commit `0b326d28ac482f59343d183ed4066c10ad037c0b` with that
identical tree. The GitHub integration assigned different commit metadata after
shell Git authentication failed; this changes commit hashes, not files/results.
The original local history remains in `refs/experiment-history/m02a-prepublication`.

## Selection and frozen annotations

PDF bytes were hashed against the existing development registry before use:

| Document | Page | Layout | PDF SHA-256 |
| --- | ---: | --- | --- |
| Attention Is All You Need, arXiv v7 | 2 | Single-column prose, numbered headings | `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697` |
| BERT, arXiv v2 | 2 | Two columns, bullets, headings | `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e` |
| Nature TabPFN, official publisher PDF | 3 | Two columns below a large vector figure/caption | `6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013` |

The coding agent inspected page renders and froze native-coordinate windows,
16 region boxes/types, 13 order hypotheses and nine paragraph-adjacency decisions
**before structure code or predictions existed**. Local freeze commit was
`3f14c952e230015d8145e8d768c6aa792e86b4a8`; the identical published freeze tree is
in [`d43c813`](https://github.com/cagianoaless/understanding_engine/commit/d43c813c0ade5f929f1ee44b8fdde2a5e360fd03).
[annotations.json](annotations.json) has SHA-256
`107aeb2eb99d4a52931916818236fbe660b25ab35d273359324dc0be1a7cfd6b`, matching
[freeze.json](freeze.json). Selection and labels were not changed after scoring.
Boxes are approximate visual annotations, not independently adjudicated truth.
The [configuration](config.json) was committed before the first structure run;
there was no real-page threshold search or subsequent implementation tuning.

Only the frozen windows score text regions; other page content is outside that
quality denominator. All selected-page characters are checked for traceability.
The original parser extracts whole PDFs to preserve original page numbers and
IDs, but the structure layer processes only the three selected pages. That is
not a full-document structure evaluation.

## Measurements

Location matching uses frozen IoU >= 0.5 and greedy descending-IoU assignment,
with explicit ID ties. This is a documented simplification of the larger
design's proposed optimal assignment, not a claim of an optimal scorer. Every
predicted text/unknown-region center inside the windows counts; unmatched
predictions are false positives and unmatched annotations are misses. Ordering
uses accepted-edge transitive closure; missing regions and abstentions fail the
pair. Paragraph points align to nearby line geometry under the frozen rule;
unmatched decisions count as errors. No Unicode/text normalization is involved.

| Document/page | Matched / reference regions | Predictions; false positives | Correct types / matched | Order pairs correct / total | Paragraph decisions correct / total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attention / 2 | 5 / 5 | 5; 0 | 5 / 5 | 4 / 4 | 3 / 3 |
| BERT / 2 | 7 / 7 | 8; 1 | 4 / 7 | 5 / 6 | 3 / 3 |
| Nature / 3 | 1 / 4 | 8; 7 | 1 / 1 | 0 / 3 | 2 / 3 |
| Total | 13 / 16 | 21; 8 | 10 / 13 | 9 / 13 | 8 / 9 |

Aggregate location precision is 13/21 (61.9%), recall 13/16 (81.25%). Document
macro precision/recall are 66.7%/75.0%; these summaries do not establish accuracy
against human references. Three reference regions were missed. Labels agree for
10/16 total references: of six annotated headings, two match as headings, three
match as paragraphs and one has no matched region. Eight of ten annotated
paragraphs match as paragraphs; two have no matched region. All eight unmatched
predictions are paragraphs. Ordering has zero observed inversions, four failed
pairs and no exclusions. Zero inversions does not imply correct ordering.

For paragraphs: four expected breaks, five expected joins; TP=4, FP=1, FN=0,
precision 4/5, recall 4/4. All nine pairs align; no failures leave the denominator.
These nine decisions are far too few to establish paragraph quality.

Column counts are labelled 1/2/2, matching the visual page-level hypotheses.
This does **not** establish correct column separation: Nature still has false
cross-column fragments. The figure reference has **0/1 localized detections**;
it is reported as unsupported, not quietly omitted from the experiment.

All **13,056** selected-page units occur once in region references
(Attention 3,628; BERT 3,859; Nature 5,569). Source-aware validation resolves
references, checks exact source byte hashes, original metadata, bounding unions,
ownership and DAG consistency. Input extraction/PDF bytes remain unchanged.
All three real overlays reproduced byte-for-byte on a second reconstruction
from the same extraction bytes and configuration; see
[repeat.json](repeat.json). Synthetic tests additionally vary paths/hash seeds.

## Correct decisions and failures

- Attention: all five annotated introduction regions, their labels, four order
  relations and three paragraph decisions agree with the frozen visual labels.
  This is the easiest selected layout and a small window, not the whole paper.
- BERT: two columns remain separate and the seven annotated boxes match. Three
  headings are labelled paragraphs. The backend font name is
  `WQTLNC+NimbusRomNo9L-Medi`, which does not contain `bold`; subsection sizes
  equal body size, while the larger section is only about 1.096 times body size,
  below the fixed 1.15 rule. This is a typographic-evidence limitation, not a text
  decoding error. A separately fragmented bottom-right continuation contributes
  one false-positive paragraph in the frozen window.
- BERT's left-column-to-right-heading transition is unresolved, so one order
  pair fails. That abstention is intentional: column positions alone do not
  prove a transition. It stays an error against this annotation, not an exclusion.
- Nature: labels report two columns, but some body fragments span their gutter.
  Four inspected gaps at the inferred gutter measure approximately
  9.825–9.888 native units, just below the row split threshold 9.9 (1.2 times
  8.25-point font size). Those fragments stay unassigned to a column and become
  isolated region candidates. The overlay visibly interleaves prose across
  columns, producing seven false positives and three misses in the windows.
  There are 19 spanning/unassigned line fragments overall, including legitimate
  figure content: not all 19 are established errors. This line-fragment rule is
  separate from production word-gap reconstruction; no production setting changed.
- Nature's second heading is mixed with adjacent-column text; the paragraph
  pair at native points `(400,622)` and `(400,632)` is incorrectly split.
  Two order failures arise from missing matched regions, and the third also
  requires an unasserted column transition. The vector figure is not localized.
- Figure labels and equations may be treated as candidate paragraphs. Their
  source units and uncertainty remain present, but structural role/ordering
  within diagrams and mathematics is not verified by this implementation.

Post-run visual review used region overlays, preserved outside Git; it did not
change annotations or scores. [review-decisions.json](review-decisions.json)
contains each correct/incorrect region, order and boundary decision, plus false
positives. Full source-reference overlays and original raw decisions remain
outside Git, indexed by [artifact-manifest.json](artifact-manifest.json).

## Reproduction, validation and next steps

Use the locked Python 3.11.13 environment and the three exact local PDFs.
[commands.json](commands.json) records the executed argv and exit code; this
equivalent command writes all large artifacts outside the repository:

```sh
uv run --frozen --offline python evaluation/experiments/004/run.py \
  --pdf attention=/local/1706.03762v7.pdf \
  --pdf bert=/local/1810.04805v2.pdf \
  --pdf tabpfn_nature_2025=/local/s41586-024-08328-6.pdf \
  --output-dir /tmp/structure-experiment-new
```

The output directory must be new. The runner checks frozen annotations and all
PDF hashes before extraction. Existing PDFs were used without download/repair;
no PDF, render, complete extraction or large structure artifact is committed.
[summary.json](summary.json) records dependencies, code/configuration and hashes.
Execution returned 0. Stderr retains existing parser warnings about unapplied
Nature CropBoxes and a degenerate glyph on page 2; they are not corrected or
hidden. That page's warning arises because extraction reads the whole source.

Local full suite: `uv run --frozen --offline pytest`, Python 3.11.13,
pytest 8.4.2 on macOS arm64, **136 passed, zero failures/skips** (2.08 seconds).
All 93 existing tests pass alongside 43 new structure/scorer cases. A development
test-file typo briefly caused a collection error and was corrected before the
frozen implementation run; no observed extraction/evaluation failure was repaired.
The full existing [GitHub workflow passed on the implementation commit](https://github.com/cagianoaless/understanding_engine/actions/runs/42126719786):
**136 passed**, zero failures/skips, Ubuntu 24.04, Python 3.11.13, pytest 8.4.2
(4.11 seconds). Final documentation/evidence revisions also trigger the unchanged
workflow. Test timings are not parser performance measurements.

[validation.json](validation.json) records unchanged protected files, including
47 preserved hashes, production parser/settings, v1 schemas, dependency lock,
Experiments 001–003 and held-out data. The existing CI workflow is unchanged.
No model, OCR, GPU, semantic, UI, database, Docling/MinerU or table/formula
reconstruction is introduced.

Recommendation: retain this as a transparent experimental baseline. It meets
the tested traceability/reproducibility invariants, but **does not meet the larger
design's quality gates** and lacks human references. Next controlled work should
test gutter-aware fragmentation and font-name-independent heading evidence using
new authored regressions and independently verified development annotations.
Do not tune against the three reported pages and then describe them as independent
validation. Do not expand this result into a production or generalization claim.
