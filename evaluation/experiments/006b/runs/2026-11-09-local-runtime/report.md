# Experiment 006b — local runtime validation, 2026-11-09

**Colima + Docker CLI installed; the dedicated ARM64 VM and corrected model-free probe passed. Candidate installation and scientific evaluation remain unexecuted.** This new run follows issue #10, stacked on unmerged PR #9 at `1b4c17cab993be0a7aecfeb1793863bf5ee4f56c`. The historical NO-GO records remain unchanged: missing Linux infrastructure was not evidence of excessive Docling memory or poor quality.

## Observed results

| Gate | Result | Evidence / limit |
|---|---|---|
| Native host / ordinary-user installation | PASS | macOS 26.5.1 ARM64; 16 GiB RAM; 8 CPUs; hypervisor available; no DEP/MDM enrollment; existing user-writable Homebrew |
| Tooling installation | PASS | Colima 0.10.3, Docker CLI 29.9.3, Lima 2.3.0; only three prebuilt bottles; no optional plugins, services, Docker Desktop or host sudo |
| Host free-space reserve | PASS | Final snapshot 34,874,974,208 bytes = 32.480 GiB; reserve 20 GiB |
| Native VM | PASS | `ue006b`, Apple Virtualization.Framework, aarch64, 4 vCPUs, 5 GiB RAM, Ubuntu 24.04.4, kernel 6.8.0-117, Docker Engine 29.5.2, cgroup v2 |
| Memory control and child accounting | PASS, bounded probe | `memory.max=134217728`; child allocation raised `memory.current` from 1,560,576 to 20,164,608 bytes; cgroup peak 20,656,128; OOM counters zero |
| Container and VM swap | PASS | `memory.swap.max=0`, `memory.swap.current=0`; Docker memory and memory-swap both 128 MiB; `/proc/swaps` has no entries |
| CPU quota | PASS | `cpu.max=100000 100000` = 1 core, within four-core ceiling and four-vCPU VM; four short workers caused 20 throttled periods and 2,054,023 additional usage microseconds |
| External timeout and cleanup | PASS | Host two-second deadline; sleeping container killed and observed exited 137, PID 0, Running=false, OOMKilled=false; elapsed 2.096 seconds including cleanup; both disposable containers removed |
| Offline container network | PASS | Docker network `none`, loopback only, no IPv4 routes; direct connection failed with exit 1; no published ports |
| Filesystem/security isolation | PASS | VM `mounts: null`; no host filesystem mounts; container Mounts=[], read-only root, UID/GID 65534, all capabilities dropped, NoNewPrivs=1, Seccomp=2; no Docker socket or GPU devices |
| Current inclusive download budget | PASS with stated accounting | Artifact payloads 397,781,165 bytes; 128 MiB conservative metadata/duplicate-small-transfer allowance gives 531,998,893 bytes, below 2 GiB |
| Current inclusive installed/cache budget | PASS at measured snapshots | 1,783,357,440 allocated bytes + 16 MiB metadata allowance = 1,800,134,656 bytes, below 4 GiB |
| Provisioning-time storage peak | UNKNOWN | Initial monitor used an unhonored Colima state-directory override and omitted the actual VM files. Corrected final and probe-time measurements are separately preserved; they cannot establish the historical setup peak. |
| Linux candidate wheels, full licenses and inclusive fit | UNKNOWN | Linux cp311 resolution/install deliberately not performed; macOS dependency inventory is not reused |
| Effective inference threads / candidate RAM / 120s page behavior | NOT RUN / UNKNOWN | No native inference pools or model were launched; environment thread settings alone are not proof |

These PASS results establish the observed kernel controls and small probe behavior. Memory was not driven to its limit and no OOM was induced. The four-GiB candidate and 120-second page run were not tested. A synthetic test or this one tiny image establishes neither Docling memory demand nor scientific extraction quality.

## Disk and download accounting

Before tooling installation, `df` reported 36,567,797,760 free bytes; afterward 36,354,424,832. The three installed kegs occupy 153,333,760 allocated bytes, and their dedicated Homebrew cache initially occupied 106,237,952. All runtime/cache/setup costs are included below, not silently removed from the experiment caps.

| Payload | Acquired bytes |
|---|---:|
| Homebrew bottles, verified SHA-256 | 64,517,518 |
| Colima-core v0.10.4 native Docker image, verified SHA-256 and SHA-512 | 332,354,401 |
| BusyBox compressed layer | 899,736 |
| BusyBox manifest/index/config payload accounting | 9,510 |
| Artifact payload total | 397,781,165 |

These are payload bytes identified by files/manifests, not a packet-level network counter. Metadata requests, API material and repeat small manifest/config transfers are conservatively reserved at 128 MiB; that allowance is an estimate, not measured wire traffic. Documentation traffic is not a candidate artifact. Model/dependency acquisition is zero.

