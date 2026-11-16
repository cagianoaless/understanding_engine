# PP-FormulaNet-S clean isolation attempt — 2026-11-16

**Comparison remains INDETERMINATE.** The single authorized clean environment fixed the previous Paddle→ModelScope→Torch/NCCL import conflict. However, the first crop's predictor construction failed because the formula decoder needs the optional **tokenizers** package. No neural recognition call occurred, no LaTeX was returned, and the other seven targets were not executed. No package addition, environment workaround or retry followed this failure.

This is new measured runtime evidence, not a mathematical-quality benchmark result. The requested eight-formula comparison could not be completed under the one-correction boundary. The omission of the formula-specific optional dependency was an implementation/preparation oversight; it is not evidence of poor model quality or an unavoidable GPU limitation.

## Preserved baseline and inputs

Based on PR #26 / `09c90958f7c25d4ce03644a6693147d46c6fe18e`. Its eight CodeFormulaV2 predictions, original environment, source crops, evaluation policy/results and historical experiments were not modified or rerun. The same eight crop hashes and byte counts were verified in the existing Colab session before the attempt. No PDFs, new crops, reference LaTeX or unrelated local data were transferred. Inputs retain the original PDF hashes/pages/boxes and explicit frozen preprocessing provenance.

The existing `understanding-engine` T4 session remained available and was reused. No session was created, restarted or terminated. Two exec transport disconnects happened before acquisition code ran; read-only checks confirmed no acquisition/model/output markers. A later exec reconnect performed acquisition once. SSH was occupied and never forcibly disconnected. Small script/input/hash files were transferred through the official CLI; ground-truth LaTeX stayed local. All essential evidence was downloaded before this report.

## Single environment correction: measured success with limited scope

A **new venv without system-site-packages** reused the retained official CUDA-13 Paddle GPU 3.3.1 wheel, verified at SHA-256 `dc920c514987a235ed1a54c6d2d3d82a9b8d8f056253a9fb80cc8fd2a176ac45`. Python remains the VM's CPython 3.13.16. PaddleOCR 3.7.0 / PaddleX 3.7.2 and the declared dependency closure were resolved with source builds disabled, then installed from an 89-artifact, hash-pinned plan. Seed/bootstrap packages and all active distribution versions are recorded separately in runtime.json.

Measured checks:

- `include-system-site-packages = false`; user site disabled; interpreter launched with `-I` and no inherited PYTHONPATH/PYTHONHOME/VIRTUAL_ENV.
- `find_spec("torch") is None` before and after importing PaddleOCR; no Torch module imported.
- Paddle CUDA compiled, one Tesla T4 visible, CUDA 13.0 / cuDNN 9.13.0; NVIDIA driver 580.82.07.
- A one-element Paddle CUDA operation succeeded. This verifies a basic native execution path, not formula inference compatibility.
- No system package, preinstalled CUDA/Torch/NCCL file, system-wide loader path or old environment was overwritten. No LD_LIBRARY_PATH override, monkey patch or binary patch was used.
- Setup/import/probe phase took **164.457 s**. Existing CodeFormula outputs/locks/scripts were hashed before and after: **70 remote files unchanged**, zero repeated CodeFormula neural calls.

The historical setup-result.json says PASS for this isolation/import/tiny-operation phase. That status is preserved as measured, **not promoted to full formula readiness**.

## Exact pinned model

Only `PaddlePaddle/PP-FormulaNet-S@0572450e501be9eb1b1cdb7e00fccf4b22fab4df` was acquired. No plus/L variant or alternative model was selected. Declared model license remains Apache-2.0.

| File | Bytes | Independently computed SHA-256 |
|---|---:|---|
| inference.json | 504,505 | `2c8fc31a94d461a7325fe06e8cbaa5db6c5658c490f74d3d6116defe8c859d6f` |
| inference.pdiparams | 231,675,001 | `b6392296d16e2a9f414c0a751d7ccbd1bd9d8272b68aab72df1d3875f35a7489` |
| inference.yml | 2,244,559 | `08b21c2d255041008266b8fb947758e9731eafff191568af21da5a4b9c9dd5a0` |

Total: **234,424,065 B**. Weights match the frozen SHA-256; JSON/YAML match their frozen Git-blob identities as well as their newly recorded SHA-256 values. Original crop and model hashes were checked again in the first worker. Weights/runtime payloads remain remote, outside Git; only small evidence was downloaded locally.

Configuration was frozen before the attempt: explicit `model_name="PP-FormulaNet-S"`, `device="gpu:0"`, batch one, FP32, HPI/TensorRT/MKLDNN disabled, four CPU threads, original official preprocessing and an external **180 s** deadline. CodeFormula's earlier FP16 configuration was not changed. No margin, resolution, threshold or generation tuning occurred.

## First target: constructor failure before recognition

`attn_fraction` used the exact crop SHA-256 `9b9b3cccafa6e482c591d1ad81c52c4d7daade04b5e63a730af286b8508c1e9d`. The worker imported PaddleOCR and began predictor construction, but failed before the `predictor_invoked` event or `model.predict()` call:

```text
FormulaRecognition -> FormulaRecRunnerPredictor._build
 -> build_postprocess -> UniMERNetDecode -> require_deps
DependencyError: UniMERNetDecode is not ready for use:
    tokenizers
RuntimeError: A dependency error occurred during predictor creation.
```

