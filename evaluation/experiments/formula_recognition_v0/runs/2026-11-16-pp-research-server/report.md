# PP-FormulaNet-S on an isolated shared research GPU — 2026-11-16

**PP produced eight genuine crop-recognition outputs. It did not improve complete-expression recognition over the preserved CodeFormulaV2 baseline: both have 4/8 provisionally source-faithful complete expressions. CodeFormula preserves substantially more of the two LoG formula cores.** Neither recognizer is authoritative. A failure-aware Formula Structure v0 research prototype remains justified, preferably starting with CodeFormula hypotheses and explicit rejection/uncertainty; this experiment does not justify adopting PP as the replacement.

All references and new judgments are **agent_visual_checked**, with **zero independent human verifications**. These are eight development-exposed crops, not a held-out or statistically conclusive benchmark. No production parser, mathematical AST, viewer, annotations, old reports, CodeFormula predictions or dependency environment was modified or rerun.

## Observed quality

The same original PNG bytes, regions, PDF identities, preprocessing and eight-image denominator from PR26/27 were retained. References stayed on the Mac; only the eight images, scripts, model/runtime files and identity manifests reached the server. `predictions.json` contains the exact official decoded `rec_formula` strings and native results, with portable input paths. The official decoder itself applies ftfy and its existing normalization; **we applied no additional cleanup or reference-based correction**. Pre-postprocessor token strings/EOS status are not exposed by this API.

| Frozen expression | PP complete output | Preserved CodeFormula complete output | Main observation |
|---|---|---|---|
| Attention fraction | Correct | Correct | Fraction, radical, transpose and d_k retained |
| MultiHead | Correct | Correct | Head indices, argument groups and W^O retained |
| FFN | Correct | Correct | Both affine stages and all four indices retained |
| Positional encoding | Correct | Correct | Both lines/exponent scopes; identifier semantics remain unresolved |
| Nature weighted sum | Incorrect | Incorrect | Both lose two bold vector glyphs; alpha-reference conflict remains unscoreable |
| Nature softmax | Incorrect | Incorrect | Formula core retained; bold vector x lost |
| LoG (2) | Incorrect | Incomplete/unknown | PP loses fraction/sums, emits malformed underbrace/array and repeated spaces; CF retains the core but previously stopped incompletely |
| LoG (4) | Incorrect | Incorrect | PP corrupts formula and prose; CF retains the core but includes malformed/extraneous prose |

“Correct” follows the preserved policy: visible mathematical content/grouping and source-sensitive vector notation; ordinary named-function font styling is presentation. It does **not** establish a machine-navigable AST or symbol alignment. The Nature Latin `a` versus source Greek alpha discrepancy was not corrected: the affected glyph is unscoreable, not a PP substitution. Other independently visible errors (lost vector bold) still support an incorrect full-output judgment.

Exact LaTeX agreement and the frozen line-ending/outer-strip comparison are **0/8 for both systems**. These are spelling measures, not mathematical equivalence. Cached local Tectonic compiled the unmodified PP bodies in the same common `align*` context for **6/8**, matching the historical CF count; both PP LoG outputs fail. No repaired rendering replaces a failed one. See [comparison.png](comparison.png), [the preserved CF comparison](../2026-11-16-t4-crops/comparison.png), raw predictions and individual component decisions.

| Enumerated component | PP correct / denominator | PP incorrect / missing / ambiguous / unscoreable | Preserved CF correct / denominator |
|---|---:|---:|---:|
| Fraction membership | 2/4 | 0 / 2 / 0 / 0 | 4/4 |
| Radical scope | 1/1 | 0 / 0 / 0 / 0 | 1/1 |
| Ordinary subscripts | 17/24 | 1 / 6 / 0 / 0 | 24/24 |
| Ordinary superscripts | 7/9 | 0 / 2 / 0 / 0 | 9/9 |
| Summation operators | 3/5 | 0 / 2 / 0 / 0 | 5/5 |
| Summation limits | 3/6 | 1 / 2 / 0 / 0 | 6/6 |
| Delimiter groups | 15/22 | 2 / 5 / 0 / 0 | 22/22 |
| Bold vector glyphs | 0/3 | 3 / 0 / 0 / 0 | 0/3 |
| Exact star glyph identity | 0/4 | 0 / 2 / 2 / 0 | 0/4; four ambiguous |
| Alpha-reference conflict | 0/1 | 0 / 0 / 0 / 1 | 0/1; one unscoreable |