The root and data disks are explicitly **4 GiB and 5 GiB virtual capacity**. At corrected inspection, the root file occupied 1,155,653,632 allocated bytes and the data file 4,128,768; other VM state was also counted. Final VM/cache components are in `accounting.json`. Nine GiB of nominal disk capacity is not nine GiB of current physical host use. Guest layer storage is already inside those VM files and is not added twice. APFS clones/exclusive extents were not established; allocation sums are conservative reported totals, not a measured reduction in exclusive host capacity.

The installed/cache accounting includes all newly created Colima state, the VM image cache, Homebrew bottles/API cache, all three installed kegs, experiment evidence and scoped Homebrew logs. A 16 MiB metadata allowance covers additional small setup/link/evidence overhead. The corrected model-free run sampled a storage maximum of 1,783,218,176 allocated bytes. Initial provisioning peak remains UNKNOWN. The 5 GiB VM data disk is not a hard four-GiB experiment filesystem quota; future candidate writes need bounded accounting/guards.

The model-free setup fits the current byte ceilings and host reserve. Full Linux Docling/Heron installation fit is still unknown; remaining headroom must include all future wheels, installed files, temporary extraction, model files, layers and caches. No budget was enlarged.

## Failures and corrections retained

1. Sandbox RAM queries and the first unscoped Colima version check were denied. Scoped permission requests then measured the host and performed ordinary-user installation; no macOS ownership/security setting changed.
2. Homebrew's original cached inventory was stale (Docker 29.8.1, Lima 2.2.0). The dry-run refreshed it; versions, sizes, licenses and bottle hashes were rechecked for Docker 29.9.3/Lima 2.3.0 before installing. Auto-update, upgrades, analytics and unrelated cleanup were disabled.
3. The requested `COLIMA_HOME` override did not determine the observed state location; Colima used its standard state root. The first VM-accounting snapshot therefore omitted VM allocation and is not accepted as complete accounting. `runtime-accounting-corrected.json` in the external evidence and committed `accounting.json` count the actual state. The first positional SSH invocation selected no running default VM; the corrected `colima -p ue006b ssh -- ...` inspection succeeded.
4. Probe attempt 01 recorded successful memory/CPU observations but returned failure: its network test expected diagnostic text that BusyBox did not emit, and its cleanup verifier expected capitalized Docker error text. The object had actually been removed. Attempt 01 and its source hash are preserved. The corrected parser requires kernel network isolation evidence plus connection exit status and checks object absence without relying on capitalization. New offline regressions cover these cases. Attempt 02 used the same digest and resource/security limits, passed, and measured timeout cleanup. No candidate code, baseline or frozen reference was changed.

## Provenance, validation and readiness

`probe-attempt-01.json`, `probe-attempt-02.json`, `image-lock.json`, `bottles.json`, `host.json`, `tooling.json`, `accounting.json` and `external-evidence-manifest.json` retain commands, exit codes, measurements and digests. Machine-specific raw collectors, private locators, VM data and downloads remain outside Git; committed path tokens are `$HOME`, `$REPO` and `$EXTERNAL_RUN`. `commands.md` gives replay requirements. Raw setup logs are retained, including unsuccessful checks; no old experiment was rewritten.

The unchanged default Docker context remained `default`; Colima auto-activation was disabled and the dedicated context lived in a separate Docker configuration directory. No existing VM was present or deleted. The dedicated VM remains operational for later authorized work; its two disposable test containers are gone.

**278 offline tests passed**, zero failures/skips, Python 3.11.13 / pytest 8.4.2, reported test duration 7.65 seconds. The existing environment was used without research dependency reinstall. All **200 original tracked files** are SHA-256 identical (`preservation.json`), including production extraction, Structure 0.2, dependencies, existing experiments and frozen references. No workflow was changed or cloud benchmark dispatched. The existing ordinary PR CI remains separate from runtime evidence.

Structure remains pinned to `ba82b2c7f71604d5bcc2859b1a05de112723107d`, Docling to 2.148.0 and Heron to `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`. Six development pages/48 reference regions remain agent_visual_checked; human-verified count is zero. No PDF was processed or substituted; model predictions, source grounding and comparative metrics are null/not_run.

**Readiness:** the local runtime mechanism is available for a subsequently authorized controlled stage. A one-page Docling smoke test is **not yet fully cleared**: it still needs Linux ARM64 cp311 wheel/license and inclusive-fit checks, fresh resource checks, correctly scoped continuous accounting and separate authorization. Historical setup-peak uncertainty must remain visible. No neural model, full candidate stack or six-page benchmark was run. Stop here.

Official references consulted: [Colima installation](https://colima.run/docs/installation/), [configuration](https://colima.run/docs/configuration/), [runtimes](https://colima.run/docs/runtimes/), [versioned image pins](https://github.com/abiosoft/colima/blob/v0.10.3/embedded/images/images.txt), and [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).
