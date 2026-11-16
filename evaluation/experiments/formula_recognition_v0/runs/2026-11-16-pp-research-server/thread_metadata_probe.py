"""Actual positive/negative probes for the authorized process-local exception."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import threading


def run(root):
    # The launcher uses --write-scope ROOT/test/allow. This owned sibling
    # proves that the proc exception does not expose unrelated regular files.
    outside = root / 'test/deny/marker'
    assert outside.read_text() == 'preserve'
    try:
        fd = os.open(outside, os.O_WRONLY)  # no truncation/content modification
    except PermissionError:
        pass
    else:
        os.close(fd)
        raise AssertionError('Persistent-file boundary weakened')
    tid = threading.get_native_id()
    own = Path('/proc/self/task') / str(tid) / 'comm'
    own.write_text('ue-own-probe')
    assert own.read_text().strip() == 'ue-own-probe'
    # A new process does NOT acquire a write exception to its own task tree
    # from the parent's inode-specific rule. Only an explicitly guarded
    # eventual CUDA process receives its own exception.
    child = subprocess.run(['/usr/bin/python3', '-S', '-B', '-c', "import os; p='/proc/self/task/'+str(os.getpid())+'/comm'; f=os.open(p,os.O_WRONLY); os.close(f)"], capture_output=True, text=True)
    assert child.returncode != 0 and 'PermissionError' in child.stderr
    result = {'persistent_sibling_open_denied': True, 'own_thread_metadata_write': True,
              'child_process_metadata_write_denied': True, 'external_persistent_writes_enabled': False}
    # GPU initialization checks the actual driver operation that failed under
    # the original strict guard; no model import or recognition occurs.
    driver = ctypes.CDLL('libcuda.so.1')
    status = driver.cuInit(0)
    result['cuInit'] = status
    assert status == 0, result
    count = ctypes.c_int()
    assert driver.cuDeviceGetCount(ctypes.byref(count)) == 0
    result['cuda_device_count'] = count.value
    assert count.value == 1
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
