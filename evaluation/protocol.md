# Evaluation protocol

## Roles and evidence

**Student output** is the unchanged `extraction.json`, `paper.txt`, and `run.json`
produced by a frozen application revision. Preserve the PDF SHA-256, application
commit, Python/dependency versions, configuration, artifact hashes, and original
PDF bytes. Its authoritative layer records backend output, not ground truth.

**Teacher review** is a separate powerful model's independent examination of
the same PDF. Generate it externally under the research workflow, without showing
student output first. Record model/version, date, prompt, configuration, PDF hash,
and complete raw response in separate review artifacts. The application never
calls the teacher. Teacher observations are hypotheses, including apparently
confident mathematical or layout claims.

**Manually verified ground truth** consists only of human-checked annotations
against the actual PDF. Neither agreement between models nor agreement between
student and teacher creates ground truth. Preserve disagreements and uncertainty.
Inspect both rendered content and embedded character mappings when Unicode
encodings, ligatures, invisible text, or font rendering are disputed: the visible
glyph alone may not distinguish precomposed and decomposed Unicode.

For each disagreement record document hash, page, native bbox, student character
IDs where available, student observation, teacher claim, verification evidence,
reviewer, resolution, and status (`unresolved`, `verified_error`, or
`verified_correct`). Corrections live in separate annotations; never overwrite
raw student or teacher artifacts or silently repair the original extraction.

## Development and held-out separation

`development/manifest.json` and `held_out/manifest.json` are separate, initially
empty manifests. Each selected document entry must contain `document_id`,
`sha256`, `local_path`, source/provenance, redistribution permission, and a short
description of its extraction challenges. Paths in manifests may be local and
are not copied into deterministic extraction output. Do not commit private or
unlicensed PDFs; record reproducible acquisition information instead.

Choose documents and lock the split by PDF byte hash before tuning. Also keep
alternate versions of the same paper in one split. Held-out content, teacher
reviews, and annotations must not guide implementation, settings, fixture
expectations, or document-specific heuristics. Synthetic regression fixtures are
development material, not held-out evaluation documents.

Iterate on development discrepancies only. Turn manually verified development
errors into legally distributable minimal regressions when possible. Before a
held-out run, freeze and record the code commit, lockfile, settings, document
hashes, metrics, annotation rules, and pass thresholds. Run the candidate once
against that frozen set. Report all documents, failures, textless outcomes, and
unresolved cases. Do not tune on held-out results and then describe the same set
as independent evidence; retire exposed documents from subsequent held-out claims
and select a fresh set if their content informs development.

## Measurements

For this milestone report page/character retention, extraction failures,
textless-page classification, coordinate validity, deterministic artifact hashes,
and exact-codepoint differences on manually transcribed samples. Keep inferred
spacing differences separate from source-unit omissions/substitutions. Record
the precise sampling and alignment rules, including treatment of ligatures and
multi-codepoint glyph mappings. Report counts/denominators, not only percentages.

Derived reading order and mathematical reconstruction have no success claim in
Milestone 01. Runtime/memory measurements, if conducted later, must include
hardware, OS, environment, document sizes, and method; do not infer a performance
claim from unit-test duration.

## Milestone acceptance

- Offline synthetic regression suite passes on Python 3.11.
- Same input/environment/configuration yields byte-identical deterministic files,
  including when input filename and Python hash seed change.
- Character Unicode, indices, IDs, geometry, and page provenance are retained;
  derived references resolve and the two layers remain distinct.
- Missing, invalid, encrypted, and malformed-geometry input failures are explicit.
  Valid textless and mixed PDFs are distinguishable from failures.
- Contract or write/publication failures do not publish a partial destination;
  existing output remains intact. All three successful-run artifacts are present.
- Fixture provenance, coordinate conventions, limitations, and empty split
  manifests are documented.

Real-paper or held-out accuracy is not an acceptance claim until documents and
verified annotations have been selected and an evaluation has actually run. No
teacher review or real-paper held-out evaluation is included in this milestone.
