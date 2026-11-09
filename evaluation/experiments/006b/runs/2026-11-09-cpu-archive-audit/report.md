# Experiment 006b — CPU wheel archive audit, 2026-11-09

**Acquisition PASS. Do not install under the present 4 GiB cap on this evidence.** All **103 exact allowlisted wheels** were downloaded once, sequentially, with matching original/final source URLs, HTTP 200 responses, expected lengths and SHA-256 hashes. Total payload: **379,580,121 bytes**. No CUDA closure, extra image, Heron weight, installation or inference was requested. The conservative installation plan projects **5,758,187,969 bytes (5.36 GiB)** and needs a **separately approved 6 GiB inclusive cap**. A more optimized installation fitting 4 GiB remains unproven, not disproved for every possible implementation.

## Authority and fixed inputs

This new run follows PR #13 at `cff63071a1bc2762268be461e0b79579549b38c4` on `feat/experiment-006b-wheel-audit`. The user's explicit authorization covers only the [frozen 103-wheel proposal](../2026-11-09-cpu-packaging/archive-audit-proposal.json), SHA-256 `81c9a936575a8376acb835c2d33949b81719e96dfbc1cf009b41cfae5026ff5e`, plus bounded archive/license inspection. New [authorization.json](authorization.json) records that scope without changing the previous run's authorization or historical constraints.

Docling stays **2.148.0**, CPU Torch **2.15.0+cpu**, CPU Torchvision **0.29.2+cpu**, Heron **8f39ad3c0b4c58e9c2d2c84a38465abf757272d8**, Structure baseline **ba82b2c7f71604d5bcc2859b1a05de112723107d**. All six references remain `agent_visual_checked`; independent human verifications: **zero**. No scientific metrics are produced. The prospective withdrawal of the 2 GiB download ceiling remains in force; **4 GiB inclusive storage and 20 GiB host reserve remain active**.

## Observed acquisition and archive contents

| Quantity | Observed or derived value |
| --- | ---: |
| Unique successful payload GETs | **103**; redirects/retries: **0** |
| Expected and acquired compressed bytes | **379,580,121** |
| Measured archive-file allocation (`st_blocks × 512`) | **396,374,016 B** |
| ZIP-declared complete unpacked logical file bytes | **1,250,768,241 B** |
| Sum with each file rounded to 4 KiB | **1,318,440,960 B**; planning estimate |
| Discovered LICENSE/NOTICE/copyright files | **263**, representing **216** unique text hashes |
| Notice bytes read, counting repeated text | **1,479,194 B**; no bounded skips/read errors |
| Remaining partial/unverified archives | **0** |

All archives stay in **one isolated directory outside every Git root**, with one copy of each wheel. ZIP member lists, CRC/size declarations, original notices and raw logs stay there too. Only root wheel METADATA and bounded notice text were decompressed/CRC checked. No package extraction, executable import, install, bytecode generation from downloaded packages, OCR or inference occurred. ZIP size totals are central-directory declarations, **not observed extracted allocation**. The 4 KiB estimate excludes directory/script/installation details and does not claim equivalence to APFS allocation.

After acquisition, a separate sequential read pass recomputed SHA-256 from **all 103 final on-disk files** (379,580,121 bytes), with no symlink following and stable regular-file identity/size/mtime checks: **zero mismatches**. Both resource gates still passed. [post-acquisition-verification.json](post-acquisition-verification.json) records this independent final-file verification and the updated storage snapshot.

[artifacts.json](artifacts.json) records each exact URL, verified length/hash, physical archive allocation, file count and ZIP sizes. [license-files.json](license-files.json) gives every notice's member path, hash and automated text signatures. Raw metadata and resource-sample files are hash-manifested in [external-evidence-manifest.json](external-evidence-manifest.json). Completed Colima/cgroup and dependency-resolution work was not repeated.

## Execution failure, correction and continuation

