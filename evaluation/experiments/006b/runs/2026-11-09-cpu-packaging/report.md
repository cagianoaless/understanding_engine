# Experiment 006b — CPU-only packaging decision, 2026-11-09

**Prefer the official CPU closure. Installation remains INDETERMINATE, pending archive-size and license inspection.** This run performs metadata resolution and HTTP HEAD requests only. No wheel payloads, Heron weights, images, installations, neural imports or inference were acquired/executed. No scientific comparison or memory-performance conclusion follows.

## Protocol and provenance

The [dated amendment](../../../../../docs/protocol-amendments/2026-11-09-download-budget.md) records the user's withdrawal of the cumulative 2 GiB download ceiling for subsequent runs. Historical reports retain their original constraints and decisions. The **inclusive 4 GiB installed/cache cap**, **20 GiB host free reserve**, 4 GiB container memory, zero swap, four CPUs/threads and 120 s/page remain unchanged. Removing a download restriction does not authorize payload acquisition.

Parent: PR #12, `1fba0d4834ee20697529c2b79e18a61cf814bf53`; dedicated stacked branch `feat/experiment-006b-cpu-packaging`. Docling remains **2.148.0**, Heron **8f39ad3c0b4c58e9c2d2c84a38465abf757272d8**, scientific Structure baseline **ba82b2c7f71604d5bcc2859b1a05de112723107d**. Six references remain `agent_visual_checked`, with **zero independent human verifications**.

## Observed packaging results

| Metadata-resolved target closure | PR #12 default PyPI | Official CPU substitution |
| --- | ---: | ---: |
| Packages | 122 | **103** |
| Selected compressed wheel bytes | 3,396,860,472 | **379,580,121** |
| Torch | 2.15.0; 483,605,887 B | **2.15.0+cpu; 170,730,380 B** |
| Torchvision | 0.29.2; 7,739,265 B | **0.29.2+cpu; 2,072,349 B** |

Savings: **3,017,280,351 compressed bytes (88.83%)**. Nineteen CUDA/toolkit/NVIDIA/Triton dependencies disappear; no packages are added. All 101 other selected artifacts and sidecar hashes match PR #12. Public versions are constrained to that closure for a controlled comparison; unused CUDA constraints do not force those nodes into the new graph. See [comparison.json](comparison.json) for every removed package.

Resolution actually succeeded with existing **uv 0.7.13**, cross-targeting **Linux aarch64 / CPython 3.11.13 / glibc 2.39**, binary-only, with the unchanged 2026-11-06 upload cutoff. Every active Linux dependency/extra/marker/version edge was independently checked: **zero closure errors**. This is target-metadata compatibility, not an observed Linux installation or import test.

