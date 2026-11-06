"""Read-only runtime discovery; never starts daemons or installs anything."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

NAMES = ("docker", "podman", "nerdctl", "ctr", "limactl", "colima")
LOCATIONS = (
    "/Applications/Docker.app", "/Applications/Docker.app/Contents/Resources/bin/docker",
    "/Applications/Podman Desktop.app", "/Applications/OrbStack.app",
    "/Applications/Rancher Desktop.app", "/usr/local/bin/docker", "/opt/homebrew/bin/docker",
    "/opt/podman/bin/podman", "/opt/homebrew/bin/podman", "/usr/local/bin/podman",
    "~/.docker/bin/docker", "~/.local/bin/podman", "~/.rd/bin/docker", "~/.orbstack/bin/docker",
    "/var/run/docker.sock", "/run/podman/podman.sock", "/sys/fs/cgroup",
)


def discover():
    memory = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"],
                            capture_output=True, text=True, timeout=5) if platform.system() == "Darwin" else None
    return {
        "stage": "B", "stage_a_local_freeze_commit": "555e4d4",
        "repository_commit_at_discovery": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "python": platform.python_version()},
        "executables": {name: shutil.which(name) for name in NAMES},
        "known_locations": {p: {"exists": Path(p).expanduser().exists(),
                                  "symlink": Path(p).expanduser().is_symlink()} for p in LOCATIONS},
        "host_memory_probe": None if memory is None else {
            "command": "/usr/sbin/sysctl -n hw.memsize", "exit_code": memory.returncode,
            "stdout": memory.stdout, "stderr": memory.stderr},
        "host_disk": dict(zip(("total_bytes", "used_bytes", "free_bytes"), shutil.disk_usage("/private/tmp"))),
        "host_logical_cpu_count": os.cpu_count(),
        "probe_policy": "Discovery only; no daemon start, installation, image pulls, privilege elevation or settings changes; no secrets or runtime contexts read.",
        "scope_limit": "PATH and listed conventional local installation locations only; not a proof that no runtime exists anywhere. No remote Linux host has been authorized/registered.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation: never overwrite earlier evidence.
    with args.output.open("x") as stream:
        stream.write(json.dumps(discover(), indent=2) + "\n")
