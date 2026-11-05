# Experiment 003 — Cross-document spacing generalization

**Decision:** retain `relative_0.125` as a candidate for a subsequent controlled,
opt-in implementation and independent validation. This run does **not** justify
adopting it as the production default. No production setting was changed.

## Source, environment and frozen protocol

The official publisher version of **Accurate predictions on small data with a
tabular foundation model**, Hollmann et al., Nature 637, 319–326 (2025), DOI
[10.1038/s41586-024-08328-6](https://doi.org/10.1038/s41586-024-08328-6), was
downloaded from [Nature's PDF link](https://www.nature.com/articles/s41586-024-08328-6.pdf).
It contains 23 PDF pages, including methods and extended data, and is 16,957,699
bytes. Its SHA-256 is:

```text
6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013
```

`source.json` records the URL, effective URL, HTTP status, article and embedded
PDF metadata, acquisition time, and licensing evidence. The publisher states
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with possible separate
third-party credits. The PDF remains outside Git and was not modified, repaired,
or replaced. It is registered in `evaluation/development/manifest.json`, not the
held-out manifest. Text/crop attribution is to the authors and publisher; crops
and transcriptions are evaluation derivatives of the unchanged PDF.

Baseline repository commit: `3a903b29eda7942064aa73ce8f0ba4e7bbafe211`.
Python: **3.11.13**. Package versions and code/lockfile hashes are preserved in
`environment.json` and `summary.json`; no dependencies were changed.

Exactly three candidates were frozen in `plan.json`:

| Candidate | Horizontal spacing setting |
| --- | --- |
| `absolute_3` | `x_tolerance=3` |
| `absolute_2` | `x_tolerance=2` |
| `relative_0.125` | `x_tolerance_ratio=0.125`; baseline `x_tolerance=3` remains in the settings dictionary and is superseded for word grouping |

All other settings remain the existing baseline's settings. No additional
thresholds, search, OCR, model calls, normalization, or text correction occurred.

Thirty single-line regions were transcribed from PDFium-rendered images before
candidate text was generated. Backend geometry was used only to locate complete
glyphs and record fonts/sizes. `annotations.json` contains document hash, page,
native bounding box, expected text, category and verification status per sample.
The selection spans 20 pages: 1–4, 6–14, 16–18 and 20–23. Font sizes range from
approximately 4.95 to 26 points, with Harding, GraphikNaturel and HelveticaNeue
families, including bold, semibold and italic styles.

All annotations are **`agent_visual_checked`**; none are human-verified ground
truth. The annotation SHA-256 frozen before scoring is
`4cd789c46848fe1cead051a46af4a8fc11d4e324d0dfbb4dc2f1b05fa158be3f`.
`freeze.json` also fixes the plan, source metadata, page geometry and review-sheet
hashes. No frozen annotation was edited, dropped or rescored after evaluation.

## Accounting and observed results

The unchanged `evaluation/spacing.py` was reused. Its original result is retained
in `raw_results.json`. `run.py` is experiment-only orchestration and reporting;
it does not modify the common evaluator or parser.

The common metric scores ASCII spaces only when every non-space code point
matches exactly. The separate report accounting adds **all frozen reference
boundaries**, including those in unscoreable samples, because the existing common
aggregate only totals boundaries in scoreable rows. That denominator limitation
is preserved explicitly rather than silently changing the common implementation.
`results_by_sample.json` retains every result and gives literal Unicode diff
opcodes, fonts, coordinates and category. No compatibility normalization, case
folding, ligature expansion or line-break correction is applied.

**All three candidates produced byte-identical text for each of the 30 regions.**

| Candidate | Exact matches | Missing spaces* | Extra spaces* | Expected spaces: all samples | Expected no-space boundaries: all samples | Non-space Unicode mismatch samples | Unscoreable samples |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `absolute_3` | 24/30 | 0 | 0 | 278 | 1,279 | 6 | 6 |
| `absolute_2` | 24/30 | 0 | 0 | 278 | 1,279 | 6 | 6 |
| `relative_0.125` | 24/30 | 0 | 0 | 278 | 1,279 | 6 | 6 |

\* Space-error counts are measurable on **24 samples only**, containing 215
expected spaces and 992 no-space boundaries. They are **unknown** on the other
six samples. Their remaining 63 expected spaces and 287 no-space boundaries stay
in the all-sample reference totals. Zero measured errors must not be read as
zero errors over all 30 samples. No unexpected line breaks occurred.

Results below are the same **for each of the three candidates**; `summary.json`
also preserves all 18 candidate/category records separately.

| Category | Samples | Exact | Expected spaces, all | Expected no-space boundaries, all | Non-space mismatch / unscoreable | Measured missing / extra* |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Body text | 6 | 5/6 | 44 | 223 | 1 / 1 | 0 / 0 |
| Figure captions | 6 | 5/6 | 67 | 297 | 1 / 1 | 0 / 0 |
| Mathematical symbols | 4 | 2/4 | 41 | 142 | 2 / 2 | 0 / 0 |
| References | 4 | 2/4 | 44 | 199 | 2 / 2 | 0 / 0 |
| Section headings | 5 | 5/5 | 15 | 114 | 0 / 0 | 0 / 0 |
| Table captions | 5 | 5/5 | 67 | 304 | 0 / 0 | 0 / 0 |

## Problems found; no post-hoc repairs

Post-evaluation magnified source-image review found four mistakes in the frozen
**agent annotations**, rather than threshold-specific extraction failures:

| Sample | Source region | Observed discrepancy |
| --- | --- | --- |
| `s05` | Page 3, body, 8.25 pt | Agent omitted the printed word `tasks`. |
| `s12` | Page 8, reference, 6 pt | Agent typed lowercase `a`; the PDF prints uppercase `A`. |
| `s14` | Page 8, reference, 6 pt | Agent typed `Breiman`; the PDF prints `Breimann`. The printed spelling was not corrected in parser output. |
| `s24` | Page 16, figure caption, 7 pt | Agent typed `Shapley`; the PDF prints the stylized `SHapley`. |

The other two mismatches concern representation, not a measured spacing error:

- `s17`, page 10, 8.25 pt: visual transcription uses mathematical tilde U+223C;
  the PDF glyph maps to ASCII tilde U+007E. The glyph still looks mathematical.
- `s19`, page 12, 8.25/4.95 pt: visual transcription uses superscript U+00B2;
  the PDF stores a separate U+0032 glyph at superscript coordinates. Glyph text
  and geometry remain preserved; converting it to U+00B2 would be reconstruction.

These diagnoses are also agent observations, not human-verified ground truth.
All six failures remain frozen and counted for every candidate. Corrected
annotations would require a separately versioned, independently reviewed follow-up;
they were not used to improve this experiment's scores. Mathematical spacing
ambiguities were recorded before scoring. No equation recognition or Unicode
recovery was implemented. See `post_evaluation_diagnostics.json` for the source
glyph encoding evidence and space counts.

## Comparison with Experiment 002

The cohorts remain separate. Experiment 002's real samples were agent-checked;
its synthetic lines were authored design cases. Neither cohort is human ground
truth, and neither is pooled with this new paper.

| Document/cohort | `absolute_3`: exact; missing/extra | `absolute_2`: exact; missing/extra | `relative_0.125`: exact; missing/extra |
| --- | --- | --- | --- |
| Attention, 16 agent-checked regions | 4/16; 110/0 | 16/16; 0/0 | 16/16; 0/0 |
| BERT, 9 agent-checked regions | 7/9; 4/0 | 9/9; 0/0 | 9/9; 0/0 |
| Synthetic, 54 authored lines | 27/54; 56/0 | 39/54; 22/56 | 54/54; 0/0 |
| Nature paper, 30 agent-checked regions | 24/30; 0/0* | 24/30; 0/0* | 24/30; 0/0* |

On this new PDF, relative 0.125 shows no observed spacing regression on the
scoreable regions, but also no comparative improvement. Absolute 2 introduces no
measured unnecessary spaces here, unlike its 56 inserted spaces in Experiment
002's synthetic matrix. No sampled font size or region exhibits a spacing failure
specific to one threshold. The six mismatches occur identically for all settings.

There are **285 literal ASCII-space glyph units in 29 sampled regions**; the
remaining region is the single-word heading “Methods”. Explicit whitespace can
already force word boundaries independently of an x-gap threshold. This likely
helps explain identical outputs and means this PDF weakly tests implicit-gap
reconstruction. The count alone does not prove that every intended boundary has
an explicit source space. The line selection was purposive, not random; four
annotation mistakes further demonstrate why agent transcription cannot be ground
truth. These are important limitations of the evidence, not reasons to discard
samples or tune on this document.

## Recommendation and limits

**Observed:** relative 0.125 preserved the same scored text as both absolute
settings across this new publisher PDF's sampled fonts and regions. There was no
measured regression in 24 scoreable samples. Experiment 002 still supplies its
main comparative advantage over absolute thresholds.

**Supported recommendation:** keep relative 0.125 as the next experimental
candidate for a controlled, opt-in implementation and independent validation.
Do not promote it to the production default on these results. Follow-up should
use independently human-verified references and additional documents that
actually stress implicit spaces and mixed typography, without using held-out
documents to tune settings.

**Unverified assumptions:** the two glyph-representation interpretations and
transcription diagnoses have not been independently checked by a human. This
single development paper does not establish statistical generalization, full-PDF
accuracy, reading order or mathematical reconstruction. No such claims are made.

## Validation and reproduction

- Evaluation command exited **0**. All three configurations used the same PDF
  hash, frozen 30 coordinates and expected strings. No samples were removed.
- An unchanged second run also exited **0**. All five external artifacts (raw
  results, per-sample results, character fingerprints, raw summary and their hash
  manifest) matched the first run byte-for-byte.
- The complete 23-page authoritative glyph-field fingerprints, covering 94,163
  units, matched before/after evaluation. `character_fingerprints.json` records
  per-page hashes and counts; no character text was changed.
- Runtime source, contracts, dependency lock, common evaluator, tests and held-out
  data are unchanged. Protected-file checks are in `validation.json`.
- Experiment 001's original artifacts and ZIP and Experiment 002's checked-in
  records, original raw results and review ZIP remain unchanged by hash.
- Existing offline suite: **81 passed, 1 failed**, exit code **1**. The failing
  test is `test_annotations_have_explicit_development_provenance` at
  `tests/test_spacing.py:123`. It asserts that Experiment 002's two document IDs
  equal the entire development manifest. Required registration of this third
  development document violates that exact-set assumption. The test was not
  rewritten or bypassed in this evaluation task; `logs/pytest.log` preserves the
  failure. This is a manifest-provenance test limitation, not a detected spacing
  regression. A separate maintenance change is needed to allow a growing registry.
- One acquisition mistake is documented in `logs/acquisition.log`: a metadata
  read occurred while curl was still downloading and reported a truncated stream.
  The completed PDF was subsequently hashed and inspected successfully. No
  candidate was evaluated on the partial download; no PDF repair occurred.

Run from the repository root, using the unchanged publisher bytes and an unused
external output directory:

```sh
.venv/bin/python -B evaluation/experiments/003/run.py \
  --pdf /path/to/s41586-024-08328-6.pdf \
  --output-dir /tmp/understanding-engine-experiment-003-new

uv run --frozen --offline pytest
```

`command.txt` records the exact executed evaluation command. `commands.json`
records acquisition, evaluation and test commands; `environment.json` records
the versions. A rerun verifies the document and all frozen-file hashes before
scoring, accepts only the three configurations and refuses existing destinations.
Raw scores should reproduce; execution paths and repository-commit metadata may
differ on a later checkout. Original PDF, page renders and large review artifacts
remain outside Git. All recorded transcriptions retain `agent_visual_checked`.