These are the original enumerated core-relation inventory, including observable fragments of malformed/incomplete outputs, not comprehensive symbol accuracy. A locally surviving script does not validate its surrounding tree. Extra underbraces, corrupted prose, missing equalities/denominators and repeated spacing remain explicit failures; no inference about hidden token-cap termination is made. Native output does not supply reliable model confidence, source-character membership or one-to-one glyph correspondence.

PP groups Attention/MultiHead/Concat/head/FFN using `operatorname`, whereas some CF outputs contain bare letter sequences. PP still emits `sin`, `cos`, `PE`, and `pos` as letter sequences in positional encoding; CF uses explicit `sin`/`cos` commands. Thus some PP identifier groups are easier to inspect, but there is no across-the-board AST-readiness advantage. Both lose vector/scalar distinctions. Neither generated LaTeX string is a source-aligned mathematical AST.

## Execution, failures and isolation

The GPU was an **NVIDIA RTX 5000 Ada Generation, 32,760 MiB**, driver 575.64.03, on Ubuntu22.04.5/x86_64. Five pre-existing compute processes occupied about4,453 MiB; three initial utilization samples were0%. No scheduler command/configuration was found; the user explicitly permitted shared use when capacity is available. The run checked at least4,096 MiB free and at most10% utilization before each crop; all eight were admitted. Existing processes were neither signalled nor modified. These are availability observations, not proof of zero scheduling interference.

A new mode0700 directory on local ext4 contained the venv, wheels, model, all configured caches, temporary files, crops and logs. Existing CPython3.12.3 and uv0.7.8 were read only. The official CPython3.12 CUDA12.6 Paddle GPU3.3.1 binary was selected for driver compatibility; the system CUDA11.5 toolkit was not used. PaddleOCR3.7.0, PaddleX3.7.2 and the complete final **88 hash-pinned candidate artifacts** are recorded. This differs from the old Colab CUDA13/Python3.13 environment, without changing either model or preprocessing. No source builds, Torch inheritance, system-site-packages, shared package changes, loader-path hacks or binary patches occurred.

Landlock ABI4 enforces persistent writes under the exact owned root. An initial strict guard blocked CUDA's own thread-name write at `/proc/self/task/<tid>/comm`, yielding `cuInit=304`. **The user subsequently approved a prospective exception for the experiment process's own task metadata.** Only WRITE_FILE/TRUNCATE rights were added to that PID-specific task subtree; no global `/proc` write access or file creation/removal right was added. Positive own-thread and negative other-process/persistent-sibling probes passed, followed by `cuInit=0` and a real one-element Paddle GPU operation. Each eventual neural worker installs its own guard. Audited stdlib supervisors, transfer and cleanup code write only the owned paths. This is not a read-isolation sandbox; no claim is made that arbitrary untrusted code cannot read the host.

The decoder audit initially checked declared class dependencies and added tokenizers0.23.3. The **first real predict call loaded and ran, but failed in official postprocessing because method-local `ftfy` was absent**. This was our dependency-preparation oversight. Full active-source inspection then found exactly that method-local import. One bounded completion installed only ftfy6.3.1, no replacements; its wcwidth dependency was already present. A neutral official `post_process("x")` check and pip check passed. The failed attempt is preserved separately and was not scored as a returned formula. There were **9 actual predict API invocations: one postprocessing failure, then8 decoded returns**, zero external timeouts, and verified worker exit after every call. No further candidate inference followed.

Other diagnostic/export issues (a nonexistent DATA_HOME import, a missing synthetic fixture, the O_TRUNC right needed by the approved metadata operation, an incorrect AST assumption about where tokenizers is declared, a finalizer launched with Python3.10, and an archive filename shadowing bug) were corrected without altering runtime packages, model behavior or existing evidence. Original failure sources/logs are retained externally; the first strict-guard snapshot is separately hashed. No failed model output was silently repaired or overwritten.

The exact model is `PaddlePaddle/PP-FormulaNet-S@0572450e501be9eb1b1cdb7e00fccf4b22fab4df`. Its three files total234,424,065 B; weights match `b6392296d16e2a9f414c0a751d7ccbd1bd9d8272b68aab72df1d3875f35a7489`. Direct server Hugging Face access failed before creating a file. The Mac acquired only those official pinned files, verified every frozen hash, transferred them, and the server independently verified them again before/after inference. No complete PDF, reference LaTeX or other model was transferred.

## Measured cost

