# CPU formula diagnostics and PP-FormulaNet-S admission — 2026-11-15

No mathematical recognition result was obtained. CodeFormulaV2's one authorized 64-token diagnostic timed out; the 256-token diagnostic was skipped. The selected official PP-FormulaNet-S runtime plans exceed the unchanged 7 GiB inclusive storage budget before installation. This is a runtime/resource outcome, not evidence of either model's mathematical quality.

Based on PR #24, commit `47505429c3e3b5e1713e91b0e0a85b9fded077cf`. All eight frozen development formulas and references are unchanged (`agent_visual_checked`, zero independent human verifications). No full-document detection ran.

## Observed CodeFormulaV2 diagnostic

Same pinned checkpoint `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`, crop SHA-256 `9b9b3cccafa6e482c591d1ad81c52c4d7daade04b5e63a730af286b8508c1e9d` (387×61 RGB), existing Linux aarch64 / CPython 3.11.13 / Docling 2.148.0 / torch 2.15.0+cpu. Only the explicitly authorized token cap and observational forward/streamer instrumentation differ. Existing preprocessing and generation settings are retained. This is separate from the historical 2048-token accuracy attempt.

| Measure | Actual observation |
|---|---:|
| Invocations / authorized maximum | 1 / 2 |
| Model/stage initialization | 3.610420 s |
| `generate()` entered | 7.461593 s after worker start |
| Generation observed without return | ≥112.298740 s |
| External wrapper wall time | 120.284840 s |
| Docker process lifetime | 120.047415 s |
| Exit / termination | 137 / externally timed out |
| Highest sampled kernel memory.peak | 644,243,456 B (614.4 MiB) |
| CPU time / mean occupied cores | 451.678432 s / 3.772 |
| Last memory.events OOM / OOM kill | 0 / 0 |
| Returned LaTeX / returned token count | null / null |

Actual kernel limits: memory.max=4,294,967,296 B, memory.swap.max=0, cpu.max=`400000 100000`; cpuset 0–3, four effective threads, network disabled. Existing model/package volumes were read-only; only a new isolated diagnostic volume was writable. The external watchdog killed only its owned container; no controller errors, running process or attached CLI remained. The sampled memory peak is a lower bound, not a measured final peak; warm file-cache accounting does not establish cold-start residency.

There was **no instrumented top-level forward entry, prompt streamer callback or generated-token callback**. Thus no prefill/decoding throughput was measured. Generation was observed stalled before these hooks; the exact internal cause remains UNKNOWN without a stack/profile. Zero observed callbacks does not establish zero internal generated tokens. Existing RoPE/tied-weight warnings remain unmodified. The second (256-token) diagnostic was not eligible because the first never returned. No further CodeFormula testing was performed.

## PP-FormulaNet-S identity and compatibility evidence

Official model: `PaddlePaddle/PP-FormulaNet-S`, pinned revision `0572450e501be9eb1b1cdb7e00fccf4b22fab4df`, declared Apache-2.0. Minimal runtime files are inference.json, inference.pdiparams and inference.yml: **234,424,065 bytes**. The expected weights SHA-256 is `b6392296d16e2a9f414c0a751d7ccbd1bd9d8272b68aab72df1d3875f35a7489`. These weights were **not acquired or verified**. The pinned model card alone was retrieved and its Git blob identity verified.

The selected official plan uses PaddlePaddle 3.3.1, PaddleOCR 3.7.0, PaddleX 3.7.2, OpenCV contrib 4.10.0.84, NumPy 2.3.5, ModelScope 1.40.3 and aiohttp 3.13.2. This is a partial admission inventory, **not a resolved installation lock**. PaddleX requires NumPy<2.4 and the exact OpenCV contrib package, so the existing candidate's NumPy 2.4.6/headless OpenCV 5 cannot satisfy these constraints. No existing dependency was changed.

