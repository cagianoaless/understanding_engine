# Experiment 006b — Linux aarch64 dependency/license/storage preflight

Run: 2026-11-09. **NO-GO for acquisition/installation under the unchanged PyPI packaging policy.** Metadata resolution succeeded, but the 122 selected wheel payloads alone exceed the complete two-GiB artifact cap. No wheels, weights, extra images or candidate software were acquired; no neural stack was imported and no inference ran.

Started from the verified clean `feat/experiment-006b-local-runtime` head `86832cf743ad03020fdfbe58ebb726edf3d2df85`, matching PR #11. This follow-up is stacked on that branch. AGENTS.md, issue #10, PR #9, Experiment 006 and the complete prior local-runtime run were read first. No previous result or branch was rewritten.

## Separate pre-install gates

| Gate | Result | Evidence |
|---|---|---|
| Complete Linux wheel closure | **PASS, metadata only** | uv 0.7.13 resolved 122 pins for CPython 3.11.13 / aarch64-manylinux_2_39; an independent Requires-Dist/extra/marker/version audit found zero missing or unsatisfied active edges |
| Pinned Heron identity | **PASS for metadata identity** | Pinned API commit, small-file hashes, weight LFS SHA-256 and expected size match Experiment 006; weight content was not fetched or verified |
| Full license clearance | **UNKNOWN** | 48 unambiguous project SPDX expressions; 74 missing/legacy-only/custom-reference expressions. Declarations and selected wheel METADATA are retained, but bundled notices/terms and full compatibility are not cleared |
| Projected inclusive download cap | **FAIL** | 4,142,063,291 expected bytes versus 2,147,483,648; wheels alone are 3,396,860,472 bytes |
| Projected installed/cache cap | **UNKNOWN** | Unpacked sizes, temporary extraction and an additional CPython 3.11 runtime/image are unmeasured. A fully retained compressed-cache planning scenario already exceeds four GiB |
| Current host reserve | **PASS** | Final inventory: 34,831,814,656 bytes free, 32.440 GiB; reserve remains 20 GiB |
| Complete candidate limit enforcement | **UNKNOWN** | VM/cgroup availability and earlier bounded controls remain documented; native inference pools, four-GiB candidate behavior, 120s/page behavior and a hard four-GiB installed/cache guard were not validated by this metadata audit |
| Historical provisioning peak | **UNKNOWN, unchanged** | The prior monitor omitted the actual state location; no new observation retroactively measures that peak |

Any decisive UNKNOWN blocks installation. This run also has an independent, quantitative download FAIL. This is a packaging/resource preflight result, not a Docling memory, accuracy or speed result.

## Resolution and provenance

The input remains `docling==2.148.0`, including its normal `docling-slim[standard]` dependency closure. The source remains PyPI, with Experiment 006's `2026-11-06T00:00:00Z` upload cutoff. No macOS wheel selection, dependency overrides, package omissions, CPU-index substitution or transitive-version tuning was used. `requirements.candidate.lock` contains one selected Linux-compatible SHA-256 per pin and is not an authorization to install.

The target is explicit CPython 3.11.13 on Linux aarch64/glibc 2.39. The host audit still runs in the existing macOS CPython 3.11.13 environment. The VM actually reports aarch64, glibc 2.39, four CPUs and system Python **3.12.3**; that interpreter was not substituted for the requested target. A candidate CPython 3.11 execution environment remains unprovisioned.

Actual CLI help confirmed `--python-version`, `--python-platform aarch64-manylinux_2_39`, `--only-binary :all:`, `--generate-hashes`, `--exclude-newer`, `--no-config` and `--no-python-downloads` support. The known incompatible `--no-build`/`--only-binary` combination was not used. The resolver does not provide a metadata-only switch, so every advertised artifact URL was routed through a loopback gateway. It forwards only official index JSON and wheel METADATA sidecars. Wheel/sdist body or range access is rejected locally before any upstream request; direct-URL requirements are rejected. Redirect targets are checked before forwarding. Zero wheel-body requests were forwarded.

`dependencies.json` records all 122 exact versions, target tags, origin URLs, expected compressed sizes, artifact SHA-256, metadata hashes, Requires-Python/Requires-Dist, activated extras and declared licenses. Every selected wheel has a hash and supported target tags. These are metadata-level compatibility checks, not tested binary imports.

The Linux PyPI PyTorch 2.15.0 wheel declares NVIDIA/CUDA dependencies for this target. CPU execution settings do not erase those packaging dependencies. They were included rather than silently replaced. The largest expected wheel payloads are:

| Package | Version | Expected compressed bytes |
|---|---|---:|
| nvidia-cudnn-cu13 | 9.26.0.51 | 595,329,497 |
| nvidia-cublas | 13.4.1.3 | 513,048,232 |
| torch | 2.15.0 | 483,605,887 |
| triton | 3.9.0 | 263,373,771 |
| nvidia-cusolver | 12.2.0.11 | 250,383,075 |

These were inspected only through index/version/sidecar metadata. None was downloaded or loaded. The source policy, not an inference device selection, produces this closure.

## License and model inspection

Version-specific publisher license expressions, classifiers, legacy excerpts and selected wheel declarations are recorded separately. Legacy labels are not promoted to modern SPDX or compatibility clearance. `LicenseRef-NVIDIA-Proprietary` in nvidia-cuda-cccl and nvidia-nvjitlink remains unresolved and UNKNOWN. Even a parseable declaration is not full wheel/bundled-notice clearance; package names were not used to infer licenses.

