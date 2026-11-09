"""Model-free, CPU-only probe; never installs packages or pulls images.

Run only against a dedicated, independently preflighted local Docker context.
Synthetic unit tests do not establish actual enforcement. Raw evidence belongs
outside Git; this script requires an already pulled ARM64 BusyBox digest.
"""

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import time
import uuid


GIB = 1024 ** 3
FROZEN = runpy.run_path(str(Path(__file__).resolve().parents[2] / "gates.py"))
SCRIPT = r"""set -eu
section() { printf '\n@@ %s\n' "$1"; }
for file in memory.max memory.swap.max memory.swap.current cpu.max memory.events; do
  section "$file"; cat "/sys/fs/cgroup/$file"
done
section memory.before; cat /sys/fs/cgroup/memory.current
awk 'BEGIN { s=sprintf("%16384s", "x"); for(i=0;i<1024;i++) a[i]=s i; system("sleep 2") }' &
child=$!
sleep 0.5
section memory.during; cat /sys/fs/cgroup/memory.current
section child.pid; printf '%s\n' "$child"
section cgroup.procs; cat /sys/fs/cgroup/cgroup.procs
wait "$child"
section memory.after; cat /sys/fs/cgroup/memory.current
section cpu.before; cat /sys/fs/cgroup/cpu.stat
workers=''
for n in 1 2 3 4; do
  sh -c 'while :; do :; done' &
  workers="$workers $!"
done
sleep 2
for worker in $workers; do kill "$worker"; done
wait || true
section cpu.after; cat /sys/fs/cgroup/cpu.stat
section memory.peak; cat /sys/fs/cgroup/memory.peak
section memory.events.after; cat /sys/fs/cgroup/memory.events
section swaps; cat /proc/swaps
section interfaces; ls /sys/class/net
section routes; cat /proc/net/route
section egress
if nc -w 1 1.1.1.1 443 </dev/null >/tmp/network.out 2>/tmp/network.err; then
  echo exit_code=0
else
  code=$?; echo "exit_code=$code"; cat /tmp/network.err
fi
section filesystem
if touch /must-not-write 2>/tmp/rootfs.err; then echo unexpected_writable_root; else echo readonly_root; fi
test ! -e /Users && test ! -e /host && test ! -S /var/run/docker.sock && echo no_host_paths_or_socket
section security; grep -E '^(CapEff|NoNewPrivs|Seccomp):' /proc/self/status
section architecture; uname -m
"""


def sections(text):
    result = {}
    current = None
    for line in text.splitlines():
        if line.startswith("@@ "):
            current = line[3:]
            if current in result:
                raise ValueError("Duplicate probe section")
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return {key: "\n".join(value).strip() for key, value in result.items()}


def counters(text):
    return {line.split()[0]: int(line.split()[1]) for line in text.splitlines()}


def controls(image, name):
    if not re.fullmatch(r"busybox@sha256:[a-f0-9]{64}", image):
        raise ValueError("An already acquired BusyBox digest is required")
    if not re.fullmatch(r"ue006b-[a-z0-9-]+", name):
        raise ValueError("Not a dedicated probe container name")
    return [
        "create", "--pull=never", "--name", name,
        "--platform", "linux/arm64", "--memory", "128m",
        "--memory-swap", "128m", "--cpus", "1", "--pids-limit", "32",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "65534:65534",
        "--cgroupns", "private", "--ipc", "private",
        "--tmpfs", "/tmp:size=32m,noexec,nosuid,nodev",
        "--env", "OMP_NUM_THREADS=4", "--env", "MKL_NUM_THREADS=4",
        "--env", "OPENBLAS_NUM_THREADS=4", "--env", "NUMEXPR_NUM_THREADS=4",
        image, "sh", "-c",
    ]


def assess(snapshot, inspection):
    """Evaluate observed evidence; malformed/missing data fails closed."""
    limits = FROZEN["cgroup_limits"](snapshot)
    before, after = counters(snapshot["cpu.before"]), counters(snapshot["cpu.after"])
    events = counters(snapshot["memory.events.after"])
    host = inspection["HostConfig"]
    child = int(snapshot["child.pid"])
    gates = {
        "cgroup_v2_limits": limits["memory_bytes"] == 128 * 1024 ** 2
            and limits["cpu_cores"] == 1,
        "child_memory_accounting": child in [int(p) for p in snapshot["cgroup.procs"].split()]
            and int(snapshot["memory.during"]) - int(snapshot["memory.before"]) >= 8 * 1024 ** 2,
        "no_oom": events.get("oom", -1) == events.get("oom_kill", -1) == 0,
        "zero_container_swap": int(snapshot["memory.swap.current"]) == 0
            and host["MemorySwap"] == host["Memory"] == 128 * 1024 ** 2,
        "cpu_throttling_observed": after["nr_throttled"] > before["nr_throttled"]
            and after["usage_usec"] > before["usage_usec"],
        "network_disabled": host["NetworkMode"] == "none"
            and snapshot["interfaces"].split() == ["lo"]
            and snapshot["egress"].splitlines()[0] == "exit_code=1"
            and len(snapshot["routes"].splitlines()) == 1,
        "host_filesystem_isolation": inspection["Mounts"] == []
            and host["ReadonlyRootfs"] is True and host["Privileged"] is False
            and host["CapDrop"] == ["ALL"]
            and "no-new-privileges" in " ".join(host["SecurityOpt"])
            and "readonly_root" in snapshot["filesystem"]
            and "no_host_paths_or_socket" in snapshot["filesystem"]
            and inspection["Config"]["User"] == "65534:65534"
            and "CapEff:\t0000000000000000" in snapshot["security"]
            and "NoNewPrivs:\t1" in snapshot["security"]
            and "Seccomp:\t2" in snapshot["security"]
            and not host.get("Devices") and not host.get("DeviceRequests")
            and not host.get("Binds"),
        "native_arm64": snapshot["architecture"] == "aarch64",
    }
    return {"gates": gates, "memory_peak_bytes": int(snapshot["memory.peak"]),
            "cpu_usage_delta_usec": after["usage_usec"] - before["usage_usec"],
            "throttled_period_delta": after["nr_throttled"] - before["nr_throttled"],
            "inference_threads": None, "inference_threads_status": "not_run",
            "oom_boundary_stress_test": "not_run; deliberately no OOM allocation"}