An official **cp311 Linux aarch64 CPU wheel exists** at the [Paddle CPU index](https://www.paddlepaddle.org.cn/packages/stable/cpu/paddlepaddle/). Its absence from PyPI does not establish runtime unavailability. Initial quoted-only link parsing missed the index's unquoted hrefs; HTMLParser corrected this before the admission decision, with regression coverage. The vendor wheel is 92,017,199 compressed bytes; the index provides no expected SHA-256, so full-payload hash verification remains required. macOS ARM64 CPython 3.11 wheels also exist. Installed ABI/operator compatibility remains UNKNOWN on both routes because no environment was created/imported.

Versioned official source exposes `FormulaRecognition(model_name="PP-FormulaNet-S", model_dir=..., device="cpu", cpu_threads=4)` through PaddleOCR, using PaddleX's runner/static path and UniMERNet preprocessing/decoding. This is not the large/plus-model Transformers path. Source tags resolve to commits recorded in pp-source-commits.json; the PaddlePaddle v3.3.1 repository tag query returned 404 and remains UNKNOWN, rather than a fabricated source commit. Published vendor accuracy/latency figures are not this experiment's measurements.

## Storage admission: stop before acquisition

Immutable limits: **7,516,192,768 B inclusive allocation**, ≥12,884,901,888 B host free, 4 GiB RAM / zero swap / four cores / 120 s. Existing assets are retained; VM allocation, archived wheels, both existing CodeFormula copies, previous evidence and new diagnostic data count inclusively.

At the admission snapshot, allocated storage was **6,724,931,584 B**, leaving **791,261,184 B**; host free was 18,159,206,400 B. Strict bounded HTTP Range requests read ZIP directories only; a server ignoring Range is rejected before reading a full wheel body. ZIP sizes are declared metadata, not measured installed allocation or exclusive APFS blocks.

| Selected route (incomplete subset + one minimal model copy) | Declared logical bytes | Per-file 4 KiB estimate | Inclusive estimate, no work space | Over 7 GiB |
|---|---:|---:|---:|---:|
| Linux: seven packages + model | 796,399,322 | 817,713,152 | 7,542,644,736 | 26,451,968 |
| macOS: Paddle + OpenCV + NumPy + model only | 849,211,036 | 860,266,496 | 7,585,198,080 | 69,005,312 |

Even logical file totals exceed the admission remainder by 5,138,138 B (Linux) and 57,949,852 B (macOS), before other required dependencies. A 128 MiB planning work margin raises the projections to 7,676,862,464 and 7,719,415,808 B. The estimates optimistically omit archives, pyc, installation staging, directories, remaining dependencies, new images and duplicate model copies; Linux additionally assumes other compatible dependencies can be reused read-only. Actual physical allocation, compression and sharing can differ; this is conservative prospective admission failure, not an observed failed installation or proof that every possible historical runtime is infeasible.

**Neither route passed admission.** No complete PP wheel, model weights, environment, inference call or native macOS resource-enforcement test followed. The remaining closure and bundled native license review were stopped, not asserted complete. No old asset was deleted to make room. A new budget would need to cover the full closure and transient peak, not merely the 26 MB partial-estimate gap; 8 GiB is at most a planning target, not a measured fit or authorized limit.

## Recognition results

| Frozen target | PDF page | PP-FormulaNet-S status | Mathematical correctness |
|---|---:|---|---|
| log_eq2 | 4 | Not executed: storage admission | null |
| log_eq4 | 4 | Not executed: storage admission | null |
| attn_fraction | 4 | Not executed: storage admission | null |
| attn_heads | 5 | Not executed: storage admission | null |
| attn_ffn | 5 | Not executed: storage admission | null |
| nature_weights | 10 | Not executed: storage admission | null |
| nature_softmax | 11 | Not executed: storage admission | null |
| attn_positional | 6 | Not executed: storage admission | null |

PP: **0/8 attempted, 0/8 completed, 8/8 unexecuted**. CodeFormula: one first-crop latency invocation, no complete return; not an eight-formula accuracy experiment. Exact/format-normalized agreement, numerator/denominator, radical scope, scripts, summations, grouping, symbol errors and complete-expression correctness are all **null**, with reasons in predictions.json/results.json. No error counts are invented from missing predictions. Detection-versus-transcription and candidate-quality comparisons are unsupported. Original-versus-reconstructed figures are unavailable because no LaTeX returned; rendering a reference would misrepresent a prediction.

## Licensing, preservation and recommendation

Publisher metadata declares Apache licenses for model/framework/OpenCV and BSD core terms for NumPy; its metadata also lists bundled native terms. Version-specific PaddleOCR/PaddleX sources have Apache headers. ModelScope's collected license field is null. No material restriction on private local research was identified in the checked declarations, but **complete bundled/transitive clearance is UNKNOWN**. Missing metadata is not PASS. Actual source hashes, URLs and model/file identities are retained.

Stop further CodeFormula calls on this pinned stack under the current deadline; a lower token cap did not produce observable decoder progress. PP-FormulaNet-S remains a reasonable candidate to measure, **not a measured better recognizer**. The shortest next step needs separate explicit storage authorization after completing the small remaining closure/peak estimate, followed by one isolated CPU crop call. Preserve CodeFormula assets and require expected/actual artifact hashes, no dependency changes to Docling, and the same first-failure boundary. Neither this run nor PR #24 justifies Formula Structure v0 or production adoption.

All 503 pre-existing tracked files, frozen selection/references and production contracts remain unchanged. The 21 new model-free regressions cover exact Range handling, unsafe ZIP metadata, vendor-index links, budget/null-result semantics and the conditional second invocation. The full existing offline suite passed **615 tests**, zero failures/skips. Raw events, warnings, cgroup samples, exact commands, metadata and private configuration remain outside Git with an evidence manifest. No new infrastructure validation, runtime installation, production integration or full-document inference occurred.

Final publication sampling (including the new external evidence copy): retained **6742237184 B**, host free **13629808640 B** (12.69 GiB). Highest sampled inclusive allocation **6742237184 B**; minimum sampled host free **13629808640 B**. Both gates remained satisfied at recorded samples; transient peaks between samples remain UNKNOWN. Guest free: root 2,123,157,504 B, Docker volume 1,946,140,672 B. Background activity changed host free space; do not attribute the entire change to this run.
