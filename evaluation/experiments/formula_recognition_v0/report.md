# Formula Recognition v0 — blocked before inference

**Execution BLOCKED; formula-recognition quality INDETERMINATE.** No formula
weights, full tokenizer payloads or candidate packages were downloaded. No model
was initialized or imported, no inference ran, and no VM/container was started.
This is an incomplete experiment with a reproducible resource decision, not a
negative measurement of Docling recognition quality.

Parent: PR #22, `60cdde1da95f76ea3e9b7e426bee750e522c8749`.
All previous constraints, experiments, source contracts and results remain intact.

## Observed blockers

The current host reserve fails before acquisition. [Final measured snapshot](storage-final.json)
reuses the original allocation inventory and adds retained subsequent evidence;
regular files are deduplicated by device/inode. Sparse VM files are counted by
allocated blocks, not nominal capacity. Guest layers are already inside those
host VM files and are not added again.

| Observation / projection | Bytes | Interpretation |
| --- | ---: | --- |
| Available host space at resource snapshot | 18,434,473,984 | **17.17 GiB**, below reserve |
| Required host reserve | 21,474,836,480 | 20 GiB, unchanged |
| Deficit just to reach reserve | 3,040,362,496 | Additional acquisition/work space would also be required |
| Current inclusive regular-file allocation | 5,396,389,888 | About 5.03 GiB; not a peak or APFS-exclusive measure |
| Remaining under 6 GiB | 1,046,061,056 | Before model, staging, work and further evidence |
| Entire formula-model repository payload | 639,800,205 | Metadata-declared, not measured allocation |
| One-copy total plus 128 MiB work allowance | 6,170,407,821 | Arithmetic fits, **strategy and peak unverified** |
| Two-copy total plus 128 MiB work allowance | 6,810,208,026 | **367,757,082 B over the 6 GiB cap** |

The original host/guest retained-copy method therefore fails projected admission.
A guest-only canonical copy might fit, but has not been implemented, verified or
demonstrated to avoid full-size temporary/cache duplicates. No such workaround was
executed. The 128 MiB allowance is a planning assumption, not an established peak.
If retaining two copies is required, a prospective **7 GiB** budget would cover
this arithmetic projection with some margin; it is **not authorized**, and actual
transient allocations would still need guarding. No existing data was cleaned,
deleted, resized or moved to make space.

An earlier snapshot before final test/evidence accounting was 5,382,258,688 B;
[that observation](storage-snapshot.json) is retained, not overwritten. Final accounting
also includes 13,148,160 B of retained pytest temporaries. These are measured
snapshots, not continuous transient peaks; APFS exclusive sharing is unknown.

The initial sandbox-only `colima status` incorrectly reported **not running**.
A permission-approved **read-only** query corrected this: the existing VM is
already running, Linux ARM64 under Virtualization.Framework, Docker Engine 29.5.2.
All listed experiment containers are exited. No VM/container was started or
changed. The Docker context remained `default`. Guest `df` reports **2,123,157,504 B**
free on root and **2,608,353,280 B** on Docker data. This capacity is sufficient for
the simple model-byte projection, but does not establish transient/installed fit.
Current cgroup counters and neural imports remain UNKNOWN. Historical successful
controls and smoke results remain historical; provisioning peak remains UNKNOWN.

[Resources](resources.json) separates these gates. Host reserve is FAIL; the
two-copy projection is FAIL; current allocation and measured guest capacity are
PASS; ARM64/BF16 import/execution compatibility, one-copy peak and formula-model
execution are UNKNOWN. Any decisive unknown continues to block execution.

## What the pinned implementation actually selects

Nine relevant **actual installed package source files** were read through Docker's
archive API from the existing stopped install container, without starting it or
importing code. All nine are byte-identical to the exact official Docling source
commit already registered in Experiment 006:
`0fa0918d16de7769d942f9b06ca18cb673cbbc2e`. Current package METADATA confirms
Docling-slim 2.148.0 and Transformers 5.22.1. This is a selected-source verification,
not a fresh hash/import audit of the whole 103-package environment. One initial
lookup of an upstream documentation example failed because it is not packaged;
that read error is preserved, not counted as model failure. The example was
inspected upstream only. Original host wheel/configuration files are absent at
their former temporary paths; no cause is inferred and nothing was reacquired.
[Implementation audit](implementation-audit.json) records all ten upstream blobs,
the nine installed-file matches and their SHA256s.

