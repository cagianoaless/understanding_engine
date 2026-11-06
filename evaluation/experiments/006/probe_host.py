"""Read host capabilities and probe the exact RSS limit in a short child.

No allocation test, dependency installation, model import or network access.
On a restricted host errors remain evidence; do not convert them to passes.
"""

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

PROBE = '''import json,resource
result={"RLIMIT_RSS":resource.RLIMIT_RSS,"RLIMIT_AS":resource.RLIMIT_AS,"requested_cap_bytes":4*1024**3}
for name in ["RLIMIT_RSS","RLIMIT_AS"]:
 key=getattr(resource,name);result[name+"_before"]=resource.getrlimit(key)
 try:resource.setrlimit(key,(4*1024**3,4*1024**3));result[name+"_after"]=resource.getrlimit(key)
 except (OSError,ValueError) as exc:result[name+"_error"]=repr(exc)
result["process_rss_bytes"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps(result))
'''


def command(argv):
    try:
        run = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return {"argv": argv, "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "error": repr(exc)}


def main():
    result = {"platform": platform.platform(), "python": platform.python_version(),
              "machine": platform.machine(), "logical_cpus": os.cpu_count(),
              "disk": shutil.disk_usage(Path.cwd())._asdict(), "allocation_bytes": 0,
              "units": "Darwin ru_maxrss bytes; ps RSS KiB; do not reuse these units on another OS"}
    result["hardware_commands"] = [command(["/usr/sbin/sysctl", "-n", "hw.memsize"]),
                                   command(["/usr/sbin/sysctl", "-n", "hw.model"]),
                                   command(["/bin/ps", "-o", "pid=,ppid=,rss=,comm=", "-p", str(os.getpid())])]
    result["limit_probe"] = command([sys.executable, "-B", "-c", PROBE])
    result["warning"] = "Even successful setrlimit calls alone do not prove a hard aggregate process-tree RSS cap. No GO is inferred."
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
