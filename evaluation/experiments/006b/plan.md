# Experiment 006b — frozen staged plan

Issue #8 resumes Experiment 006's macOS control NO-GO; it does not establish a
model memory failure. This branch starts at PR #7 commit
`0cebd59980b156499a60aee24d625f9203676cf8`. Comparison baseline remains unchanged
Structure 0.2 at `ba82b2c7f71604d5bcc2859b1a05de112723107d`.

`plan.json` is the machine-readable freeze of metrics, label mappings, coordinate
conversions, resource limits and stage gates. `selection.json` records prior page
exposures. Six new development pages are Attention 6/9, BERT 6/10 and Nature 15/19.
None overlaps Experiments 004/005 or their training pages, or the earlier spacing
sample pages. BERT 9 was previewed from the source PDF and not selected.
The existing development/held-out manifests are unchanged.

Stage A completes source-only annotations and an external review package before
runtime investigation or either candidate's predictions. The agent-estimated
references remain provisional until a named independent human reviews them.
`freeze.json` hashes all frozen inputs, including review-package member hashes.
Any later reference corrections must create a new version, never rewrite v1.

Stage B reads current official container documentation and checks for an already
available local Linux Docker/Podman runtime without installation, daemon startup,
privilege elevation or settings changes. Actual cgroup limits, child-inclusive
memory, swap, observed CPU behavior, timeout cleanup and byte accounting must be
demonstrated in a disposable model-free container before installing Docling.
Flags and Docker VM allocations alone are insufficient. A missing runtime is a
prerequisite blocker: stop without installing Docker or substituting a model.

Only after B passes may C resolve the Linux cp311 closure for the actual native
architecture, audit licenses, account for base images/layers, fetch the three
allowlisted Heron inference files and install in an isolated environment. Frozen
versions are Docling 2.148.0 and Heron
`8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`. Prior macOS wheel counts are not a
Linux feasibility estimate. Offline CPU inference excludes OCR, table/formula
reconstruction, enrichment, plugins, telemetry and remote services.

Limits: combined new downloads 2 GiB including images and all artifacts;
installed/cache 4 GiB including layers; hierarchical container memory 4 GiB;
swap disabled; CPU quota at most four cores and at most four effective inference
threads; external page deadline 120 seconds with whole-container/process-tree
cleanup. Record logical/uncompressed, physical and compressed bytes separately.
The limits bound the container, not the host or Docker Desktop VM.

D compares both candidates on the same six original PDF pages, bytes, settings,
coordinate frame and frozen scopes under comparable controls. Measurements are
per-document and per-layout plus micro/macro aggregates. Failed samples stay in
the denominator. Localization, classification, order, paragraph, grounding and
resource metrics have separate denominators; see `plan.json` for exact policies.
Model text never replaces the authoritative character layer. No silent Unicode
normalization, formula recovery or semantic correction is permitted.

If B/C fails, comparison and grounding metrics remain null with stage status
not_run. Report the exact blocker, completed agent-only references and outstanding
human review. Do not infer model accuracy, memory demand or generalization from
an experiment that has not executed.
