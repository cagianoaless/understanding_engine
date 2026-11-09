# Protocol amendment — 2026-11-09: remove the cumulative download ceiling

Authority: the user's explicit decision after PR #12, on 2026-11-09.
Applies to `2026-11-09-cpu-packaging` and subsequent explicitly authorized runs.
It does not amend or reinterpret any historical experiment's constraints/results.

- The former hard 2 GiB cumulative artifact-download ceiling is withdrawn.
  A projection above that value is no longer itself a NO-GO criterion.
- Record actual downloads, retained prior consumption, and projected totals before
  acquisition. Use exact artifact allowlists, sizes and hashes; this is not
  authorization for unrestricted downloads.
- Preserve at least 20 GiB available on the host throughout operations.
- The existing **4 GiB inclusive installed/cache limit remains in force**,
  independently of compressed download sizes. Do not expand it without separate
  user authorization. Include runtime/setup costs and potential duplication.
- Container memory remains <=4 GiB, swap disabled, <=4 CPU cores and <=4 effective
  inference threads, and <=120 seconds per page.
- Docling 2.148.0, Heron revision
  `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, Structure 0.2 at
  `ba82b2c7f71604d5bcc2859b1a05de112723107d`, and the six frozen development
  references remain unchanged. They are agent_visual_checked, with zero
  independent human verifications.
- The present authorization covers official CPU-only packaging resolution,
  comparison, resource/license assessment, and a scoped acquisition proposal.
  It does not authorize wheel-payload acquisition, Heron weights, complete neural
  installation or inference. No CUDA-heavy closure will be acquired by default.

PR #12 remains a valid NO-GO under its original policy. Its former download-cap
FAIL is superseded only as a decision rule for new runs; it is not corrected
retroactively. Historical provisioning peak storage remains UNKNOWN; do not
repeat already completed Colima/cgroup validation without evidence of a problem.