def budget(download_bytes, installed_cache_bytes, free_bytes):
    FROZEN["add_bytes"](0, download_bytes, 2 * GIB)
    FROZEN["add_bytes"](0, installed_cache_bytes, 4 * GIB)
    if type(free_bytes) is not int or free_bytes < 20 * GIB:
        raise ValueError("Host free-space reserve not met")
    return True


def confirmed_absent(exit_code, stdout, stderr):
    """Distinguish a removed object from permission/daemon/connection errors."""
    return (exit_code != 0 and stdout.strip() == "[]"
            and re.search(r"no such (object|container)", stderr, re.IGNORECASE) is not None)


def execute(context, image, destination):
    destination = Path(destination).resolve()
    if destination.is_relative_to(Path(__file__).resolve().parents[5]):
        raise ValueError("Raw evidence must stay outside the repository")
    destination.mkdir(parents=True, exist_ok=False)
    docker = [shutil.which("docker") or "docker", "--context", context]
    records, owned = [], set()
    outcome = {"schema_version": "006b.local-runtime-probe.1", "success": False}

    def call(args, timeout=20, checked=True):
        started = time.monotonic()
        r = subprocess.run(docker + args, capture_output=True, text=True, timeout=timeout)
        records.append({"argv": docker + args, "exit_code": r.returncode,
                        "stdout": r.stdout, "stderr": r.stderr,
                        "elapsed_seconds": time.monotonic() - started})
        if checked and r.returncode:
            raise RuntimeError("Docker command failed; see raw command log")
        return r

    def inspect(name):
        return json.loads(call(["inspect", name]).stdout)[0]

    def remove(name):
        call(["rm", name])
        owned.remove(name)
        missing = call(["inspect", name], checked=False)
        if not confirmed_absent(missing.returncode, missing.stdout, missing.stderr):
            raise RuntimeError("Container cleanup not confirmed")

    suffix = uuid.uuid4().hex[:10]
    normal, sleeping = "ue006b-probe-" + suffix, "ue006b-timeout-" + suffix
    try:
        info = json.loads(call(["image", "inspect", image]).stdout)[0]
        if info["Architecture"] != "arm64" or info["Os"] != "linux":
            raise ValueError("Image is not native Linux ARM64")
        outcome["image"] = info
        call(controls(image, normal) + [SCRIPT])
        owned.add(normal)
        prediction = call(["start", "-a", normal], timeout=20)
        snapshot = sections(prediction.stdout)
        observed = inspect(normal)
        if observed["State"]["ExitCode"] != 0 or observed["State"]["Running"]:
            raise RuntimeError("Probe did not finish cleanly")
        outcome["snapshot"] = snapshot
        outcome["inspection"] = observed
        outcome["assessment"] = assess(snapshot, observed)
        remove(normal)
        call(controls(image, sleeping) + ["sleep 300 & wait"])
        owned.add(sleeping)
        start = time.monotonic()
        process = subprocess.Popen(docker + ["start", "-a", sleeping],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        timed_out = False
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            timed_out = True
            call(["kill", "--signal", "KILL", sleeping])
            stdout, stderr = process.communicate(timeout=10)
            records.append({"argv": docker + ["start", "-a", sleeping],
                            "exit_code": process.returncode, "stdout": stdout,
                            "stderr": stderr, "external_timeout_seconds": 2,
                            "elapsed_seconds": time.monotonic() - start})
        dead = inspect(sleeping)
        cleanup = (timed_out and not dead["State"]["Running"]
                   and dead["State"]["Pid"] == 0 and dead["State"]["ExitCode"] == 137
                   and dead["State"]["OOMKilled"] is False)
        outcome["timeout"] = {"deadline_seconds": 2, "triggered": timed_out,
                              "elapsed_seconds": time.monotonic() - start,
                              "inspection_after_kill": dead, "tree_cleanup_verified": cleanup}
        remove(sleeping)
        outcome["assessment"]["gates"]["external_timeout_cleanup"] = cleanup
        outcome["success"] = all(outcome["assessment"]["gates"].values())
    except Exception as error:
        outcome["error"] = type(error).__name__ + ": " + str(error)
    finally:
        for name in sorted(owned):
            call(["rm", "-f", name], checked=False)
        outcome["commands"] = records
        (destination / "probe.json").write_text(json.dumps(outcome, indent=2) + "\n")
    return outcome


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = execute(args.context, args.image, args.output)
    print(json.dumps({key: result[key] for key in ("success", "assessment", "error") if key in result}))
    raise SystemExit(0 if result["success"] else 2)