| PP target | Model init s | predict incl. official preprocessing/decoding s | Process wall s | Peak RSS MiB | Highest sampled process VRAM MiB |
|---|---:|---:|---:|---:|---:|
| attn_fraction | 3.343 | 0.439 | 8.642 | 2137.2 | 682 |
| attn_heads | 3.366 | 0.458 | 8.638 | 2139.4 | 682 |
| attn_ffn | 3.312 | 0.458 | 8.652 | 2150.6 | 680 |
| attn_positional | 3.357 | 0.456 | 8.644 | 2089.6 | 678 |
| nature_weights | 3.280 | 0.453 | 8.639 | 2003.1 | 688 |
| nature_softmax | 3.348 | 0.460 | 8.638 | 2029.5 | 694 |
| log_eq2 | 3.380 | 0.760 | 8.904 | 2180.6 | 682 |
| log_eq4 | 3.368 | 0.784 | 8.916 | 2240.2 | 682 |

Maximum measured process RSS: **2,349,072,384 B**. Highest observed per-process VRAM sample: **727,711,744 B (694 MiB)**, a sampled lower bound, not exact peak. Paddle tensor allocation counters report231,670,272 B for each call and omit substantial static/native inference allocations. No cgroup/process-memory cap was imposed on this native shared-server run. CPU affinity and inference-thread variables were limited to four; processes ran at nice19. External180-second timers never fired. CPU observations are in per-page results and raw resources; no unsupported OOM counter is invented.

Historical CodeFormula prediction time was2.543–15.350 s on a **different T4 GPU, FP16, CUDA13**, with different memory telemetry. PP's mean predict time here was0.534 s; it is not a controlled model-speed or memory-efficiency ranking.

Maximum observed regular-file allocation during setup was **11,416,215,552 B (10.632 GiB)**, sampled every5s with hard-link deduplication. Directory blocks are excluded from that series, so the exact transient whole-tree peak is **UNKNOWN**. Retained whole-tree `du` before final ZIPs was9,574,924,288 B. No arbitrary storage budget was applied; sufficient filesystem capacity remained and no existing assets were deleted to make room.

## Download and mandatory cleanup

The final evidence ZIP is **1,469,501 B**, SHA-256 `cf1c64dd8444e66060cc7340bc88bf636d06c9b7282097039bbceaf0f4472673`. All154 members, individual SHA-256 values, byte counts and ZIP integrity were independently checked on the Mac before cleanup. It contains raw/native results, events/resources, configs, package reports/locks and diagnostics, excluding wheels, weights and the venv. Local external evidence and model/crops remain available outside Git.

Cleanup validated the original canonical path, UID/device/inode marker, mode0700, ownership/filesystem of every entry, absence of nested mounts and live owned processes/open handles, and the verified-download acknowledgement. lsof excluded only three disjoint FUSE portal mounts that produced unrelated stat warnings; the owned ext4 tree was never excluded. Descriptor-relative traversal unlinked symlinks without following their targets. **The exact owned directory was removed; an independent later SSH check confirmed it absent.** No other directory or research job was cleaned.

- Initial filesystem available: **74,644,930,560 B**.
- Immediately before cleanup: **65,066,541,056 B**.
- Immediately after cleanup: **74,644,422,656 B**.
- Observed recovered: **9,577,881,600 B (8.920 GiB)**.
- Remaining owned remote files: **0**; independent later free-space reading74,644,414,464 B.

This measured filesystem delta includes concurrent activity and directory/metadata effects; it is not inferred from archive logical sizes. All protected research files/environments were intentionally preserved. The Colab session was not contacted, restarted or terminated.

## Recommendation and reproducibility

There is **no PP quality advantage on these eight crops**: 4/8 complete correct for each, with more missing core relations and one additional definite catastrophic output for PP versus CF's incomplete/unknown LoG(2). CodeFormula is provisionally preferable for the first failure-aware Formula Structure research prototype; PP may remain an optional hypothesis for future independently reviewed comparison. Neither should be authoritative or automatically accepted. A small independently human-reviewed set of unseen, clean and prose-adjacent formulas should precede any deployment conclusion. Source alignment, LaTeX syntax parsing, AST construction and mathematical correctness remain separate unsolved capabilities.

See commands.md, inputs/protocol/isolation-amendment, immutable external-evidence hashes, runtime/installed-artifacts, predictions/results/adjudications, and cleanup.json. No AST, new benchmark, PDF detection, accuracy-driven tuning or production integration was performed. Full offline regression and preservation results are recorded in validation.json; exact-head CI is linked from the PR.
