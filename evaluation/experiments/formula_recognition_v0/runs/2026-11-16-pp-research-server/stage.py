"""Owned-process runner and sampled directory allocation evidence."""
import argparse
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time


def allocation(root):
    allocated = logical = 0
    files = 0
    seen = set()
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in names:
            try:
                info = os.lstat(os.path.join(parent, name))
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) in seen:
                continue
            seen.add((info.st_dev, info.st_ino))
            files += 1
            allocated += info.st_blocks * 512
            logical += info.st_size
    fs = os.statvfs(root)
    return {'allocated_bytes': allocated, 'logical_bytes': logical, 'files': files, 'available_bytes': fs.f_bavail * fs.f_frsize}


def execute(root, name, command):
    root = Path(root)
    start = time.perf_counter()
    samples = []
    with (root / (name + '.stdout.log')).open('x') as out, (root / (name + '.stderr.log')).open('x') as err:
        child = subprocess.Popen(command, cwd=root, stdout=out, stderr=err, start_new_session=True)
        pid = child.pid
        while child.poll() is None:
            sample = allocation(root)
            sample['elapsed'] = time.perf_counter() - start
            samples.append(sample)
            print(json.dumps({'stage': name, 'elapsed': sample['elapsed'], 'allocated_bytes': sample['allocated_bytes'], 'available_bytes': sample['available_bytes']}), flush=True)
            time.sleep(5)
        child.wait(timeout=10)
    samples.append(dict(elapsed=time.perf_counter() - start, **allocation(root)))
    record = {'stage': name, 'pid': pid, 'exit_code': child.returncode, 'wall_seconds': time.perf_counter() - start,
              'process_exited': not Path('/proc', str(pid)).exists(), 'command': command, 'samples': samples}
    (root / (name + '.stage.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'stage': name, 'exit': child.returncode, 'seconds': record['wall_seconds']}), flush=True)
    return child.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    raise SystemExit(execute(args.root, args.name, command))