Heron remains `docling-project/docling-layout-heron` at `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`. Its card declares apache-2.0. The README/config/preprocessor bytes match the original inventory, and the API's weight metadata matches **171,658,996 bytes**, SHA-256 `00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c`. The minimal three-file inference payload remains **171,662,708 bytes**. Live metadata/card/config retrieval acquired only **8,504 bytes**, with weight URLs explicitly forbidden. This verifies pinned metadata identity, not the unacquired weight contents or complete model licensing.

## Cumulative accounting — no reset

| Component | Bytes |
|---|---:|
| Prior setup artifact payloads, carried forward | 397,781,165 |
| Prior metadata/duplicate-small-transfer allowance, carried forward | 134,217,728 |
| New metadata bodies, including all three resolver attempts, release audit and model metadata | 24,764,002 |
| Additional small/error/protocol-transfer allowance | 16,777,216 |
| Before future candidate payloads, conservative accounting | 573,540,111 |
| Expected selected Linux wheels | 3,396,860,472 |
| Expected complete minimal model files, conservatively counted again | 171,662,708 |
| Projected inclusive download total | **4,142,063,291** |

Measured metadata bodies are distinct from packet-level traffic; allowances are conservative reservations, not observed traffic. The download conclusion does not depend on allowance precision: wheels alone exceed the cap. Additional future runtime/image bytes are unknown and would only add cost; they are not silently assumed free.

Current reported allocated storage totals **1,986,494,464 bytes (1.850 GiB)** across the existing VM, retained runtime/download/API/evidence caches, all three Homebrew kegs, scoped logs, this preflight and the retained Experiment 006 raw/cache directory (53,460,992 allocated bytes). No old cache was subtracted or cleaned. `accounting.json` gives the individual roots and logical/allocated distinction. VM disks remain nominally 4+5 GiB; their sparse nominal lengths are not treated as physical allocation. Guest layers already inside the VM files are not added twice; APFS exclusive sharing was not established.

Assuming each future compressed wheel and minimal model file is fully allocated once, current allocation plus a 16 MiB metadata allowance and those cached payloads gives a **5,571,794,860-byte (5.189 GiB) planning subtotal**, before unpacked files, temporary extraction, duplicate copies or an additional interpreter/image. This is a planning scenario, not observed physical allocation or a guaranteed lower bound. No reliable unpacked-size bound is available from the acquired metadata; ZIP records were not fetched. Consequently the overall installed/cache gate remains UNKNOWN, with a failing full-retention scenario. No predicted fit is presented as observed.

## Failed attempts, controls and limitations

- The initial Docker formatted-info query referenced an unsupported template field. Its failure was preserved; the supported read-only query succeeded. No VM setting changed.
- Resolver attempt 01 stopped on a malformed legacy index filename (`pydantic-0.18-py36+-none-any.whl`). Such invalid index entries are now recorded and excluded, rather than mistaken for valid CPython 3.11 candidates. Client cancellations after the stop are retained as diagnostics.
- Attempt 02 stopped on a reset connection to the public nvidia-cusolver index. Attempt 03 used at most four upstream requests and one bounded metadata transport retry; it completed with exit 0, no retry needed, no gateway errors and no artifact requests. Each failed attempt, source hash, command, traffic count and original raw evidence remains separate. No attempt required falling back to wheel bodies.
- The first focused test used a loopback socket disallowed by the sandbox. Its guard test was made socket-free; the real gateway/resolver ran only through approved metadata-read permissions. No sudo, runtime install, cleanup or configuration workaround was used.
- Before publication, the initial raw-output location was found inside an ancestor Git root. Only this run's new raw evidence was relocated outside all Git roots by same-filesystem rename, preserving internal file contents. Prior runtime caches and historical runs were left in place; this does not remove any earlier raw-location caveat.
- The existing VM is still operational; current Docker context remains `default`, the dedicated Docker configuration is reused read-only, no containers were created, and the image inventory remains the original BusyBox image only. Colima configuration contents/stat identity match before/after. Normal runtime logging may change live disk allocation; no VM disk/cache was deliberately reconfigured or cleaned.

**304 offline tests passed**, zero failures/skips, on Python 3.11.13; reported pytest time 7.97s. Existing research dependencies were not reinstalled. All **218 pre-existing tracked files are SHA-256 identical**, including parser, Structure 0.2, dependencies, historical experiments and prior runtime evidence. Tests validate audit safeguards; they are not empirical Docling results.

Scientific baseline remains `ba82b2c7f71604d5bcc2859b1a05de112723107d`. The six frozen references remain agent_visual_checked with **zero independent human verifications**. No PDF processing or comparative scientific metric is reported. Historical NO-GO and provisioning uncertainty remain unchanged.

## Stop and next authorization

Stop after publishing this preflight. Do not acquire the current over-budget closure. The next useful authorization is **a separate metadata-only preflight of an explicitly selected CPU-only PyTorch distribution source/packaging policy**, retaining Docling 2.148.0, the same Heron revision and every existing cap. That would be a new packaging evaluation, not a silent correction of this result. Any later bounded wheel/license/unpacked-size acquisition needs separate payload authorization. Installation, model weights, smoke tests and the six-page benchmark stay blocked until all decisive gates pass and the user separately authorizes that stage.

Reproduction: `commands.md`. Immutable structured evidence: `summary.json`, `dependencies.json`, `model.json`, `licenses.json`, `accounting.json`, `resolution-evidence.json`, `runtime.json`, `validation.json`, `preservation.json`. Machine-specific raw responses, caches, collectors and prior attempt sources remain outside Git, identified by `external-evidence-manifest.json`.

Official protocol references: [uv compilation](https://docs.astral.sh/uv/pip/compile/), [uv indexes](https://docs.astral.sh/uv/concepts/indexes/), and [Python Simple Repository API / core metadata](https://packaging.python.org/en/latest/specifications/simple-repository-api/). Version-specific package/model provenance URLs and hashes are in the inventories.