The full original exception chain is in first-failure.json and the external stderr. Retained package metadata explains the gap: PaddleOCR's base requirement is `paddlex[ocr-core]`. PaddleX declares `tokenizers>=0.19` under `ocr`, `base` and other extras, while the `ocr-core` closure used here does not include it. Thus a successfully resolved/importable base installation was **not the complete formula-specific dependency closure**. The clean environment also removed the formerly inherited tokenizer package.

| First-attempt observation | Measured value |
|---|---:|
| Worker exit / timeout | 1 / false |
| External wall time | 18.883 s |
| Worker lifetime | 18.175 s |
| Observed failed-constructor interval | 9.114 s |
| Peak process RSS | 1,315,074,048 B |
| Paddle tensor allocator peak allocated/reserved | 231,670,272 B / 231,670,272 B |
| Highest sampled process GPU memory | 429,916,160 B (410 MiB) |
| Neural predictor invocations / returned LaTeX | 0 / none |

These are **failed-initialization costs**, not recognition latency, successful model-load time or model-inference memory requirements. GPU process samples are lower bounds; Paddle tensor counters may omit native/static-inference allocations. Allocation of model buffers does not establish that a neural prediction ran. No OOM or external timeout was observed. The owned worker exited and process cleanup was verified.

No tokenizers install or second target attempt followed the failure, respecting the single-correction limit. A future tightly scoped tokenizer addition and first-crop retry would need separate authorization; its success is not assumed. Reintroducing inherited Torch or changing CUDA binaries is not justified by this error.

## Eight-image accounting and comparison

| Target | New PP status | LaTeX / mathematical scores |
|---|---|---|
| attn_fraction | Initialization failed; neural call absent | null |
| attn_heads | Not executed | null |
| attn_ffn | Not executed | null |
| attn_positional | Not executed | null |
| nature_weights | Not executed | null |
| nature_softmax | Not executed | null |
| log_eq2 | Not executed | null |
| log_eq4 | Not executed | null |

The selected denominator remains **8**: one target preparation attempt, one initialization failure, **zero neural predictor invocations**, zero completed expressions, seven unexecuted targets, zero timeouts. All PP exact/format-normalized, syntax/rendering, formula-core, full-output, fraction/radical, script/limit, named-identifier, vector/scalar and prose metrics remain **null**, with zero scoreable predictions. No PP image can be reconstructed honestly without model output. Failed/unexecuted targets are not counted as eight mathematically incorrect formulas.

The preserved CodeFormula baseline remains: 8 attempted/returned, 7 EOS returns, 1 incomplete native repetition stop; 4/8 provisionally source-faithful under PR26's explicit policy, three identified whole-output problems, one incomplete/unknown; exact/format string matches 0/8 and TeX compilation 6/8. These historical judgments were not recomputed or used as remote inputs. Their strict spelling counts are not mathematical equivalence tests.

The known Nature `a` versus source `α` reference discrepancy remains explicit and unchanged. With no new PP predictions, the affected glyph and every other PP quality measure are unscoreable. All references/reviews remain `agent_visual_checked`; independent human verifications=0.

## Decisions

1. **Which has fewer complete-expression failures?** Not determinable as a recognition-quality comparison. CodeFormula is operational with preserved outputs; PP has a constructor failure, not eight wrong transcriptions.
2. **Which preserves identifiers/source notation better?** Unknown for PP. CodeFormula's prior vector/identifier limitations remain visible; no new ranking is supported.
3. **Which provides better LaTeX for a future AST?** Unknown comparatively. No PP LaTeX exists. Visually reconstructed formula cores and machine-navigable syntax/identifier grouping are different capabilities.
4. **Are differences meaningful on eight exposed samples?** There are no comparable PP quality observations. Even a completed eight-sample run would remain provisional and would not establish statistical generalization.
5. **One, both or neither as authoritative?** **Neither neural recognizer is authoritative.** Original PDF characters/Unicode/coordinates remain authoritative. The prior limited CodeFormula research-prototype recommendation is unchanged; PP selection/AST-readiness remains untested.

New measured gates: isolation/import/tiny CUDA PASS; formula dependency completeness and predictor construction FAIL; recognition NOT_EXECUTED; quality UNKNOWN. No frozen references, historical experiment or production contract changed. No AST, viewer, Inspector, extra model or inference retry was implemented.

Remote snapshots show the new clean runtime/model/evidence directory allocated **6,842,580,992 B** (excluding the old directory and base VM), with **106,172,895,232 B** remote free. These are retained snapshots, not measured transient peaks or a claim that the stack fits historical local CPU storage limits. No user cleanup or local neural-runtime installation occurred. Essential raw evidence is preserved outside Git with hashes. The existing Colab session remains running; release it manually after reviewing the downloaded results.

Validation: **654 offline tests passed in 19.76 s**, zero failures/skips. All **546 pre-existing tracked files** remain byte-identical; 17 new model-free checks cover identities, sequencing, isolation boundaries and reporting a failed constructor without invented quality. Failure accounting reproduced byte-for-byte. Exact-head CI is recorded on the PR after publication.
