"""Offline policy regressions, never empirical Docker enforcement evidence."""

from pathlib import Path
import runpy

import pytest


PROBE_PATH = (Path(__file__).resolve().parents[1] / "evaluation/experiments/006b"
              / "runs/2026-11-09-local-runtime/probe.py")
probe = runpy.run_path(str(PROBE_PATH))


def test_no_implicit_image_pull_or_host_access():
    args = probe["controls"]("busybox@sha256:" + "a" * 64, "ue006b-probe-test")
    assert "--pull=never" in args
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--memory-swap") + 1] == args[args.index("--memory") + 1]
    assert "--privileged" not in args and "--mount" not in args and "-v" not in args
    assert "--read-only" in args and "--cap-drop" in args
    assert "--gpus" not in args and "--pid=host" not in args


@pytest.mark.parametrize("image", ["busybox:latest", "busybox:1.37.0", "other@sha256:" + "a" * 64])
def test_image_requires_exact_preacquired_digest(image):
    with pytest.raises(ValueError):
        probe["controls"](image, "ue006b-probe-test")


@pytest.mark.parametrize("name", ["user-container", "ue006b-../../anything", "ue006b-x; echo unsafe"])
def test_only_owned_probe_container_names(name):
    with pytest.raises(ValueError):
        probe["controls"]("busybox@sha256:" + "a" * 64, name)


@pytest.mark.parametrize("extra", ["@@ memory.max\n1\n@@ memory.max\n2", "@@ x\na\n@@ x\nb"])
def test_duplicate_kernel_sections_are_not_silently_overwritten(extra):
    with pytest.raises(ValueError):
        probe["sections"](extra)


def test_exact_budget_boundaries_and_host_reserve():
    gib = probe["GIB"]
    assert probe["budget"](2 * gib, 4 * gib, 20 * gib)
    for values in [(2 * gib + 1, 0, 20 * gib), (0, 4 * gib + 1, 20 * gib),
                   (0, 0, 20 * gib - 1), (True, 0, 20 * gib), (0, 0, True)]:
        with pytest.raises(ValueError):
            probe["budget"](*values)


def test_unknown_cgroup_limit_is_never_a_pass():
    with pytest.raises(ValueError):
        probe["assess"]({"memory.max": "max", "memory.swap.max": "0", "cpu.max": "100000 100000"}, {})


def test_missing_runtime_observations_fail_closed():
    with pytest.raises(KeyError):
        probe["assess"]({"memory.max": "134217728", "memory.swap.max": "0", "cpu.max": "100000 100000"}, {})


def test_no_neural_runtime_or_package_install_in_probe():
    # Import in a fresh interpreter with ordinary project dependencies only;
    # this is a dependency-boundary regression, not an inference-thread test.
    import subprocess
    import sys

    program = (
        "import runpy,sys; runpy.run_path(sys.argv[1]); "
        "assert not any(m.split('.')[0] in {'torch','docling','transformers','onnxruntime'} "
        "for m in sys.modules)"
    )
    subprocess.run([sys.executable, "-B", "-c", program, str(PROBE_PATH)], check=True)


@pytest.mark.parametrize("message", ["error: no such object: ue006b-probe-test", "Error: No such container: ue006b-probe-test"])
def test_cleanup_confirmation_accepts_docker_case_variants(message):
    assert probe["confirmed_absent"](1, "[]\n", message)


@pytest.mark.parametrize("code,stdout,message", [(1, "[]", "permission denied"),
                                                 (1, "", "cannot connect to daemon"),
                                                 (0, "[]", "no such object")])
def test_cleanup_does_not_confuse_permission_or_daemon_failure_with_absence(code, stdout, message):
    assert not probe["confirmed_absent"](code, stdout, message)


def synthetic_observations():
    snapshot = {
        "memory.max": "134217728", "memory.swap.max": "0", "cpu.max": "100000 100000",
        "memory.swap.current": "0", "memory.before": "1000000", "memory.during": "18000000",
        "memory.peak": "19000000", "child.pid": "2", "cgroup.procs": "1\n2",
        "cpu.before": "nr_throttled 0\nusage_usec 1000",
        "cpu.after": "nr_throttled 10\nusage_usec 2000000",
        "memory.events.after": "oom 0\noom_kill 0", "interfaces": "lo",
        "routes": "Iface Destination Gateway", "egress": "exit_code=1",
        "filesystem": "readonly_root\nno_host_paths_or_socket",
        "security": "CapEff:\t0000000000000000\nNoNewPrivs:\t1\nSeccomp:\t2",
        "architecture": "aarch64",
    }
    inspection = {"Mounts": [], "Config": {"User": "65534:65534"}, "HostConfig": {
        "MemorySwap": 134217728, "Memory": 134217728, "NetworkMode": "none",
        "ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
    }}
    return snapshot, inspection


def test_silent_connection_failure_still_requires_kernel_isolation_evidence():
    snapshot, inspection = synthetic_observations()
    assert probe["assess"](snapshot, inspection)["gates"]["network_disabled"]


@pytest.mark.parametrize("key,value", [("interfaces", "eth0 lo"),
                                      ("routes", "Iface Destination Gateway\neth0 0 0"),
                                      ("egress", "exit_code=127")])
def test_failed_connection_alone_cannot_establish_network_isolation(key, value):
    snapshot, inspection = synthetic_observations()
    snapshot[key] = value
    assert not probe["assess"](snapshot, inspection)["gates"]["network_disabled"]
