# Frozen issue #8 instructions

Source: https://github.com/cagianoaless/understanding_engine/issues/8

Title: Experiment 006b: gated Linux Docling benchmark with frozen references and unchanged resource caps

Issue updated_at at initial read: 2026-11-06T14:59:06Z

# Experiment 006b — Controlled Linux container and frozen Docling comparison

## Objective and provenance
Resume Experiment 006 after its **valid preflight NO-GO** on macOS (see [issue #6](https://github.com/cagianoaless/understanding_engine/issues/6) and [PR #7](https://github.com/cagianoaless/understanding_engine/pull/7)). Its result is a **failure of the attempted host resource-enforcement mechanism**, not evidence that Docling is too large, nor evidence about quality.

**Keep constant**: baseline Structure 0.2.0 at `ba82b2c7f71604d5bcc2859b1a05de112723107d`, candidate `docling==2.148.0` + pinned default Heron model revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, and exact SHA-256 PDFs in the development manifest (Attention, BERT, Nature TabPFN). No changes to original parser, production thresholds, 0.1/0.2 implementations, their schemas, `uv.lock`, Experiments 001–006, or held-out records.

Create a new `feat/experiment-006b-container` branch stacked on PR #7's `feat/experiment-006-docling` (or document any immutable equivalent). Open its own PR; no merges. Produce artifacts only in `evaluation/experiments/006b/` and external hashed data directories.

## Fixed resource budgets (unchanged)
- **Combined newly downloaded bytes <= 2 GiB**; include base Linux images, package wheels, model files, and all other newly fetched artifacts in the accounting. If Docker Desktop itself is absent, **do not install it automatically** or modify machine-wide settings; report as a prerequisite requiring the user's action.
- **Isolated experiment installed/cache footprint <= 4 GiB** (include layers, virtual environment and models attributable to this experiment; distinguish logical file sizes vs physical and compressed vs uncompressed).
- **Container-wide memory hard limit <= 4 GiB including children**, with swap explicitly limited or disabled (not just `RLIMIT_RSS` on macOS). Verify effective Linux cgroup values; do not assert whole-host / Docker-VM RSS bound from container cgroup alone.
- **CPU quota <= 4 CPU cores, and <= 4 effective inference threads** across applicable native math/OpenMP/Torch pools (record both configuration and observed worker behavior); no GPU/MPS.
- **External page-processing timeout <= 120 s per processed page**; process-group/container is terminated on timeout and the sample remains in denominator.
- Inference **offline** / no remote inference, unapproved plugins or telemetry-required paths. Never expose secrets or proprietary files. No container privilege escalation, unrestricted Docker socket mounts, or `--privileged`.

## Stage A — Independently frozen human-reviewable development references (before inference)
1. Choose six **fresh development pages** (two per exact registered paper), excluding Experiment 004/005 evaluation pages, 005 training-check pages, and where practical the heavily exposed spacing windows. Record any unavoidable overlaps explicitly.
2. Use source PDF renders to freeze page selection, region locations/types, reading-order comparisons, paragraph decisions, figure/equation/chart coverage and explicit ambiguous cases, all with stable IDs and PDF hashes. Select and freeze page scope, metric formulas, matching algorithm, coordinate conventions and scoring settings **before any proposed-model outputs**.
3. Transcriptions produced by Codex are always **`agent_visual_checked`**, never `human_verified`. Provide a small review pack (render/crop + expected boxes/relations in a manifest) for independent human checking. Do not assert that an AI or second agent is a human reviewer. Do not fabricate verification when a human is unavailable.
4. Store frozen annotations and SHA-256, plan and review protocol in the repository; keep full PDFs and potentially copyrighted image crops outside Git with hash manifest. Preserve post-freeze corrections as a new version, not silent edits. **This stage may proceed even if Linux/Docling is unavailable.**

## Stage B — Host/container feasibility (no expensive installation)
1. Read the archived 006 preflight and current Docker Engine/Desktop documentation. Check whether Docker/Podman or an explicitly authorized, compatible Linux host is **already available**; examine version, daemon accessibility, CPU architecture, RAM/disk capacity, Docker Desktop VM resource allocation on macOS, cgroup support and security policies. **Do not install Docker, start external cloud resources, elevate privileges, or alter machine-wide Docker settings without asking for authorization.**
2. If an existing Linux container runtime is available, resolve the candidate's wheel closure for **that exact Linux architecture, CPython 3.11**. **Do not reuse the macOS ARM wheel inventory** as a Linux resolution. Maintain the same Docling release and Heron model revision; pin exact compatible wheels and hashes.
3. Demonstrate resource enforcement on a **small disposable, model-free test process**: read `/sys/fs/cgroup/memory.max`, effective swap controls, CPU quota, and test an external timeout plus process-tree teardown. Verify container-wide accounting including children; record limits independently of configuration claims. Validate disk/download accounting mechanisms with tiny files without exceeding limits.
4. Never assume a Docker `--memory` flag alone implies no swap; explicitly control/check swap. Never claim the whole Mac's or Docker VM's usage is capped by a Linux container cgroup. Prefer native `linux/arm64` on Apple Silicon; avoid accidental x86 emulation.
5. Re-audit effective dependency/model licenses; model weight SHA-256 must be content-verified after any permitted acquisition. Confirm offline flags and local-path behavior before inference. If required controls cannot be demonstrated, mark **NO-GO**; do not install/download models. Distinguish a missing runtime, unverified budget, and genuine incompatibility.

## Stage C — Gated isolated acquisition and smoke test
**Only if Stage B passes sufficiently to safely enforce budgets**:
1. Use the smallest compatible pinned base image and a dedicated, disposable, non-privileged environment. Account for base image, Linux wheels, cache, installed model and build layers in the same caps. Use explicit bounded/watched acquisition with SHA-256 verification; stop on either download or disk budget.
2. Model/cache permissions and exact revision must be pinned; no generic "download all" commands. No optional OCR, VLM, table reconstruction, formula generation, image classification/description, chart enrichment, external plugins or remote APIs.
3. After acquisition, turn networking **off** for all inference workers; set CPU-only model device, explicit thread limits, fixed timeout, observed cgroup memory and OOM diagnostics. Do a bounded one-page smoke test *only after freezing Stage A*; retain failures and logs. If memory/time/disk caps are exceeded or cannot be observed, stop and report it; do not raise caps.

## Stage D — Controlled comparison (only if Stage C passed)
Run the unmodified 0.2 engine and Docling on the **same six original-PDF pages**, under comparable recorded resource limits, using identical source bytes / documented page-range semantics and coordinate conversions. Docling's raw text is **not** authoritative extraction. Keep native output; implement an independent adapter with clearly marked valid/ambiguous/unmapped source-character links, without fabricating original glyph IDs.

Report full frozen denominators (including timeouts, crashes and unsupported regions):
- region detection P/R/F1, heading/caption and false headings on equation tokens, figure/chart/equation localization;
- pairwise reading-order correctness, inversions, abstentions, paragraph boundaries;
- page-/document-level scores and macro aggregation;
- traceability/coverage, unresolved/missing/many-to-many/contradictory glyph grounding;
- download/installed/cache bytes, cold and warm runtime, process-tree/container memory, CPU threads and page timeouts; distinguish initialization from inference.
- All quality results remain **provisional agent-checked** until genuinely human-reviewed. Do not claim six-page or three-paper generalization.

## Stopping and deliverables
A valid STOP at any stage is better than violating controls. Missing Docker/Podman or a suitable Linux host is a **prerequisite to resolve**, not proof that Docling is infeasible. Do not replace the model/backend, increase budgets, access cloud inference, or silently run unrestricted on macOS.

Deliver `evaluation/experiments/006b/{plan.md,preflight.md,report.md,summary.json,...}`; exact commands, frozen annotations/manifest and human review pack when Stage A is completed; lock/dependency/weight inventories, validation probes and logs; if benchmark runs, score adapter, raw per-decision comparisons, resource evidence and hashes of off-repo artifacts. Clearly mark each stage GO/NO-GO/NOT_RUN and preserve previous 006 NO-GO unchanged.

Add focused offline tests for freeze, hash/reference integrity, gate/timeout accounting, cgroup parsing, CPU/memory/swap boundaries, coordinate transforms where implemented, and absence of neural imports in ordinary CI. Keep `uv run --frozen --offline pytest` green with no Docling installed. Provide CI link and PR link; **do not merge**.

## Scientific acceptance
We want actionable, reproducible evidence about whether a specialized local document-layout model gives enough improvement over Structure 0.2 to justify dependencies and loss/risk of source grounding. A complete, transparent precondition-blocked partial result is acceptable; never invent model quality results.
