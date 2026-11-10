# Prospective amendment — 2026-11-10

Authority: explicit user approval after PR #14. Applies to the new single-page
run and subsequent separately authorized runs, never to historical reports.

- Inclusive installed/cache storage rises from 4 GiB to **6 GiB
  (6,442,450,944 bytes)**. Preserve and count all retained setup/runtime, archives,
  images/layers, installations, models, caches, duplicate and temporary files.
- Host available space stays >=20 GiB. Container memory stays <=4 GiB, swap zero,
  CPU quota/effective inference threads <=4 and the one page's timeout <=120 s.
- Authorized, in order and only after each gate passes: targeted version-specific
  license verification; isolated Linux ARM64 CPython 3.11.13 runtime; install the
  exact 103 verified CPU wheels; exact pinned minimal Heron files; **one** existing
  development page through Docling with OCR and networking disabled.
- Docling 2.148.0, torch 2.15.0+cpu, torchvision 0.29.2+cpu, every wheel/hash,
  Heron revision 8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 and Structure baseline
  ba82b2c7f71604d5bcc2859b1a05de112723107d remain fixed.
- Do not tune or change annotations, preprocess a replacement PDF, clean/resize
  existing resources, change host research environments, use cloud/GPU/OCR or run
  the six-page benchmark. Stop on material unresolved local-use license terms,
  unexpected downloads/dependencies/privileges, or resource-gate failure.
- The prior download-ceiling withdrawal remains prospective. Earlier NO-GO and
  UNKNOWN records retain their original policy, observations and limitations.
- A successful smoke test verifies execution only. It establishes no comparative
  accuracy, generalization or independent human verification.
