"""Pure preflight/accounting helpers. Synthetic tests are not runtime evidence.

No Docker runner or model installation is implemented after a missing-runtime
blocker. These helpers fail closed on unbounded/malformed cgroup v2 controls.
"""

from fractions import Fraction

GIB = 1024 ** 3
OBSERVATIONS = (
    "child_inclusive_memory_enforced", "swap_disabled_observed", "cpu_quota_observed",
    "native_pools_at_most_four", "external_timeout_tree_cleanup",
    "bounded_disk_downloads", "offline_no_plugins_or_telemetry", "license_audit",
)


def integer(value):
    if not isinstance(value, str) or not value.strip().isascii() or not value.strip().isdigit():
        raise ValueError("Expected finite nonnegative cgroup integer")
    return int(value.strip())


def cgroup_limits(snapshot):
    """Parse actual-file-shaped values, without claiming enforcement proof."""
    memory = integer(snapshot["memory.max"])
    swap = integer(snapshot["memory.swap.max"])
    parts = snapshot["cpu.max"].split()
    if len(parts) != 2:
        raise ValueError("Malformed cpu.max")
    quota, period = map(integer, parts)
    if not 0 < memory <= 4 * GIB or swap != 0 or quota <= 0 or period <= 0:
        raise ValueError("Memory/swap/CPU outside frozen limits")
    cores = Fraction(quota, period)
    if cores > 4:
        raise ValueError("CPU quota above four cores")
    return {"memory_bytes": memory, "swap_bytes": swap, "cpu_cores": cores}


def add_bytes(current, new, limit):
    """Check before accepting a download/write, never after an overrun."""
    if any(type(v) is not int or v < 0 for v in (current, new, limit)):
        raise ValueError("Invalid byte accounting")
    if current + new > limit:
        raise ValueError("Frozen byte budget exceeded")
    return current + new


def page_outcome(elapsed_seconds, exit_code, externally_timed_out=False):
    if elapsed_seconds < 0 or elapsed_seconds != elapsed_seconds or elapsed_seconds == float("inf"):
        raise ValueError("Invalid elapsed time")
    if externally_timed_out or elapsed_seconds >= 120:
        return {"status": "timeout", "denominator": 1, "successful_pages": 0}
    return {"status": "success" if exit_code == 0 else "failed",
            "denominator": 1, "successful_pages": int(exit_code == 0)}


def authorize_install(runtime_available, snapshot, observations, download_bytes, installed_bytes):
    """Configuration and missing observations can never authorize installation."""
    if not runtime_available:
        return False
    try:
        cgroup_limits(snapshot)
        add_bytes(0, download_bytes, 2 * GIB)
        add_bytes(0, installed_bytes, 4 * GIB)
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    return all(observations.get(key) is True for key in OBSERVATIONS)
