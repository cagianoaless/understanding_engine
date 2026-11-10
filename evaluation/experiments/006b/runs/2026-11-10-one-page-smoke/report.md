# Experiment 006b — first controlled Docling page, 2026-11-10

**SMOKE PASS.** Docling 2.148.0 processed the original Attention PDF's **page 6**, with **one nonempty Heron prediction batch**, no OCR and no inference network. Exit status **0**; no conversion errors or OOM events. The six-page comparison was **not run**. This result establishes execution of this one configuration/page, not accuracy or generalization.

Parent: PR #14, `4104548e2779d8c44d9e000f2d364dc22271ecc8`; branch `feat/experiment-006b-one-page-smoke`. The [prospective amendment](../../../../../docs/protocol-amendments/2026-11-10-storage-and-single-page.md) activates **6,442,450,944 bytes inclusive storage** for this run. Prior 4 GiB/download-ceiling/NO-GO records remain unchanged. Structure stays at `ba82b2c7f71604d5bcc2859b1a05de112723107d`; the 103 wheel versions/hashes, Heron revision and frozen annotations are unchanged.

## A. Licensing and actual runtime

Targeted publisher verification closed the three *local-use notice evidence gaps*: [Docling v2.148.0 at 0fa0918](https://github.com/docling-project/docling/blob/0fa0918d16de7769d942f9b06ca18cb673cbbc2e/LICENSE) and [latex2mathml 3.81.1 at fb724a9](https://github.com/roniemartinez/latex2mathml/blob/fb724a91658cf41d2fad0192da0845b05446f208/LICENSE) supply MIT texts; [tokenizers v0.23.3 at 3012770](https://github.com/huggingface/tokenizers/blob/301277072263fb3830eb66eec7e47adadf76f1dc/LICENSE) supplies Apache-2.0. Its Python binding manifest identifies 0.23.3 while the underlying Rust crate remains 0.23.2 in this Python-only release. The actual latex2mathml tag has no `v` prefix; the failed `v3.81.1` lookup was not a version substitution. Source URLs, lengths and hashes are in [license-sources.json](license-sources.json).

The PR #14 bundled GEOS/FFmpeg/autocommand LGPL terms, generated-code MPL terms and GCC Runtime Library Exception remain applicable. Their running-scope permissions and unchanged private local use do not identify a material blocker here. Keep notices and separately assess modification/redistribution/service obligations before sharing third-party binaries. No modern SPDX field was demanded and no keyword match was treated as legal clearance. This is an **agent-checked local-use assessment**, not exhaustive legal or redistribution approval; see [licensing.json](licensing.json).

The [official Python image](https://hub.docker.com/_/python) was pinned through registry index, ARM64 manifest and config hashes:

`python@sha256:18ce9b03d18802119f4f9270d10a1ceb45d0acb768c305b7fbbd7c6b5b5a020b`

Observed runtime: **CPython 3.11.13 / Linux aarch64 / glibc 2.36**. All **103** original wheel tags intersect this actual runtime's supported tags. The four manifest-listed compressed layers total **47,597,645 bytes**, and all reported download completion; engine-verified rootfs diff IDs match the pinned config. Protocol/network packet overhead was not measured. [image-lock.json](image-lock.json) preserves provenance, digests, layer sizes and metadata request hashes.

Observed runtime-setup allocation growth before wheel copying was **234,725,376 bytes**, including stored compressed content, unpacked runtime layers and small new container/volume/VM metadata. Docker's API reported `Size=47,604,811`; **that is not physical or unpacked allocation**. The original raw stdout misnamed this API value as unpacked bytes; that source/log is preserved, the current label is corrected, and all budget decisions use measured allocated blocks instead.

## B. Installation and compatibility

All 103 retained CPU wheels were rehashed on the host, checked again by offline pip `--require-hashes`, and verified inside the guest. Installation used `--no-index --no-deps --only-binary=:all: --no-cache-dir --no-compile --target /ue/candidate`, with the frozen hash lock and only the supplied local wheels. **Zero candidate package HTTP downloads**, unexpected packages or CUDA dependencies. All 103 installed target versions and pip report hashes match; [installed-packages.json](installed-packages.json) records each version/file/hash.

Actual candidate allocation: **1,319,063,552 bytes**; logical files: **1,250,810,900 bytes**; generated `.pyc` files: **0**. Imports of Torch, Torchvision, Transformers, OpenCV, PDFium, Docling Parse, document converter and pipeline options **passed**. Torch reports **2.15.0+cpu**, Torchvision **0.29.2+cpu**, and Torch CUDA version is null. The complete one-page conversion subsequently exercised the model/backend code path; this does not test every optional native capability.

A fresh owned Docker volume stores the candidate, guest wheels, model, input copy, caches and outputs. The original host archives remain intact. Containers use UID/GID 65534, dropped capabilities, no-new-privileges, read-only root, network `none`, no host bind mounts, no Docker socket or GPU. A short root-in-container initializer only set permissions on this newly created volume; no host privilege or permission change occurred. Existing Colima configuration, disks and Docker contexts were preserved.

## C. Pinned model and single-page evidence

Only `model.safetensors` (**171,658,996 bytes**) required a new model HTTP acquisition. The two previously verified small configs were copied from the retained metadata cache. All three minimal files (**171,662,708 bytes total**) match the frozen SHA-256 values on host and guest at revision **8f39ad3c0b4c58e9c2d2c84a38465abf757272d8**; see [model.json](model.json). No other model request occurred. The already-installed RapidOCR wheel's bundled assets were not executed.

Selection was frozen before prediction: first document/first page in the existing 006b development selection, **Attention page 6**, original PDF SHA-256 `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`. No derivative PDF or changed preprocessing. Docling used its pinned backend/Heron preprocessing defaults, CPU, four Torch threads, one interop thread, compile disabled, and the existing frozen disabled-feature settings. OCR, table reconstruction, formula/code/picture/chart enrichment, external plugins and remote services were disabled. The predictor wrapper only rejects a wrong/multiple page or second nonempty prediction batch and otherwise delegates unchanged.

| Actual measurement | Result |
| --- | ---: |
| Container exit / status | **0 / success** |
| Nonempty model prediction batches | **1**, page **6**, input image **612 × 792** |
| `convert()` wall time, including lazy pipeline/model initialization | **4.578672 s** |
| Page-process total, including imports and output export | **8.988007 s** |
| Externally observed job wall time | **10.244980 s** |
| Kernel cgroup `memory.peak` | **629,465,088 B (600.30 MiB)** |
| Actual `memory.max` / `memory.swap.max` | **4,294,967,296 / 0** |
| Actual `cpu.max` | **400000 100000**, four CPUs; affinity 0–3 |
| Delta cgroup CPU time | **12.047816 CPU s**, about **134.04%** of one core averaged over process wall time |
| Memory limit / OOM / OOM-kill events | **0 / 0 / 0** |
| CPU throttling events | **0** |

The independent host **120-second watchdog was armed**, did not fire, and has an owned-container-only kill path. This successful short run does not empirically exercise the 120-second expiry path. The inference process also checked actual cgroup values before neural imports. [execution.json](execution.json) retains before/after kernel counters, isolation configuration, timing scopes and native output counts. Stderr contained normal weight-loading progress (770/770 tensors), with no candidate warning/error observed. The process/cgroup was fresh; VM/image/filesystem caches were already populated by installation and hash verification, so these figures are not cold-start or worst-case bounds.

## Inspectable native output and limitations

[page-structure.json](page-structure.json) preserves **all 32 native items in traversal order**, their labels/text, hierarchy levels, provenance boxes, Docling body references and **14 postprocessed layout clusters**. Observed labels: **27 text**, **2 section headers**, **1 caption**, **1 table region**, **1 formula region**. These are predictions, not verified classifications.

For example, the native output contains:

1. Table region and its caption/flattened text children.
2. Heading **“3.5 Positional Encoding”**, following text and a formula-labelled region.
3. Heading **“4 Why Self-Attention”**, followed by text beginning **“In this section we compare various aspects of self-attention layers…”**.

Table structure was disabled; the table label/flattened children are **not a reconstructed grid**. The formula label is **not formula recognition or LaTeX recovery**. Text is copied from native Docling output without subsequent correction, normalization or evaluation-driven tuning. The full native document JSON, Markdown, cells/layout and kernel samples stay outside Git with hashes in [external-evidence-manifest.json](external-evidence-manifest.json).

Docling reports page size **612 × 792**. Exported item-provenance boxes use **BOTTOMLEFT** origin; layout-cluster boxes use **TOPLEFT**. Both are retained explicitly. No tested crop/rotation transformation or character-ID crosswalk to Structure 0.2 is asserted. Docling `charspan` offsets index its own item text, **not authoritative PDF characters**. No precision/recall, reading-order correctness or accuracy advantage is claimed. The annotations remain `agent_visual_checked`, with **zero independent human verifications**. The selected development page is now exposed; no parameters were tuned, and it must not later be described as fresh independent validation.

## Storage, interruptions and preservation

Highest **observed** inclusive allocation / retained snapshot: **4,826,791,936 bytes (4.50 GiB)**, below the active **6 GiB** cap. The snapshot retains all old setup/cache/evidence roots plus images/layers, original host archives, guest wheel copies, installed candidate, both model copies, caches, input and outputs. No old resource was cleaned, deleted or resized. Final host availability in that snapshot: **30,317,051,904 bytes (28.23 GiB)**, above the 20 GiB reserve. Background host writes affect df independently of the experiment; free-space deltas are not equated with artifact sizes.

Guest final capacity: root **2,123,157,504 bytes available**, Docker data filesystem **2,795,560,960 bytes available**. Existing nominal root/data disks were not resized. Maximum observed new installation temporary directory allocation: **1,319,059,456 bytes**, sampled approximately every two seconds. Pip staged the whole target then moved it on the same volume; temporary and final target maxima must **not** be added as simultaneous copies. This is a sampled temporary peak, not a filesystem high-water counter. Observed host-block peaks likewise do not prove every sub-sample transient or APFS-exclusive allocation. Preventive admission, a 128 MiB margin and continuous checks bounded each producer; all authorized 6 GiB/20 GiB observations passed. Historical provisioning peak remains UNKNOWN.

Two controller interruptions are preserved in [setup-interruptions.json](setup-interruptions.json): a log-name collision before pip, and an overly small **64 MiB internal import-step estimate** reacting to deferred installation/VM writeback. The latter killed verification with exit 137, **OOMKilled=false**, at **4,458,328,064 bytes**, below the authorized cap. After guest sync, import verification alone was rerun with a 512 MiB reservation inside the unchanged 6 GiB cap. **One pip install, no package/version repair, and one PDF prediction batch** occurred. These are controller issues, not Docling extraction failures or evidence of exceeding model memory.

All **281 pre-existing tracked files** remain SHA-256 identical. Original Attention PDF hash and Colima configuration hash remain unchanged; Docker context is still `default`. Host Conda/project `.venv`/system Python were not modified. The project's old temporary interpreter lacks stdlib sources; tests used an already-installed intact **3.11.13** with the unchanged project's site-packages read-only. All 22 installed project distributions checked against uv.lock had no version mismatch. Because `uv --no-project` was used to avoid touching the broken launcher, its `--frozen` flag has no effect in that mode; there was no resolution, sync or dependency installation. Full offline suite: **343 passed**, zero failures/skips, **8.11 s**, including **19 new control regressions**. Existing GitHub CI separately uses the normal locked Python 3.11.13 workflow.

## Readiness and stop

**Runtime, installed candidate, pinned model and one-page execution are ready for a separately authorized comparison. Input readiness is not complete:** the registered temporary BERT and Nature PDF paths are currently absent; bounded workspace/Spotlight filename searches found no alternatives. No replacement was downloaded or substituted. Locate/restore the originals matching SHA-256 **5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e** (BERT) and **6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013** (Nature), then obtain separate six-page authorization. Their frozen manifests/annotations remain unchanged; global absence or a deletion cause is not inferred.

The six-page benchmark, comparative scoring, tuning and host-launcher repair are unexecuted. All owned containers are stopped; the image, volume, wheels, model and evidence are retained. **Stop here.**
