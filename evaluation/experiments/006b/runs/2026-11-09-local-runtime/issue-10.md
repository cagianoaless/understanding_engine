# Experiment 006b — Local, no-paid-services Docker-compatible container preflight

## Change of direction (user preference, 2026-11-08)
**Supersedes the earlier GitHub Actions workflow plan in this issue.** The user does **not** want to rely on potentially billed cloud runner minutes and explicitly agrees to installing local Docker-related tooling if needed. **Do not implement, merge, or dispatch the formerly proposed GitHub Actions probe.**

Prefer **Colima + Docker CLI** on the user's Apple Silicon Mac: free, open-source, no Docker Desktop subscription, local Linux VM with Docker-compatible engine. Docker Desktop is an optional fallback **only after its personal/educational/institutional license is checked and the user selects it**. Do not assume institutional research usage automatically qualifies for Docker Personal.

Official references:
- https://colima.run/docs/installation/
- https://colima.run/docs/configuration/
- https://colima.run/docs/runtimes/
- https://docs.docker.com/engine/containers/resource_constraints/
- https://www.docker.com/legal/docker-subscription-service-agreement/

## Project context and frozen baseline
Resume [issue #8](https://github.com/cagianoaless/understanding_engine/issues/8) / [PR #9](https://github.com/cagianoaless/understanding_engine/pull/9), where Stage A references are frozen on six pages (Attention 6/9, BERT 6/10, Nature 15/19), 48 regions, 24 order pairs, 18 paragraph decisions. All are **agent_visual_checked**, zero independently human-verified.

Keep Structure 0.2 baseline at `ba82b2c7f71604d5bcc2859b1a05de112723107d`, candidate Docling `2.148.0` and pinned Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, original PDF hashes, and all established Experiment 006b scoring/stop rules. Do not modify or re-label existing 006/006b NO-GO results. New dated run/audit under a separate directory/revision, with immutable evidence and a dedicated feature branch stacked on PR #9; no merge. No changes to default `main`.

## Phase 1 — Native Mac preflight, before installation
- Verify `uname -m`, OS version, actual free disk/RAM, Homebrew availability, current container/tool installations and paths, and whether the machine is managed or installation is restricted. Prior evidence ~11 GB free is **stale**; remeasure.
- Check the predicted Homebrew installation footprint (Colima, Lima, Docker CLI and dependencies) and VM creation requirements, including disk sparse-image actual vs virtual size. Record expected downloads, installed/cache bytes and remaining free disk **before** acting. Do not allow installation to crowd the host disk or displace user data.
- User has approved **local installation of free tooling**. Use a bounded ordinary user-space Homebrew installation `brew install colima docker` only if Homebrew is installed, source/packages are free and preflight shows sufficient free space. Use explicit pinned/versioned packages where practical; log actual versions. Never request paid plan, cloud VM, AWS/GCP, GitHub Actions benchmark, Docker subscription, or optional trial.
- If Homebrew itself would need installation, `sudo`, privileged modifications, large downloads, license acceptance on user's behalf, or unbounded disk requirements: **STOP and document the exact interactive steps for the user**. Do not automate such changes or enter passwords, accept Docker legal terms for the user, or make machine-wide config changes without separate confirmation.
- No automatic Docker Desktop install. If Colima is not feasible, produce options with measured requirements, not a cloud fallback.

## Phase 2 — Small dedicated local Docker/Colima VM and model-free evidence
- Use a dedicated Colima profile for the experiment, with explicit CPU/memory/disk settings instead of defaults (Colima's default disk is a *virtual* 100 GiB). Size conservatively **relative to measured host free space**, enabling a 4 GiB isolated experiment installed/cache budget plus VM overhead. Make the distinction between VM allocation, actual macOS physical bytes, and container limits clear; never claim a VM limit alone guarantees Docker container limit.
- Prefer native arm64, Apple Virtualization Framework if available, no GPU, and no architecture emulation. Track original Docker context and restore it on exit. Do not expose Docker socket to containers, mount private directories or add elevated privileges.
- Run one tiny, version-pinned/digest-verified minimal Linux image, accounting for image download, its layers, metadata and caches. **No Docling, neural package or scientific PDF during this model-free test**.
- Probe actual Linux cgroup v2 memory.max <=4 GiB, memory.swap.max=0, CPU quota <=4 cores (and no more than what VM actually provides), memory.current and memory.events including a bounded child allocation. Demonstrate external process/container timeout and cleanup with a trivial sleeping process; do not allocate anything close to 4 GiB or induce OOM. Verify `--network none`, security settings, CPU quota and that no child remains. Collect exact argv, digests, logs and results; never log tokens/environment secrets.
- Preserve experiment ceilings: **2 GiB new artifact downloads**, **4 GiB isolated experiment installed/cache disk**, **4 GiB container memory**, **0 swap**, **<=4 CPU cores and <=4 effective inference threads**, **120 seconds per page**. Count setup/runtime/base-image bytes separately from candidate bytes, and also give an inclusive total; never silently exclude them from the original cap or assume compressed=installed bytes. If inclusive cap cannot be met, explicitly mark NO-GO and report alternatives. Keep enough host free space after setup.
- Grade PASS/FAIL/UNKNOWN per gate. No estimated or synthetic result counts as observed enforcement. An offline test suite passing is not empirical proof.

## Phase 3 — Candidate, only after independent resource and license GO
A subsequent explicitly bounded run may resolve Linux arm64 Python 3.11 wheels for the **same** pinned Docling/Heron versions (do not reuse the macOS wheel list), verify licenses, install into an isolated volume and acquire only approved files. Log hashes and all bytes, then disable network and run a one-page smoke test under the hard limits. Use the already frozen six-page references in 006b for later paired comparison. No OCR, remote service, GPU, VLM or unrestricted downloads. Fail closed at any resource/timeout/licensing blocker.

**For this issue, prioritize Phase 1/2 infrastructure evidence. Do not run the neural model unless all gates independently pass AND the later benchmark has a separate deliberate go-ahead.**

## Deliverables and review
- New branch stacked on PR #9; open a small PR without modifying prior records and without merging.
- Local host/pre-install diagnostics, version/package inventories and installation decision; actual installer/VM acquisition logs if permitted; cgroup/CPU/swap/timeout evidence and inclusive disk/download byte accounting if successful.
- A precise status table, blockers, and copyable user steps for any required interactive install.
- Clean teardown of disposable containers; do not delete user files or existing virtual machines. No routine GitHub Actions workflow, no runner charges, no cloud services.
- Keep ordinary `uv run --frozen --offline pytest` green; the normal existing CI may still run on a PR, but do not use GitHub Actions as the benchmark platform. Do not claim a model evaluation or any human-verified labels without evidence.

Scientific objective is to enable a **local, resource-bounded Docling vs Structure 0.2 comparison** with no paid service dependency, not to collect yet another model-free synthetic score.