The initial inspector stopped after **80 successfully hash-verified downloads (179,154,508 bytes)**. It selected setuptools' last nested vendored `*.dist-info/METADATA` as the root package identity. Inspection of the verified archive established that its root `setuptools-84.2.1.dist-info/METADATA` correctly identifies setuptools 84.2.1. **This was an audit-tool error, not a candidate parser/extraction failure.**

The initial source, STOPPED audit, logs and resource samples are preserved unchanged. The inspector now accepts only the single root `.dist-info/METADATA`; a synthetic vendored-metadata regression covers the error. The continuation rehashed/reinspected the 80 retained archives locally and downloaded only the **23 still-unacquired wheels (200,425,613 bytes)**. No HTTP payload was retried, no source or threshold changed, and no old experiment was overwritten. See [execution.json](execution.json) and [commands.md](commands.md). An initial new-test fixture byte-count expectation was also corrected before acquisition; final regression results below include the complete corrected suite.

## Specific license findings

**100 wheels contain discovered notice text; three have concrete notice gaps.** This improves on the previous metadata-only evidence but does not establish complete native/transitive license clearance. Text-signature detection is automated; the following contextual review is **agent-checked**, not independent human/legal verification. [license-review.json](license-review.json) contains exact notice paths/hashes and qualifications.

- **Docling, latex2mathml, tokenizers:** no LICENSE/NOTICE candidate and no `License-File` header in these wheels. Root metadata respectively supplies SPDX MIT, legacy MIT, and an Apache classifier. Tokenizers' native/Rust third-party notice coverage remains unresolved. Obtain authoritative version-matched license/notice evidence; package names/classifiers alone do not close these gaps. The Docling wrapper's SPDX declaration is retained as evidence, not silently classified as missing metadata.
- **Shapely:** the actual GEOS notice identifies LGPLv2.1 shared libraries. **Setuptools:** vendored autocommand carries LGPLv3 and generated validation code carries MPL terms. **OpenCV:** bundled FFmpeg binaries have LGPLv2.1 text. These are actual bundled conditions to retain/map, not evidence that private CPU execution is prohibited. Future modification/redistribution requirements have not been exhaustively assessed.
- **NumPy/SciPy:** libgfortran notices identify GPLv3 **with GCC Runtime Library Exception 3.1**. A GPL/AGPL word in the complete license text does not classify the whole wheel/project under that license. Pillow, PDFium/ICU and PSF notices similarly contain contextual or exception language; no blanket incompatibility is inferred.
- **RapidOCR:** its already-authorized wheel bundles **three ONNX OCR models, 31,749,509 logical bytes**. `MODEL_LICENSES.md` names all three and states Apache-2.0 terms, separate upstream ownership/conversion provenance, and permission beyond non-commercial use. No separate model URL was requested; Heron was not acquired and the ONNX data was not executed or decompressed for inspection. Independent upstream/per-model hash validation remains unexecuted. See [bundled-assets.json](bundled-assets.json).
- **False keyword concerns resolved:** OpenCV's non-commercial phrase explicitly permits both commercial and non-commercial use; RapidOCR's phrase rejects a noncommercial-only restriction. Shellingham's actual text supplies an ISC-style grant missed by the literal signature. These are not reported as new restrictions or missing licenses.

Full closure licensing remains **UNKNOWN**, specifically because of the three notice gaps and unverified native-component applicability/completeness. No incompatible license has been established merely from the searches. No additional upstream source/license downloads occurred in this allowlist-only run.

## Measured storage and prospective installation

| Measurement | Bytes |
| --- | ---: |
| Initial host available | **34,685,857,792** |
| Minimum sampled during acquisition | **34,270,756,864** |
| Post-acquisition host available | **34,250,293,248** (**31.90 GiB**) |
| Initial inclusive registered-root allocation | **2,050,318,336** |
| Highest sampled during acquisition | **2,455,052,288** |
| Post-acquisition inclusive allocation | **2,456,641,536** (**2.29 GiB**) |

