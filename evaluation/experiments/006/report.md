# Experiment 006 — NO-GO before candidate acquisition

The [complete preflight](preflight.md) could not clear the resource/isolation gates
on the audited macOS arm64 host. The requested baseline remains
`ba82b2c7f71604d5bcc2859b1a05de112723107d`.

Docling 2.148.0 has a successfully resolved, target-compatible 103-package closure.
The selected wheels plus minimal pinned Heron files total **500,726,377 expected
artifact bytes**, below the 2 GiB artifact budget. This is not an installed-size
or memory result. Exact 4 GiB standard RSS/address-space limit calls reject the
request; no verified whole-tree enforcement exists in this harness. Installed/
cache footprint, full license clearance and effective runtime controls remain
unverified. [summary.json](summary.json) records **NO_GO**, with acquisition
authorization false. No cap or candidate was changed to force a run.

## Comparative metrics and resource measurements

| Registered development document | Structure 0.2 | Docling | Region/heading/caption/order/paragraph metrics |
| --- | --- | --- | --- |
| Attention, exact registered arXiv v7 | not_run | not_run | not_run |
| BERT, exact registered arXiv v2 | not_run | not_run | not_run |
| Nature TabPFN, exact publisher PDF | not_run | not_run | not_run |
| Aggregate / document macro | not_run | not_run | not_run |

There are no new performance, quality, localization, inversion, abstention or
per-category denominators. Unknown values are JSON `null`/`not_run`, **not zero
errors or perfect precision**. No new pages were selected, references frozen,
crops/overlays produced or predictions generated: Phase 1/2 was not entered after
Phase 0 failed. No Codex annotations are labelled human-verified. Experiment
004/005 scores are not repackaged as a fresh comparison.

| Observed preflight quantity | Result |
| --- | --- |
| Installed host RAM | 16 GiB |
| Host logical CPUs | 8 |
| Free disk at elevated probe | 12,816,334,848 bytes |
| Pinned selected dependency wheels | 103; 329,063,669 expected bytes |
| Minimal model inference payload | 171,662,708 expected bytes |
| Model weight acquisition / candidate installation | not attempted |
| Actual candidate installed/cache bytes | not_run |
| Candidate cold/warm initialization, time/page, process-tree peak RSS | not_run |
| Effective inference CPU device/threads, offline/plugin isolation | not_run |

Metadata/configuration/source reads and resolver caching occurred; they are
distinguished from binary/model acquisition. The 4 GiB failure is a host-control
probe result, not a measured model-memory violation. The known artifact sizes
do not establish that Docling would fit or exceed the remaining limits.

## Source-grounding analysis

No empirical grounding comparison is possible without candidate output. Valid,
missing, unassigned, ambiguous, contradictory and unmapped counts are all
**not_run**. No glyph ID is fabricated and no Docling Unicode is treated as an
authoritative extraction or correction.

Static source review finds that the standard object-detection engine produces
label IDs, scores and bounding boxes, not Understanding Engine character IDs.
Its page-image scaling code and native output would need a separate crosswalk
to original source pages/boxes/characters. A later permitted adapter must test
crop/rotation/origin transformations and preserve many-to-many, ambiguous and
unmatched references. Image-space boxes alone would not prove character-level
traceability. These are adapter requirements, **not observed grounding failures**.
The NO-GO therefore supports retaining the deterministic baseline until a valid
comparison is possible; it establishes no quality advantage for either engine.

## Failures, safeguards and reproduction

Actual preflight failures/diagnostics are preserved:

- Mutually exclusive uv flags were rejected before resolution, then corrected
  without enabling builds. The cross-target macOS wheel error was checked
  against native tags and disproved; native resolution succeeds.
- Both exact-cap OS limit calls raise `ValueError`. An exit-0 collector does not
  turn those recorded errors into enforcement evidence. Restricted RAM/process
  reads were retried with read-only escalation and succeeded.
- Some decisive gates remain unknown: installed/cache upper bound, full artifact
  license clearance and execution-verified isolation/thread/timeout control.
  They were not silently marked passed or replaced with inferred measurements.

[preflight.py](preflight.py) replays immutable caps and fails closed for every
failed, missing or unknown check. It never installs a dependency, fetches weights
or launches inference. [probe_host.py](probe_host.py) reproduces the bounded
host-limit check; [audit_metadata.py](audit_metadata.py) rechecks only frozen
package metadata. Exact commands, selected wheel pins/hashes, model revision/
URLs/digests, raw probe output, environment and hashed external artifacts are
committed alongside this report. Large/raw metadata/source caches stay outside
Git. Neither requirements file is a tested Docling installation.

Normal offline tests cover gate failures, incomplete evidence, fixed budgets,
source/model identity accounting, collector-error interpretation and preservation
of previous audit output, without neural imports/downloads. Coordinate/model-
adapter and candidate resource-runner tests are **deferred with Phase 2**, not
invented for an unexecuted implementation. The full existing suite and unchanged
GitHub CI run for this branch; test results are in [validation.json](validation.json)
and the PR.

All 139 baseline tracked files, including the parser, Structure 0.1/0.2, schemas,
production dependencies/lockfile, Experiments 001–005 and held-out manifest,
remain byte-identical. No PDF or weight is committed. The dedicated follow-up
PR targets PR #5's feature branch and is left unmerged.

Actionable rerun prerequisites and the limits of this NO-GO are in
[preflight.md](preflight.md). No specialized model integration or baseline
replacement is recommended from this absence of comparative evidence.