- [`PdfPipelineOptions.do_formula_enrichment`](https://github.com/docling-project/docling/blob/0fa0918d16de7769d942f9b06ca18cb673cbbc2e/docling/datamodel/pipeline_options.py#L2223)
  enables the **`CodeFormulaVlmModel`** stage in the standard PDF pipeline.
  The default preset is **`codeformulav2`**, not the old standalone CodeFormula
  implementation or another model selected from newer documentation.
- The preset selects **`docling-project/CodeFormulaV2`**. It contains no immutable
  revision; the Transformers engine falls back to `main`. This run resolved that
  branch once to **`ecedbe111d15c2dc60bfd4a823cbe80127b58af4`** and freezes that
  identity for any continuation. No unrestricted model download occurred.
- Model metadata identifies **Idefics3ForConditionalGeneration**, with
  **315,467,328 BF16 parameters**. The weight file is **630,993,616 B**, expected
  SHA256 `4b04e77af34c4e682a7ab1617628340d658f3c3dcd12456dd2a7fff805cf79d2`.
  This is an LFS metadata hash; the payload has **not** been acquired or verified.
- The required family of artifacts includes model/generation configs, the
  Idefics3 processor/image config, chat template, tokenizer configuration,
  special/added tokens, vocabulary and tokenizer JSON. [Model inventory](model-inventory.json)
  records every repository file, length, URL, Git blob and known SHA256. Missing
  SHA256s are explicit; Git SHA1 is never represented as SHA256. Only six small
  card/config documents, **5,294 B total**, were fetched and blob-verified, plus
  the **3,292 B** API metadata response. No weights or full tokenizer/vocab payload.
- The Transformers implementation explicitly supports CPU. BF16 CPU execution
  on this exact ARM64 environment is **not measured**. No obvious new package is
  required by the static path, but that is not a successful import/load test.
  The original 103-package closure remains pinned, including Transformers 5.22.1,
  Torch 2.15.0+cpu, Torchvision 0.29.2+cpu, Accelerate 1.15.0 and Tokenizers 0.23.3.
  No dependency was resolved, installed or upgraded.

The [revision-specific model card](https://huggingface.co/docling-project/CodeFormulaV2/blob/ecedbe111d15c2dc60bfd4a823cbe80127b58af4/README.md)
declares **CDLA-Permissive-2.0**. The [publisher's terms](https://cdla.dev/permissive-2-0/)
permit use; sharing the covered data requires providing the license text, and
results have separate permissive treatment. These declared terms identify no
material private-local-research restriction in this agent review. This is not
exhaustive legal/redistribution clearance, and does not replace the existing
package/native-library notices or establish rights from keyword matching.

## Detection, crops and raw-output separation

The audited stage enriches items already classified **FORMULA**. It is not an
independent full-page mathematical detector. Missed formulas and formulas labelled
text/picture must therefore be recorded as detection failures before transcription
is judged. The end-to-end path must receive original pages, never target boxes or
reference LaTeX, and retain every unwanted formula detection.

Important source-level observations, **not execution results**:

1. Image preparation uses the stage's **1.67 scale (~120 DPI)** and **0.18 expansion
   factor**. The preset's separate `scale=2.0` must not be mistaken for the class
   value used by `prepare_element`. Processor resizing, splitting, padding, RGB
   conversion and normalization then apply, with configured longest edge 2048
   and maximum tile edge 512. Margins may include numbers or neighbouring prose.
2. [`VlmEngineInput`](https://github.com/docling-project/docling/blob/0fa0918d16de7769d942f9b06ca18cb673cbbc2e/docling/models/inference_engines/vlm/base.py#L141)
   accepts a PIL image; `BaseVlmEngine.predict_batch` is an exposed crop interface.
   This supports a plausible minimal crop-only invocation without synthetic PDF
   injection, but it has **not** been imported or executed here. Crop mode is
   oracle localization, never an end-to-end detection score.
3. Stage generation uses `<formula>`, temperature 0, **2048 new tokens**, special
   tokens retained, and repetition stopping. The Transformers path uses
   `do_sample=False`, CPU SDPA and the selected BF16 dtype. Batch size must be
   bounded to one; the unmodified default stage batch size is five. No budget,
   thread or generation setting was increased to force completion.
4. Native formula LaTeX is written to **`TextItem.text`**, after built-in token
   cleanup/repetition-tail stripping. Original PDF character IDs are not supplied
   by this transformation. Capture raw engine text, stop reason/configuration and
   final native item separately; do not call the latter authoritative PDF text.
5. **Critical fallback:** the stage catches engine exceptions and yields existing
   backend text unchanged. A nonempty formula item's text, or even overall
   conversion success, is **not proof formula recognition ran**. Continuation
   must record actual predictor calls and preserve errors/raw output before
   postprocessing. No such failure or fallback was observed here because no
   candidate process was launched.

## Frozen development selection and references

[Selection](selection.json) fixes eight expressions before any inference:

| Document | Page | Targets |
| --- | ---: | --- |
| Attention v7 | 4 | Scaled dot-product attention |
| Attention v7 | 5 | MultiHead and FFN |
| Attention v7 | 6 | Two-line positional encoding |
| Nature TabPFN | 10 | Weighted summation |
| Nature TabPFN | 11 | Softmax |
| User-confirmed LoG final preview | 4 | Equations (2) and (4) |

All three original PDFs and unchanged retained source caches were SHA256/length
checked against PR #22's registry; [input manifest](input-manifest.json) binds
those identities. The eight selections cover six unique source pages. Original
page geometry, IDs, target/content/padded crop boxes and rendering/rounding policy
are recorded. No new authoritative extraction or character correction occurred.

[References](references.json) contains separately curated LaTeX checked against
original PDF review renders and links to existing component references. Positional
encoding was additionally inspected on an original PDFium page-6 render. References
remain **agent_visual_checked**, with **zero independent human verifications**.
TeX spelling/font choices are not uniquely determined by PDF ink; exact string
agreement alone cannot establish mathematical correctness. Detailed PE component
annotations and the formula-specific scorer remain unfinished.

All examples are development-exposed, including the two LoG controls. None is an
independent held-out validation. There is no true stacked nested fraction among
these eight; do not claim that capability from slash divisions or a radical.
No inference-input crop hashes or recognized renderings exist yet. Full-resolution
source review evidence remains outside Git. Tectonic is available on the host,
but was not invoked; offline bundle/cache readiness was not verified and no
predicted LaTeX exists to render. No visual fidelity or syntax-validity score is
invented.

## Results and decision

[Predictions](predictions.json): **0 model initializations, 0 predictor calls**;
end-to-end and verified-crop stages are NOT_EXECUTED.
[Results](results.json) retains all **8/8 selected IDs**, with **0 attempted** and
**8 unexecuted**. Exact/normalized string, syntax, detection, symbol and structural
counts are **null**, with reasons. Unexecuted targets are neither silently dropped
nor counted as model errors/successes. Initialization/inference time, peak memory,
OOM counts, CPU, model storage/transient peak and comparative visuals are likewise
null. Previous Heron measurements are not formula-model measurements.

Consequently all substantive recognition questions—fractions, radical distinction,
CID sums, correct index attachment, entire multi-part equations and consistency
across papers—are **unanswered**. Detection and transcription failures cannot yet
be separated observationally. Do not conclude that Docling is either reliable or
poor, or switch to PP-FormulaNet-S on this evidence.

**A navigable mathematical expression tree is not justified by measured recognition
quality yet.** Generated LaTeX, independently checked syntax, mathematical AST
construction and source-symbol alignment are four different capabilities. The
next justified activity is the **same bounded Docling recognition experiment**
after resources are restored, not Formula Structure v0 or another model now.

## Reproduction, preservation and continuation

[Commands](commands.md) reproduce the arithmetic assessment and offline tests.
The helper reads captured resource/model metadata only; it cannot download,
start the VM, import the model or execute inference, and never reads references.
**568 offline tests passed**, zero failures/skips, including **17 new cases**.
All **462 pre-existing tracked files** remain byte-identical.
Regression tests cover resource accounting, immutable source/model identities,
failure-closed decisions, missing hashes, deterministic results and unexecuted
denominators. Final suite/CI evidence is recorded with publication.

No historical files/reports, production behavior, annotations, models, Docling
runtime, Source Selection, Hybrid, viewer or Contextual Inspector were modified.
The existing broken host launcher was not repaired. No cleanup or alternative
model/inference occurred. Git publication and source/config metadata checks are
not remote document processing; no PDF or private raw inventory was uploaded.

To continue, first restore **at least 20 GiB plus prospective growth headroom**
through a separately authorized user action; no cleanup is authorized here. Then
either validate a genuinely single-copy acquisition/temporary strategy within
6 GiB, or obtain an explicit prospective storage amendment for retained duplicates.
Only after both gates pass should the existing VM be used for candidate execution,
installed identities and guest capacity checked, and the pinned recognition candidate run with the
unchanged 4 GiB/no-swap/four-core/120-second bounds. Complete the isolated worker
and component scorer without feeding references into prediction. No VM restart
is needed merely to fix the initial sandbox status error. The current
conditional model-acquisition/inference authorization was **not exercised**.

**Stop: no production parser/AST integration, no alternate model and no inference.**