Only the PyTorch family is routed to the [official CPU index](https://download.pytorch.org/whl/cpu/torch/); other packages use PyPI. Both `download.pytorch.org` and its index-linked `download-r2.pytorch.org` origin are allowlisted. The CPU wheels provide compatible `manylinux_2_28_aarch64` tags (Torch `cp311-cp311`, Torchvision `py3-none`). Official index SHA-256 values and verified METADATA sidecars identify the selected builds; HTTP HEAD supplies their expected payload sizes. **Wheel content hashes remain unverified until acquisition.** Published provenance URLs are recorded where available; no cryptographic attestation verification is claimed.

The gateway denied wheel/sdist/range payload forwarding by design. Actual resolution: exit **0**, **103** packages, no blocked requests or gateway errors. This stage acquired **11,632,447 HTTP metadata body bytes**, including the initial CPU source scout; protocol overhead is separately reserved rather than claimed as measured. Exact artifact URLs, sizes, hashes, tags, dependencies and license declarations are in [dependencies.json](dependencies.json). Reproduction is in [commands.md](commands.md).

## Licensing concerns

There are **46 explicit declared license expressions** and **57 UNKNOWN declaration classifications** under the unchanged conservative metadata checker. Some UNKNOWN packages supply legacy labels such as BSD or MIT; that is evidence to investigate, not proof of incompatible licensing. **Bundled-license clearance is UNKNOWN for all 103 wheels** because their notices/native-library license files were not acquired.

The actual CPU Torch metadata declares `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib`. CPU Torchvision supplies legacy `BSD` without an SPDX expression; no stronger clearance is invented. Large native distributions such as Torch, SciPy, OpenCV and PDFium need their bundled notices inspected. Heron's unchanged pinned model evidence declares Apache-2.0 and preserves its exact weight hash/size; weights remain unacquired and full model license clearance remains UNKNOWN. See [licenses.json](licenses.json) and the unchanged [prior model evidence](../2026-11-09-linux-preflight/model.json).

## Resource decision

Fresh measured host availability: **34,759,376,896 bytes (32.37 GiB)**. Retained runtime/setup/cache/evidence roots allocate **2,049,421,312 bytes (1.91 GiB)** in this snapshot. APFS exclusive sharing is not measured; sparse virtual disk capacities are not charged as actual allocation. Guest layers already reside in the measured VM files and are not added again. No caches or previous artifacts were removed.

| Planning scenario | Inclusive bytes | Status against 4 GiB |
| --- | ---: | --- |
| Current retained allocations | 2,049,421,312 | Measured snapshot fits |
| Current + all CPU wheel archives + 64 MiB work allowance | **2,496,110,297** | Projected archive audit fits |
| Above + pinned minimal Heron files, once | 2,667,773,005 | Subtotal only; **not an installation estimate** |

That last subtotal leaves **1,627,194,291 bytes (1.52 GiB)** for **all unpacked packages, an additional CPython 3.11 runtime/base image, temporary extraction, image layers and duplicate pip/model/cache copies**. Their sizes are UNKNOWN. The existing VM's Python is not the requested candidate CPython 3.11. A functioning package-tag resolution does not provision that interpreter or verify native runtime libraries.

The full formula is `H + E + M + U + R + T + D + 64 MiB <= 4 GiB`, defined in [accounting.json](accounting.json). It retains all prior consumption and accounts for potential duplicate files. Download accounting, including carried historical allowances and this stage, is **601,949,774 bytes before candidate payloads**; adding selected CPU wheels and minimal Heron gives **1,153,192,603 bytes plus the unknown additional runtime**. Those figures include estimated allowances and are not measured cumulative network traffic. There is no active fixed download ceiling.

**The 4 GiB cap is not yet demonstrated to block installation, and no increase is applied or justified from compressed sizes alone.** If observed archive contents and the selected runtime make the inclusive requirement exceed it, report the component totals and request a separately authorized budget based on those measurements. Host reserve feasibility and the 4 GiB experiment-storage gate remain separate decisions.

Existing model-free Colima/cgroup evidence is reused unchanged. No VM/context modifications, image pulls or repeated infrastructure tests occurred. Actual candidate memory, imports, runtime and inclusive installation peak are unmeasured. Historical provisioning peak remains UNKNOWN; this does not establish Docling resource failure and does not require repeating the old infrastructure exercise for this packaging decision.

## Shortest remaining path

1. **Request narrowly scoped archive-audit approval:** fetch only the **103 exact URL/hash/size-allowlisted wheels (379,580,121 expected payload bytes)** in [archive-audit-proposal.json](archive-audit-proposal.json). Use one external archive copy, bounded sequential transfers, SHA-256/length checks, a fresh destination outside Git, monitoring of both current caps, and no pip install. Read ZIP central directories and bounded LICENSE/NOTICE files. Report exact declared unpacked logical sizes separately from physical allocation. No extra image, Heron weight or separate OCR/model download. The default closure includes RapidOCR; inventory any bundled assets without executing them.
2. With that evidence, finish license review and one inclusive installation plan including a pinned Linux ARM64 CPython 3.11 runtime, temporary peaks and retained/duplicate caches. Reuse the frozen closure and existing cgroup controls. If necessary, request a measured, explicit storage-budget amendment; do not silently relax 4 GiB.
3. **Only after decisive gates and separate authorization**, acquire the pinned Heron weight/runtime, install the isolated candidate and run one frozen page with OCR disabled and network disabled under the existing limits. This future smoke test is not authorized or executed by this report.

The withdrawn 2 GiB ceiling is a historical discretionary constraint, **not a present technical blocker**. Remaining packaging evidence, licensing, installed/runtime fit and explicit acquisition/installation authorization are real unresolved gates. No need to download the CUDA closure or perform another generic Colima preflight.

## Verification and limits

`uv run --frozen --offline pytest`: **314 passed**, zero failures/skips, 7.47 s on existing CPython 3.11.13. This includes ten new offline gateway/policy regressions. All **237 pre-existing tracked files** remain SHA-256 identical, including production code, research dependency pins, Experiments 001–006b historical runs, six references and held-out data. Raw evidence is outside every Git root; committed records redact private paths. No interpretation or repair of extraction results occurred.

No payload acquired means no observed wheel unpacking, complete native ABI/import compatibility, installed peak, license-notice completeness, Docling memory consumption, timing, OCR behavior or extraction quality. **Stop at this packaging decision; archive acquisition still needs approval.**
