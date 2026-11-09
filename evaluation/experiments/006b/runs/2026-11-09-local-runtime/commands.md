# Reproduction and exact command scope

This records an observed run, not authorization for another installation or neural execution. Choose a new external output directory; do not overwrite previous evidence or an existing VM/profile. Check all gates again. Tool versions and bottle hashes are in `bottles.json`; if Homebrew now resolves different versions, stop and audit the difference instead of calling it an exact replay.

## Tooling preflight and installation

Use the existing Homebrew installation as the ordinary user. The host collector measured `sw_vers`, `uname -m`, `sysctl -n hw.memsize`, `hw.physicalcpu`, `hw.logicalcpu`, `kern.hv_support`, `memory_pressure -Q`, `profiles status -type enrollment`, and `df -k /System/Volumes/Data`. Sandbox-denied reads were repeated only via approved access; no sudo was used.

Exact dry-run and installation argv:

```sh
brew install --dry-run --force-bottle colima docker
brew install --force-bottle colima docker
```

For both commands the process environment set HOMEBREW_NO_AUTO_UPDATE=1, HOMEBREW_NO_ANALYTICS=1, HOMEBREW_NO_INSTALL_CLEANUP=1, HOMEBREW_NO_INSTALL_UPGRADE=1 and HOMEBREW_NO_ENV_HINTS=1. HOMEBREW_CACHE and HOMEBREW_TEMP selected new subdirectories of the external run. The installer had a 240-second watchdog, checked the 20 GiB host reserve and bounded unexpected cache growth; it did not invoke `brew services`. `tooling.json` records the successful command and measured sizes. No source build was permitted.

## Dedicated VM

Set an external UE_RUN directory and scope the following environment to this workflow; preserve the original Docker context/environment. The original context was `default`. DOCKER_CONFIG="$UE_RUN/docker-config" and XDG_CACHE_HOME="$UE_RUN/xdg-cache" were set. SSH_AUTH_SOCK, DOCKER_HOST and DOCKER_CONTEXT were unset only in child processes. The attempted COLIMA_HOME override was not honored and is not a proven relocation mechanism; account for the observed state directory from `colima status`. No user's HOME variable was changed.

Exact VM start argv:

```sh
colima start ue006b --runtime docker --vm-type vz --arch aarch64 \
  --cpus 4 --memory 5 --root-disk 4 --disk 5 \
  --mount none --mount-type virtiofs --ssh-agent=false --ssh-config=false \
  --binfmt=false --vz-rosetta=false --kubernetes=false --activate=false \
  --port-forwarder none --network-address=false --network-host-addresses=false
```

Observed configuration: mounts=null, sshConfig=false, forwardAgent=false, autoActivate=false. Inspect effective files and `/proc/mounts`; flags alone do not prove isolation. Use `colima -p ue006b ssh -- ...` for commands, rather than assuming `ssh ue006b` selects a profile. Root/data nominal size is not actual allocation. The original setup monitor omitted the standard state root; its peak is unknown. Correct current and subsequent measurements must include that root, all setup caches/kegs/logs, and the external evidence directory.

## Digest-locked model-free test

The tag docker.io/library/busybox:1.37.0-musl was resolved once using official OCI metadata. The selected ARM64 manifest digest and its config hash were verified before the pull. `image-lock.json` records the immutable manifest, config and compressed layer sizes.

```sh
docker --context colima-ue006b pull --platform linux/arm64 \
  busybox@sha256:a4b7bbbb14a7e50bec3f6cbc4e2560c9b6792a7ae7062637bdfc25793817d4ff
.venv/bin/python evaluation/experiments/006b/runs/2026-11-09-local-runtime/probe.py \
  --context colima-ue006b \
  --image busybox@sha256:a4b7bbbb14a7e50bec3f6cbc4e2560c9b6792a7ae7062637bdfc25793817d4ff \
  --output "$UE_RUN/new-probe-attempt"
```

Keep the dedicated DOCKER_CONFIG active for these commands; do not change the user's default context. The script never pulls images, installs packages or imports a neural stack. Its exact Docker argv and raw output are retained per attempt. It uses 128 MiB memory, memory-swap equal to memory, one CPU, four short CPU workers, pids-limit 32, a 32 MiB tmpfs, read-only root, no host mounts, no network, UID/GID 65534, private namespaces and all capabilities dropped. The bounded child allocates approximately 16 MiB. It then externally times a different sleeping container at two seconds, kills only that container, verifies exit/PID state and removes only owned containers.

Attempt 01 failed on evidence/parser assumptions and never reached timeout testing. Its source is retained externally under the SHA in preservation.json. Attempt 02 used the corrected committed probe and passed. Neither failure is a Docling result.

Resource sampling used read-only `ps -axo pid=,rss=,%cpu=,comm=`, retaining only Lima/Colima/Virtualization entries, plus actual state/cache allocated blocks and `df`. These are sampled host observations, not guaranteed host process peaks. No environment secrets or process arguments were collected.

## Offline regression validation

```sh
UV_CACHE_DIR="$UE_RUN/uv-cache" uv run --frozen --offline pytest
```

This uses the existing Python 3.11.13 environment; no research dependency sync/reinstall was performed. Expected recorded result: 278 passed, zero failures/skips. Logs are committed with private local prefixes replaced by tokens. The original workflow is unchanged and is not a benchmark runner.

Stop after the model-free probe and verification. Linux candidate wheel/license/resource preflight and any one-page smoke test need a separate deliberate authorization; no neural acquisition is part of these commands.
