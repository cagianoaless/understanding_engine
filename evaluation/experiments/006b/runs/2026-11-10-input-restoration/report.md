# Experiment 006b — original PDF input restoration, 2026-11-10

**PDF INPUTS READY:** all three original files match their registered byte lengths and SHA-256 values, and all six frozen page numbers exist. No inference, prediction scoring, text extraction, runtime preflight, installation or model acquisition was performed. No benchmark was run.

Parent PR #15: `9b0e329d294434dcbfe5699953aebd8f696703ea`. New branch: `feat/experiment-006b-restore-inputs`. The authoritative `evaluation/experiments/006b/source-inputs.json` remains byte-identical, SHA-256 **4609502f6dcfae904f90be522d9a0ee1682b45eb7e515ac32ea9f3bc899a9469**. Paths are supplied as a separate overlay; scientific identities, revisions, settings and page selection were not changed.

| Registered original | Exact bytes | Verified SHA-256 | Original pages | Frozen pages verified |
| --- | ---: | --- | ---: | --- |
| Attention v7 | 2,215,244 | `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697` | **15** | **6, 9** |
| BERT v2 | 775,166 | `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e` | **16** | **6, 10** |
| Nature TabPFN | 16,957,699 | `6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013` | **23** | **15, 19** |

## Discovery, retrieval and acceptance

Attention remained available at its registered path. BERT/Nature were absent from their registered paths; bounded searches of known experiment artifact roots and the workspace found no matching originals. The already unavailable source-extraction caches were inspected for existence only, not regenerated or overwritten.

Attention was independently checked and copied byte-for-byte. BERT was retrieved from exactly **https://arxiv.org/pdf/1810.04805v2**, never a versionless/latest URL. Nature was retrieved from exactly **https://www.nature.com/articles/s41586-024-08328-6.pdf**. Original URLs, observed final publisher paths, HTTP status, bytes and hashes are in [retrieval-provenance.json](retrieval-provenance.json).

Two portable-client Nature responses were HTTP 200 **text/html**, advertising **3,038 bytes**; both were rejected before acceptance. A bounded native-client inspection read/discarded a 65,537-byte prefix, exceeding its diagnostic limit; a subsequent HEAD advertised the exact PDF. The existing macOS standard-library client then followed ordinary anonymous HTTPS redirects through `idp.nature.com` back to the same Nature PDF path and received **application/pdf, 16,957,699 bytes**, with the exact frozen hash. This is a client-delivery observation, not a proven diagnosis of its cause. No credentials/cookie store, alternate paper, publisher rendering, cached third-party PDF, re-export or byte correction was used. Opaque publisher query values remain only in local evidence; committed provenance retains query names and exact URL hashes.

The native transfer remained a `.native.part` until an independent CPython 3.11.13 verification re-read it, checked length/SHA-256 and validated its page tree using existing **pypdf 6.1.1**. Only then was it atomically renamed to the original filename. All three final files were independently reverified again. Wrong bytes/hashes and out-of-range pages fail closed; the ordinary publisher-resume path explicitly rejects a PDF hash mismatch as a resumable HTML-delivery case.

Accepted new PDF HTTP payload: **17,732,865 bytes** (BERT + Nature). The diagnostic prefix adds **65,537 application-read bytes**; total wire traffic, TLS/headers and any rejected-response prefetch were not measured. Local copied Attention bytes are not reported as a network download.

## Final verified locations

All three originals are together in a **private mode-0700 persistent directory under `/Users/Shared`**, outside every Git repository. `$INPUT_ROOT` below denotes that exact directory; its physical location and authoritative original-path-to-final-path mapping are retained in the external **`input-remapping.complete.local.json`**. No PDF or machine-specific path is committed.

```text
$INPUT_ROOT/documents/1706.03762v7.pdf
$INPUT_ROOT/documents/1810.04805v2.pdf
$INPUT_ROOT/documents/s41586-024-08328-6.pdf
$INPUT_ROOT/input-remapping.complete.local.json
```

[inputs.json](inputs.json) records each verified identity, length, page count and final relative location. [path-remapping.json](path-remapping.json) is the portable location overlay, bound to the unchanged registry hash. Original Attention remains in place; the absent registered BERT/Nature temporary paths were not recreated. Future callers must explicitly load the external overlay instead of editing the frozen registry or silently substituting paths.

The initial incomplete mapping/rejected responses and successful native-transfer/acceptance records are preserved. The canonical complete local mapping was published after independent final verification; earlier attempt records were not overwritten. Full exact local paths and raw publisher redirect URLs stay outside Git, with hashes in [external-evidence-manifest.json](external-evidence-manifest.json).

## Verification, preservation and readiness

Targeted offline tests: **14 passed**, zero failures/skips, **0.14 s**, covering exact identities, wrong same-length bytes, lengths, symlinks, page bounds, immutable selection, arXiv revision restrictions, publisher origins, HTML-resume restrictions and incomplete mappings. Offline live-input verification reports **3 documents / 6 selected page pairs / zero inference**. Only page dictionaries/counts were read; no extraction outputs or annotations were generated. [commands.md](commands.md) supplies reproduction and offline verification commands.

All **323 pre-existing tracked files** remain SHA-256 identical, including prior reports, frozen references, development/held-out manifests, baseline code/settings and source identities. Colima, Docling, installed packages, Heron and all resource policies were left untouched. The existing host launcher remains unrepaired; verification/tests use the already-installed intact 3.11.13 and unchanged project packages read-only. No dependency resolution or installation was needed.

The new input directory allocated **20,844,544 bytes** at the verification snapshot, including PDFs and local manifests; the three PDFs contain **19,948,109 bytes**. Registered-root inclusive allocation was **4,848,283,648 bytes**, under the unchanged **6 GiB** cap; available host space was **30,271,504,384 bytes**, above 20 GiB. These are allocated-block observations, not APFS-exclusive allocations or a claim of continuous peak coverage. Existing roots plus the new input/evidence locations were counted; no runtime/API preflight, cleanup or resizing occurred. Include `$INPUT_ROOT` in subsequent accounting.

**PDF input readiness is restored.** Registered extraction-cache paths were already unavailable and remain so; this PDF-only task neither recreated nor altered them. Any required baseline regeneration belongs to a separately authorized comparison plan. The six-page benchmark, inference, scoring and annotation changes remain unexecuted. Stop here.