**912 acquisition checks** plus the post-acquisition snapshot remained below 4 GiB inclusive and above 20 GiB available. Before/stream/after checks include `.part` files and all registered setup/runtime/cache/evidence roots. VM guest layers are already in measured sparse VM disks; nominal disk capacity is not charged as actual allocation. Old caches and artifacts were retained. APFS exclusive sharing is unknown, and concurrent host writes mean df changes cannot be equated with payload size. Samples are not proof of a continuous historical peak; historical provisioning peak stays UNKNOWN.

Let **H** be measured retained allocations (including these host archives/evidence), **U** the rounded package-file estimate, **M** pinned minimal Heron files (not acquired), and **W** a 64 MiB work/directory allowance. Then:

`H + U + M + W = 4,013,854,068 B`

That leaves only **281,113,228 bytes (268.09 MiB)** under the active 4 GiB cap for the **entire CPython 3.11 runtime/base image, every temporary installation allocation and all extra archive/model/cache copies**. The required interpreter is not already provisioned. Actual installation allocation remains unmeasured. This subtotal does **not** establish an end-to-end 4 GiB fit.

The following bounded conservative plan supports a **6 GiB proposal**, not an automatic budget change:

| Component | Bytes | Evidence/status |
| --- | ---: | --- |
| H: retained runtime/cache/archive/evidence | 2,456,641,536 | Measured host allocation |
| U: package files | 1,318,440,960 | ZIP sizes rounded per file to 4 KiB |
| M: Heron once | 171,662,708 | Frozen exact model-file inventory |
| T: one largest package scratch copy | 656,220,160 | Rounded Torch file sum; conservative allowance, not observed installer behavior |
| R: new CPython 3.11 runtime/base image plus retained compressed/layer/cache allocation | 536,870,912 | **512 MiB planning allowance**, image not selected/acquired |
| D: guest wheel copy plus a second model copy | 551,242,829 | Exact compressed CPU payload + frozen Heron payload; conservative duplication allowance |
| W: directory, metadata and install work | 67,108,864 | Planning allowance |
| **Conservative projected total** | **5,758,187,969 (5.36 GiB)** | Exceeds 4 GiB; also exceeds 5 GiB |
| **Margin under proposed 6 GiB** | **684,262,975 (652.56 MiB)** | Conditional forecast |

Conditions: keep one installation copy, install sequentially with at most one largest-package staging copy, prevent extra build/export/compiled-bytecode caches, and constrain new runtime/image costs to the 512 MiB allowance. If any premise fails, stop and reassess instead of spending the margin silently. A minimal direct installer might use less scratch/duplication, but such a complete <=4 GiB plan has **not been demonstrated**. The conservative plan is not a claim that every installer actually makes all these copies.

The extra allocation projected by this plan would leave roughly **28.82 GiB** on the host, above the reserve, subject to concurrent activity and actual allocation. Runtime and Heron downloads remain unexecuted; retained prior download accounting is carried forward to **981,529,895 bytes including historical allowances**, not reset or presented as measured wire traffic. See [resources.json](resources.json) for formulas, component status and all root allocations.

**Recommendation:** request a separate **6 GiB inclusive storage amendment** for this conservative plan. Keep 4 GiB memory, zero swap, four CPU cores/threads, 120 s/page and the host reserve unchanged. Resolve the targeted license evidence gaps and verify the selected runtime fits its explicit allowance before any separately authorized installation/Heron acquisition/smoke test. Current authorization ends with this report.

## Validation and stop

Existing `uv run --frozen --offline pytest`: **324 passed**, zero failures/skips, **7.98 s**, existing CPython **3.11.13**. Ten new offline regressions cover the exact allowlist, both resource guards, redirect refusal, bounded notices, traversal rejection, identity validation and nested vendored METADATA. All **258 pre-existing tracked files** remain SHA-256 identical. Production parser, Structure 0.2, dependency pins, all previous experiments and frozen/held-out inputs are unchanged. The working branch is stacked on PR #13; do not merge automatically.

Archive acquisition/inspection succeeded. **Actual candidate installation fit, native import compatibility, installation peak, inference memory/time and scientific quality are unexecuted/UNKNOWN.** No new runtime, image, Heron, OCR, neural import or inference step follows this audit.
