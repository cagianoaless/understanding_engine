# Experiment 006 preflight: NO-GO

Baseline: `ba82b2c7f71604d5bcc2859b1a05de112723107d`, as required by
[issue #6](https://github.com/cagianoaless/understanding_engine/issues/6).
The complete issue, PR #5 and Experiment 004/005 reports were read before this
audit. PR #5 is unmerged; this work is isolated on `feat/experiment-006-docling`,
to be proposed against its feature branch. No original file is changed.

**Decision: NO-GO on this host under the specified controls.** The exact 4 GiB
RSS/address-space limit probes fail, and no alternative aggregate process-tree
limiter has been validated. Installed/cache footprint and several effective
runtime controls are also unverified. Issue #6 requires stopping when these
gates cannot be passed. Nothing is installed and no weight file or prediction
is acquired/generated. This is not evidence that Docling necessarily exceeds
the limits or has inferior layout quality.

## Exact candidate and host

- Proposed release: `docling==2.148.0`, delegating to
  `docling-slim[standard]==2.148.0`. Both declare Python >=3.10,<4 and MIT in
  [version-specific metadata](https://pypi.org/pypi/docling/2.148.0/json),
  [slim metadata](https://pypi.org/pypi/docling-slim/2.148.0/json).
  **No release is runtime-tested**; the proposal is not relabelled as tested.
- Host: macOS 26.5.1 arm64, Mac14,2, CPython 3.11.13, eight logical CPUs,
  **17,179,869,184 bytes RAM (16 GiB)**. Free disk at the successful host probe:
  **12,816,334,848 bytes**. These capacity readings do not prove resource enforcement.
- In-sandbox RAM/process reads were denied. Read-only escalation successfully
  measured RAM and process RSS. The cap-setting failures below occurred even
  in an escalated child; they are not inferred solely from sandbox denial.
- Baseline project environment has no Docling, torch or transformers. No
  isolated candidate environment is created. See [hardware.json](hardware.json)
  and [environment.json](environment.json).

## Dependency closure and costs

`uv 0.7.13` resolved the native host, Python 3.11.13 and proposed pin at an upload
cutoff of `2026-11-06T00:00:00Z`, with source builds forbidden. **103 exact
dependencies** have native-compatible selected wheels, recorded sizes, URLs,
SHA-256 and license declarations in [dependencies.json](dependencies.json).
[requirements.candidate.lock](requirements.candidate.lock) contains one selected
host-wheel hash per pin; it is not a tested environment or the production lock.
The complete original multi-platform hash output is preserved outside Git.

| Metadata-known payload | Bytes |
| --- | ---: |
| Selected dependency wheels | 329,063,669 |
| Three minimal Heron inference files | 171,662,708 |
| Combined expected artifact payload | **500,726,377** |
| Hard new-download cap | 2,147,483,648 |
| Projected installed/cache footprint | **unknown** |
| Candidate runtime RSS/time | **not_run** |

The known payload is below 2 GiB. This is **not** actual binary acquisition,
complete network traffic, uncompressed installed size, or peak cache usage.
Preflight acquired metadata/source/configuration text only. The resolver's local
index/METADATA cache occupies 48,194,015 logical bytes; that is neither a wheel
download counter nor an installed-footprint estimate. Raw metadata response sizes
are recorded separately. No wheel size is used to approve the 4 GiB disk cap.

Two diagnostic command problems are preserved rather than called incompatibility:

1. `--only-binary` and `--no-build` together are rejected by this uv release.
   The corrected command uses `--only-binary :all:` alone, retaining no-build policy.
2. An explicit `aarch64-apple-darwin` cross-target resolution rejected macOS 14
   wheels. Those wheels **are compatible with this macOS 26 host** under native
   `packaging.tags.sys_tags()`. Native resolution succeeds, selecting
   `docling-parse==7.24.2` and its CPython 3.11/macOS 14 arm64 wheel. The initial
   resolver error is not a genuine host incompatibility. Logs and exact commands
   remain in [commands.json](commands.json) and [logs](logs).

## Version-specific API and minimal model

The release tag resolves to source commit
[`0fa0918`](https://github.com/docling-project/docling/tree/0fa0918d16de7769d942f9b06ca18cb673cbbc2e).
Ten reviewed source files were checked against their exact Git blob identities;
[api-audit.json](api-audit.json) records pinned URLs, hashes and review scope.
The live [pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
and [advanced options](https://docling-project.github.io/docling/usage/advanced_options/)
were consulted, but the release source takes precedence over unversioned docs.

The default modern path is `LayoutObjectDetectionOptions`, preset
`layout_heron_default`, with the **Transformers** object-detection engine.
Deprecated `LayoutOptions` is a compatibility shim. No ONNX, Egret, VLM or other
backend/model is substituted. Source exposes explicit CPU selection, thread
configuration, local `artifacts_path` and `page_range`; a derivative PDF is not
currently required or created.

The inspected flags allow disabling OCR, table structure, code/formula enrichment,
picture classification/description, chart enrichment, remote services and external
plugins. CPU/device options and `compile_model=False` exist. These findings are
**static API evidence**, not proof that runtime isolation/thread/time controls work.
No guessed option set is claimed to have run.

Standard model: `docling-project/docling-layout-heron`, pinned from `main` to
**`8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`** for inventory:

| Required file | Bytes | Digest status |
| --- | ---: | --- |
| `config.json` | 3,268 | Metadata content SHA-256 and Git blob verified |
| `preprocessor_config.json` | 444 | Metadata content SHA-256 and Git blob verified |
| `model.safetensors` | 171,658,996 | Expected LFS SHA-256 available; **not downloaded/content-verified** |

The weight's expected SHA-256 is
`00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c`.
Pinned URLs and individual identities are in [model-inventory.json](model-inventory.json).
The configuration identifies RT-DETRv2/ResNet, no pretrained-backbone fetch and
640×640 preprocessing; no tokenizer file is required by this inspected vision
path. README/configuration metadata was read; the weight, logo and generic
all-model download command were not fetched/run. These are minimum runtime
files, not a claim that all bundled contents of 103 wheels were audited.

Licenses are recorded separately: Docling/slim MIT declarations, and each model
entry refers to the [pinned model card's Apache-2.0 declaration](https://huggingface.co/docling-project/docling-layout-heron/blob/8f39ad3c0b4c58e9c2d2c84a38465abf757272d8/README.md). All 103 packages
have declarations, including compound/bundled notices (notably torch/PDFium).
Full artifact compatibility clearance stopped at the resource blocker. **No
license incompatibility is asserted**, and repository declarations are not
presented as a complete per-file legal clearance. The original license text and
package metadata are retained externally with hashes.

## Resource-control failure

The exact probe calls `setrlimit` in a short child, without allocating a large
buffer or importing a model:

```text
requested cap:        4294967296 bytes
RLIMIT_RSS:          5
RLIMIT_AS:           5
RLIMIT_RSS_error:    ValueError('current limit exceeds maximum limit')
RLIMIT_AS_error:     ValueError('current limit exceeds maximum limit')
```

Both identifiers alias the same mechanism on this host, so address-space limiting
is not an independently validated fallback. The collector exits 0 because it
successfully records the exceptions; that is **not** a passed enforcement test.
Its approximately 19 MB RSS is the probe's RSS, not Docling's. An earlier 16 MiB
probe also failed before its planned allocation, so no 64 MiB buffer was allocated.
[rss-limit-probe.json](rss-limit-probe.json) preserves the source and raw result.

This proves failure of the tested method, **not impossibility of every macOS
control strategy**. No alternative whole-tree hard guard was implemented or
validated. Process sampling/kill-after-threshold alone is not asserted to prove
an aggregate peak never exceeded 4 GiB. CPU pools, wall timeout, offline/telemetry
and plugin isolation likewise remain execution-unverified. Under the issue's
strict all-gates rule, these unknowns prohibit acquisition/inference.

## Reproduction and actionable next steps

Offline replay (expected exit **3**, meaning a recorded NO-GO):

```sh
uv run --frozen --offline python evaluation/experiments/006/preflight.py
```

Recheck host capability, without model imports or allocation tests:

```sh
uv run --frozen --offline python evaluation/experiments/006/probe_host.py
```

Restricted reads are recorded as errors; elevated read access was needed in the
managed session. Even a successful setter alone would not prove whole-tree RSS
enforcement. Recheck frozen wheel metadata separately, without installation:

```sh
uv run --frozen --offline python evaluation/experiments/006/audit_metadata.py \
  --output-dir /tmp/experiment-006-metadata-new
```

That audit script deliberately uses network metadata; `uv --offline` prevents
dependency synchronization downloads, not Python's HTTP requests. The script
never fetches wheels/weights or converts PDFs. Historical response hashes and
all exact native resolver flags are preserved; changed live metadata creates a
new audit rather than rewriting this one.

To revisit the same candidate, first provide/validate a whole-process-tree RSS
guard and bounded installed/cache accounting, including native allocations,
children and failures. Complete artifact/notice clearance and verify CPU-only,
four-thread, offline and 120-second controls before acquisition. A separately
approved host with suitable controls could be audited under the **same caps**;
no host, model, backend, version or paper switch occurs in this experiment.
Do not raise caps or call this a quality failure. Preserve Structure 0.2 unchanged.
