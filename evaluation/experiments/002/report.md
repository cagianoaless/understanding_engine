# Experiment 002: deterministic word-boundary investigation

Production decision: **retain `x_tolerance=3` and the existing application**.
Ratio 0.125 is a promising experimental candidate, not a validated new default.
There are **zero human-verified real samples** in this run. The 25 transcriptions
were visually checked by the coding agent against rendered PDF regions and are
explicitly marked `agent_visual_checked`. Under the project protocol, that does
not constitute manually verified ground truth. Human review remains required.

## Inputs and immutable baseline

- Attention Is All You Need, user-supplied arXiv 1706.03762v7;
  SHA-256 `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`.
- [BERT, arXiv 1810.04805v2](https://arxiv.org/abs/1810.04805v2), acquired manually
  from its versioned arXiv PDF URL;
  SHA-256 `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e`.
  The PDF is not committed or downloaded automatically by the evaluator.
- 54 authored synthetic lines from `tests/fixtures/spacing.pdf`, with intended
  text and construction parameters in `tests/fixtures/spacing_samples.json`.

Both real papers are explicitly development documents. The held-out manifest
remains byte-identical, SHA-256
`68587f4136bc75640c717308a6bc6c12da1d4ee12d16690e51b226155b2f5628`.

[Experiment 001's record](../001/baseline.json) preserves the original commit,
configuration, archive checksum, and artifact hashes. Its original external
JSON, text, run metadata, logs, and ZIP were verified and never rewritten.
The unchanged parser was also run on both development PDFs: both returned 0.
The Attention repeat's `extraction.json` and `paper.txt` matched Experiment 001
byte-for-byte. Full control outputs remain outside Git.

The user reported selective teacher-anchor matches of 7/16, 8/16, 16/16, and
16/16 for tolerances 3, 2.5, 2, and 1.5. Those 16 strings were not supplied, so
that diagnostic is recorded as reported evidence, not reproduced ground truth.
The 16 Attention regions below are **different samples**; their counts cannot be
compared directly with the teacher's 16 anchors.

## Method and scope

The candidate grid and selection gate are in `evaluation/spacing_plan.json`.
The nine candidates were fixed before the first comparison. The agent selected
16 Attention title/body/caption/footnote lines and nine short BERT regions
spanning two-column body text, headings, and multiple font sizes. Bounding boxes
and transcriptions were frozen before scoring; candidate results were not used
to change those annotations. These selective windows are not a comprehensive
paper-accuracy benchmark. BERT coverage is particularly small: 22 excerpt words.

The absolute rule splits when the horizontal gap exceeds its point threshold.
The backend's relative rule uses `x_tolerance_ratio * preceding_glyph.size`;
the absolute x threshold is then superseded for word grouping. For ratio 0.125,
the threshold is 1.25 points at 10-point type and 3 points at 24-point type.
Other text-map settings remain the baseline's settings, including disabled
ligature expansion and Unicode normalization. The production parser, schemas,
and dependency lock were not changed. The research evaluator copies settings
and verifies that candidate calls do not mutate source-character dictionaries.

The metric first requires exact equality of **all non-space Unicode code
points**. Unexpected line breaks, changed symbols, substitutions, and reordered
characters are unscoreable failures, counted explicitly. There is no fuzzy
matching, ligature expansion, dehyphenation, or semantic correction. For scoreable
single-line samples, ASCII spaces are counted at offsets between non-space code
points. Expected spaces absent in output are missing; surplus spaces, including
inside words and repeated spaces, are extra. Leading/trailing spaces also count.

Denominators: Attention has 137 annotated spaces and 755 internal no-space
boundaries; BERT has 13 spaces and 127 no-space boundaries; synthetic lines have
110 spaces and 842 no-space boundaries. These are conditional on the annotation
status above. Counts below are missing/extra space units, not full-document
accuracy percentages. Every candidate had zero unscoreable samples in this run.

## Results

| Rule | Attention: missing / extra | BERT: missing / extra | Synthetic: missing / extra |
| --- | ---: | ---: | ---: |
| Absolute 3 (baseline) | 110 / 0 | 4 / 0 | 56 / 0 |
| Absolute 2.5 | 59 / 0 | 0 / 0 | 36 / 28 |
| Absolute 2 | 0 / 0 | 0 / 0 | 22 / 56 |
| Absolute 1.5 | 0 / 0 | 0 / 0 | 8 / 60 |
| Relative 0.10 | 0 / 0 | 0 / 0 | 0 / 168 |
| Relative 0.125 | 0 / 0 | 0 / 0 | 0 / 0 |
| Relative 0.15 | 0 / 0 | 0 / 0 | 2 / 0 |
| Relative 0.20 | 0 / 0 | 0 / 0 | 2 / 0 |
| Relative 0.25 | 39 / 0 | 5 / 0 | 60 / 0 |

Baseline exact matches: Attention 4/16, BERT 7/9, synthetic 27/54. Relative 0.125
matched 16/16, 9/9, and 54/54 respectively. Full aggregate counts, exact-match
counts, hashes, and verification levels are in `summary.json`.

The synthetic set covers Helvetica and Times-Roman at 6, 8, 10, 12, 18, and
24 points; positive tracking, negative AV/VA kerning, explicit source spaces,
implicit word gaps, punctuation, tight headings, and font-covered mathematical
symbols, accents, and ligatures. It reproduces the 2.49/2.68-point gap failure.
Lowering the absolute threshold splits large tracked words; a ratio of 0.10
does so too. Larger relative thresholds miss tight heading spaces. These are
observed candidate quality regressions, not failures of the unchanged parser's
existing regression suite.

Ratio 0.125 meets the numeric gate on these samples, but fails the required
human-verification gate. A small, deliberately authored synthetic matrix and
selective agent transcriptions do not establish robustness across new fonts,
spacing conventions, inline font changes, mathematics, or other papers. No
production change or new default is justified yet. Human review should confirm
or correct the annotations with a named reviewer; then the comparison should be
rerun, followed by additional independent development coverage. No held-out
tuning is authorized by this result.

## Failures and regression checks

The first new-test run had two failures because the authored fixture selected
lowercase Greek not covered by the bundled Vera font; those glyphs became NULs.
The fixture was corrected to use supported symbols, and the generator now
asserts font coverage. No extraction or mathematical-recovery code was changed.
The final suite passes **82 tests** on Python 3.11.13, including all 60 original
tests and 22 new metric, spacing, provenance, and immutability tests.

All 17 original fixture hashes are unchanged. The authoritative character
contract, runtime source, dependency lock, and held-out manifest are unchanged.
Rendered real crops and representative synthetic pages were inspected with the
already installed PDFium renderer. These visual checks are explicitly agent
checks, not human ground truth.

Unmapped glyphs such as `(cid:80)` remain a known limitation. Spacing evaluation
does not map these placeholders to mathematical Unicode or reinterpret them.
Preserving symbols here means retaining backend code points and glyph units,
not claiming the backend decoded every mathematical symbol correctly.

## Reproduction

Use the existing pinned Python 3.11 environment. Obtain the exact development
PDFs separately and verify their manifest hashes. The evaluator is offline and
refuses hash mismatches, unknown/duplicate document mappings, ambiguous sample
identities, and existing result paths. No dependencies or PDFs are fetched.
Choose unused output filenames, for example:

```sh
.venv/bin/python -B evaluation/spacing.py \
  --pdf attention=/path/to/1706.03762v7.pdf \
  --pdf bert=/path/to/1810.04805v2.pdf \
  --samples evaluation/development/spacing_samples.json \
  --output /tmp/spacing-real-new.json

.venv/bin/python -B evaluation/spacing.py \
  --pdf synthetic_spacing=tests/fixtures/spacing.pdf \
  --samples tests/fixtures/spacing_samples.json \
  --output /tmp/spacing-synthetic-new.json

uv run --frozen --offline pytest
```

The expected real samples remain unverified until a human compares their text,
spaces, punctuation, and Unicode with the supplied PDF crops. Do not relabel them
based on student/teacher agreement or a successful score. A named human reviewer
is required for any `human_verified` annotation. No teacher model is invoked by
this experiment or the application.
