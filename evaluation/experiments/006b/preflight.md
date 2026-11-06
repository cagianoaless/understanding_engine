# Experiment 006b preflight — NO-GO, missing prerequisite

Stage A was completed and committed locally as
`555e4d4c582fdb6a7ce35d66739760b63a4bed36` **before** runtime discovery.
`freeze.json` preserves those references; neither candidate generated predictions.

Measured discovery (`runtime-discovery.json`, then the broader reproducible
`runtime-discovery-expanded.json`) found Darwin 25.5.0, arm64, Python 3.11.13 and
eight host logical CPUs. No docker, podman, nerdctl, ctr, limactl or colima
executable was found in PATH. Listed conventional application/binary locations,
including Docker Desktop, Podman Desktop, OrbStack, Rancher Desktop and common
user CLI locations, were absent. Standard runtime sockets and `/sys/fs/cgroup`
were absent. These are bounded local checks, not an exhaustive search of every
possible installation. No existing remote Linux host was authorized or registered.

The broader probe measured 11,051,196,416 free host disk bytes (a changing host
observation, not a container disk quota). Reading host RAM with
`/usr/sbin/sysctl -n hw.memsize` returned exit 1, `Operation not permitted`.
Host RAM is unmeasured in this run. No privilege escalation was attempted.
Docker VM architecture/allocation, daemon version and security configuration are
unavailable. No runtime was installed or started and no settings were changed.

**Exact blocker:** no usable existing Linux container environment was discovered.
Actual cgroup memory/swap/CPU, child-inclusive memory enforcement, observed native
thread pools, bounded disk/download writes, external timeout and whole-process
cleanup therefore remain **not_run**, not passed or empirically unsupported.
`gates.py` has synthetic offline tests; those are not container-enforcement proof.

Current official documentation was read after Stage A:

- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/):
  hard limits differ from reservations; disabling swap requires equal memory
  and memory-swap settings, whereas memory-swap=0 is ignored. CPU quotas differ
  from shares. The actual kernel controls must be checked.
- [Docker Desktop settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/):
  VM CPU, RAM, swap and disk allocations are distinct from container limits.
  No Desktop settings were opened or modified.
- [Docker security](https://docs.docker.com/engine/security/): namespaces/cgroups
  and daemon access matter. No privileged container, secret/host-root/socket mount
  or remote daemon was used.

The frozen caps remain 2 GiB combined new artifact downloads (including base
images), 4 GiB installed/cache including layers, 4 GiB container memory, zero
swap, four CPU quota cores, four effective inference threads and 120 seconds per
page with whole-tree termination. These would bound the container, not the host
or Docker VM. None is reported as execution-verified.

Linux cp311 resolution and license audit were not attempted without an actual
validated target. The 103-package macOS closure from Experiment 006 is not reused
as a Linux inventory. Docling remains pinned to 2.148.0; Heron remains pinned to
`8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`. The prior model inventory and declared
licenses remain unchanged; full Linux artifact compatibility is unexecuted.
There were no image pulls, dependency installs, weight downloads or model imports.
Documentation access was online; zero candidate artifact downloads is not a
claim of zero network traffic.

Stages C and D are **not_run**. Stop here without installing Docker, changing
limits, selecting another model or running an uncontrolled host benchmark.
