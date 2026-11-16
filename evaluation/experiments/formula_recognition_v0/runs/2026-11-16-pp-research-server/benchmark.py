"""Sequential guarded crop calls; no reference input; externally timed and sampled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def gpu():
    p = subprocess.run(['nvidia-smi', '--query-gpu=memory.free,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=10)
    free, utilization = map(int, p.stdout.strip().split(','))
    return {'free_mib': free, 'utilization_percent': utilization}


def run(root, name='initial'):
    assert name in {'initial', 'decoder-complete'}
    output_root = root / ('outputs' if name == 'initial' else 'outputs-decoder-complete')
    assert json.loads((root / 'preflight.json').read_text())['status'] == 'PASS'
    manifest = json.loads((root / 'inputs.json').read_text())
    output_root.mkdir(exist_ok=False)
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')}
    write(root / ('prediction-freeze.json' if name == 'initial' else 'prediction-freeze-decoder-complete.json'), {'scripts': code, 'inputs_sha256': hashlib.sha256((root / 'inputs.json').read_bytes()).hexdigest(), 'references_present': False})
    summary = []
    for identifier in manifest['execution_order']:
        time.sleep(3)  # Let the previous process's GPU utilization window expire.
        capacity = gpu()
        if capacity['free_mib'] < 4096 or capacity['utilization_percent'] > 10:
            summary.append({'id': identifier, 'status': 'DEFERRED_RESOURCE_CONFLICT', 'capacity': capacity})
            break
        args = ['/usr/bin/python3', '-S', '-B', str(root / 'isolate.py'), '--root', str(root), '--allow-self-task-metadata', '--', str(root / 'runtime/bin/python'), '-I', '-B', '-X', 'pycache_prefix=' + str(root / 'pycache'), str(root / 'pp_worker.py'), '--root', str(root), '--crop-root', str(root / 'crops'), '--id', identifier, '--output', str(output_root / identifier)]
        started = time.perf_counter()
        samples = []
        timeout = False
        with (output_root / (identifier + '.stdout.log')).open('x') as out, (output_root / (identifier + '.stderr.log')).open('x') as err:
            process = subprocess.Popen(args, stdout=out, stderr=err, start_new_session=True)
            expired = threading.Event()

            def deadline():
                expired.set()
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            timer = threading.Timer(180, deadline)
            timer.start()
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                sample = {'elapsed': elapsed}
                try:
                    for line in Path('/proc/' + str(process.pid) + '/status').read_text().splitlines():
                        if line.startswith(('VmRSS:', 'VmHWM:')):
                            key, value, _ = line.split()
                            sample[key[:-1] + '_bytes'] = int(value) * 1024
                except FileNotFoundError:
                    pass
                try:
                    fields = Path('/proc/' + str(process.pid) + '/stat').read_text().rsplit(')', 1)[1].split()
                    sample['process_cpu_seconds'] = (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
                except FileNotFoundError:
                    pass
                p = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
                if p.returncode == 0:
                    for line in p.stdout.splitlines():
                        fields = line.split(',')
                        if fields[0].strip() == str(process.pid):
                            sample['process_vram_bytes'] = int(fields[1]) * 1024**2
                samples.append(sample)
                if expired.is_set():
                    break
                time.sleep(0.25)
            process.wait(timeout=15)
            timer.cancel()
            timeout = expired.is_set()
        # A process group with descendants must not survive into the next crop.
        try:
            os.killpg(process.pid, 0)
            clean = False
        except ProcessLookupError:
            clean = True
        record = {'id': identifier, 'pid': process.pid, 'exit_code': process.returncode, 'timed_out': timeout, 'wall_seconds': time.perf_counter() - started, 'process_cleanup_verified': clean, 'capacity_before': capacity, 'samples': samples}
        write(output_root / (identifier + '.resource.json'), record)
        prediction = output_root / identifier / 'prediction.json'
        returned = prediction.exists() and json.loads(prediction.read_text())['status'] == 'RETURNED'
        summary.append({k: record[k] for k in ['id', 'exit_code', 'timed_out', 'wall_seconds', 'process_cleanup_verified']})
        print(json.dumps(summary[-1]), flush=True)
        if process.returncode or timeout or not returned or not clean:
            break
    write(root / ('benchmark-summary.json' if name == 'initial' else 'benchmark-summary-decoder-complete.json'), summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--name', default='initial')
    args = parser.parse_args()
    run(args.root, args.name)
