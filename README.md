# Understanding Engine

Milestone 01: offline scientific PDF extraction using Python 3.11 and pdfplumber.
Milestone 02a adds a separate experimental geometric structure layer.
The package preserves positioned backend text units separately from derived page
text. No LLM, OCR, GPU, database, UI, or semantic analysis is included.

## Setup

Install Python 3.11 and [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --frozen --extra dev --python 3.11
uv run --frozen --offline pytest
```

Setup downloads the locked dependencies once. Parsing and tests require no
network access. `uv.lock` pins direct and transitive versions and artifact hashes;
`pyproject.toml` also pins direct requirements. Runtime dependencies are pdfplumber
and jsonschema; pytest, ReportLab, and pypdf are development dependencies. Runtime
does not import ReportLab or pypdf. ReportLab/pypdf regenerate synthetic fixtures.

For a runtime-only environment, use `uv sync --frozen --python 3.11` and
`uv run --frozen --offline --no-dev ...`. The development extra must be explicitly
selected for the tests on a fresh installation.

## CLI

From the repository root, this example uses a checked-in, distributable fixture:

```sh
uv run --frozen --offline understanding-engine tests/fixtures/unicode.pdf --output-dir output/unicode
```

For a paper, substitute its local path and choose a new output directory:

```sh
uv run --frozen --offline python -m understanding_engine /path/to/paper.pdf --output-dir output/paper
```

The destination must not already exist, even as an empty directory or symlink.
Use a different directory for each run. Output files are:

| File | Meaning |
| --- | --- |
| `extraction.json` | Deterministic, versioned character layer, derived lines/text, geometry, provenance, configuration, and warnings |
| `paper.txt` | UTF-8 derived text with explicit page headers and form-feed separators; blank pages retained |
| `run.json` | Paths, UTC start/end, elapsed time, configuration, statistics, warnings, and SHA-256 hashes of the other artifacts |

Exit codes: **0** = parsed with non-whitespace text; **3** = valid but textless
(artifacts still written); **2** = input, geometry, contract, publication, usage,
or unexpected failure. Mixed documents return 0 and identify every empty page.
All encrypted PDFs are rejected, including those with an empty user password.
A PDF without pages is invalid. No OCR is attempted on image-only pages.

Normal logs go to stderr and include event codes, document hashes, and relevant
page/character references. `--debug` includes tracebacks and verbose backend logs,
which may contain source content. There is no stdout data stream.

All files are staged in a sibling directory, flushed, validated, then published
with a single directory rename on the same filesystem. Fatal failures before
publication leave no destination. Existing results are never reused. A sibling
exclusive lock coordinates application invocations; an abrupt process termination
can leave a hidden staging directory or lock. Confirm no writer is active before
manually removing either. This is atomic publication on ordinary local
filesystems, not a guarantee of recovery from power loss or protection against
unrelated programs racing to write the destination. Failure diagnostics are on
stderr; failed runs do not publish a `run.json`.

## Python API and contracts

```python
from understanding_engine.pdf_parser import extract_pdf
from understanding_engine.output import parse_to_directory

extraction = extract_pdf("paper.pdf")
run = parse_to_directory("paper.pdf", "output/new-run")
```

Expected failures raise `ExtractionError` with a machine-readable `code`.
JSON Schema Draft 2020-12 files are installed with the package:
[extraction](src/understanding_engine/schemas/extraction.schema.json) and
[run](src/understanding_engine/schemas/run.schema.json), version **1.0.0**.
Validation also checks cross-references, contiguous page/index sequences, IDs,
derived-line consistency, status consistency, and finite/non-inverted geometry.
Non-finite/inverted backend geometry is fatal; zero-area and outside-page
character boxes are retained with explicit warnings. Raw PDF rectangle corner
order is preserved because reversed corners can be legal.

`characters` is authoritative only as a record of what the pinned backend
extracted. Each unit contains its original extracted Unicode (possibly multiple
code points), zero-based `backend_index`, ID, geometry, matrix, and font details.
IDs follow `<PDF_SHA256>:p<one-based-page>:c<zero-based-backend-index>`. They are
stable for identical PDF bytes and extraction environment. Backend version changes
can alter indices: retain parser provenance together with every reference.

`derived.text` and `derived.lines` come from pdfplumber's geometric TextMap with
explicit tolerances/directions. Line references follow source units, not Unicode
string offsets; a line bbox encloses its referenced units. A line with no source
units has a null bbox. Inferred spaces/newlines have no character reference.
The derived layer can omit source whitespace and change ordering; it is **not a
lossless reconstruction**. Unicode normalization, ligature expansion,
dehyphenation, correction, and character deduplication are disabled.
Neither backend extraction order nor geometric ordering is claimed to be reading
order. Rotated and multi-column derived text can be misleading.

Reproducibility means byte-identical `extraction.json` and `paper.txt` for the
same bytes, package version, Python/dependency versions, and settings. JSON uses
UTF-8, sorted keys, two-space indentation, and a final newline; coordinates are
not rounded. Paths, execution timestamps, and timings appear only in `run.json`.
The full deterministic payload remains in memory; pages release backend caches
as extraction progresses. Timings end after the first two artifacts are written,
before writing `run.json` and publishing the directory.

See [coordinate conventions](docs/coordinates.md),
[evaluation protocol](evaluation/protocol.md), and
[fixture provenance](tests/fixtures/README.md).

## Candidate document structure (Milestone 02a)

Use an existing, unchanged extraction file; the original PDF CLI is unchanged:

```sh
uv run --frozen --offline python -m understanding_engine.structure \
  /path/to/extraction.json --output-dir output/structure --pages 2
```

The new directory contains versioned `structure.json`, with source glyph
references, candidate lines/paragraphs/headings, basic columns, and partial
reading-order relations. It contains no corrected text. Omit `--pages` to process
all pages; supply `--config settings.json` to override explicit geometric settings.
Unknown orientation and possible non-text content remain visible in the output.
Cross-column order is deliberately unresolved. See the
[structure contract and limitations](docs/structure.md) and the
[three-page development report](evaluation/experiments/004/report.md).

## Known limitations

- Embedded text can be missing, incorrectly mapped, invisible, or out of order.
  Backend output is not ground truth; CID placeholders and unusual mappings may
  survive unchanged.
  For example, `(cid:80)` is an unmapped-glyph placeholder, not a recovered
  mathematical symbol. Mathematical Unicode recovery is outside Milestone 01b.
- The original parser performs no scientific layout, section, table, equation,
  prerequisite, or semantic reconstruction. The separate structure experiment
  provides geometric candidates only. Mathematical symbols are preserved only when the backend can
  decode them; two-dimensional formulas are not reconstructed.
- No claim to solve reading order, bidirectional/vertical text, complex scripts,
  rotated line order, or overlapping text. Derived text assumes top-to-bottom,
  left-to-right directions, including rotated glyphs.
- Extraction uses the MediaBox, does not filter to CropBox, and retains UserUnit
  without applying physical scaling. Axis-aligned boxes do not encode a glyph's
  complete outline; the backend character matrix is retained for diagnosis.
- Geometry validation detects malformed numeric structure, not whether a box
  accurately matches the rendered glyph. pdfplumber's TextMap interface is
  backend-specific and pinned; upgrades require regression review.
- No performance or extraction-accuracy claims on real papers, held-out
  documents, other operating systems, or large/malformed PDF populations have
  been established. Synthetic fixture tests are development evidence only.

Development and held-out manifests remain separate. The development manifest now
records two spacing-investigation papers; the held-out manifest is still empty
and unchanged. This milestone does not run teacher models or automatically change
extraction based on their suggestions.

## Milestone 01b: development spacing investigation

The production parser and its version 1.0.0 character contract remain unchanged.
`x_tolerance=3` is retained pending human verification of real text samples.
The research-only [spacing comparison](evaluation/spacing.py) measures missing
and extra ASCII spaces independently for a fixed candidate grid. Non-space
Unicode changes and unexpected line breaks are reported as unscoreable failures;
they are never normalized or silently removed from the result counts.

Experiment 002 compares absolute tolerances 3, 2.5, 2, and 1.5 points with
font-relative ratios 0.10, 0.125, 0.15, 0.20, and 0.25. A relative threshold is
the ratio times the preceding glyph's font size. The 54 authored synthetic lines
show that lowering a global absolute threshold can insert spaces inside tracked
text at larger sizes. Ratio 0.125 is promising on this limited development set,
but no new production default is recommended without human-verified real
samples and further independent development coverage.

See the [report and reproduction commands](evaluation/experiments/002/report.md).
The two real documents are development-only; transcriptions are explicitly
`agent_visual_checked`, not human-verified ground truth. They are separate from
the independent teacher's 16 anchors. No held-out document or manifest changed.
The [Experiment 001 record](evaluation/experiments/001/baseline.json) preserves
the original baseline fingerprints; its external artifacts were not rewritten.
