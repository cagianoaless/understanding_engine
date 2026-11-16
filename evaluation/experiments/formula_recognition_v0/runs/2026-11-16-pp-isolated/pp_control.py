"""Sequential guard and external per-crop watchdog; no model/reference logic."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def prior_success(output, identifier):
    resource = json.loads((output / (identifier + '.resource.json')).read_text())
    result = json.loads((output / identifier / 'prediction.json').read_text())
    return resource['exit_code'] == 0 and not resource['timed_out'] and result['status'] == 'RETURNED' and bool(result['raw_latex'])


def execute(root, crop_root, identifier):
    manifest = json.loads((root / 'inputs.json').read_text())
    if identifier not in manifest['execution_order']:
        raise ValueError('Unregistered crop')
    assert json.loads((root / 'setup-result.json').read_text())['status'] == 'PASS'
    output = root / 'outputs'
    output.mkdir(exist_ok=True)
    index = manifest['execution_order'].index(identifier)
    for name in manifest['execution_order'][:index]:
        assert prior_success(output, name), 'Earlier crop did not return successfully; stop'
    freeze = json.loads((root / 'inference-freeze.json').read_text())
    for name, digest in freeze.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    with (output / (identifier + '.started.json')).open('x') as stream:
        json.dump({'id': identifier, 'deadline_seconds': 180, 'worker_sha256': freeze['pp_worker.py']}, stream)
    env = dict(os.environ)
    for name in ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV']:
        env.pop(name, None)
    env.update({'PYTHONNOUSERSITE': '1', 'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4', 'HF_HUB_OFFLINE': '1',
                'TRANSFORMERS_OFFLINE': '1', 'MODELSCOPE_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True', 'DO_NOT_TRACK': '1', 'PYTHONHASHSEED': '0'})
    command = [str(root / 'runtime/bin/python'), '-I', '-B', '-u', str(root / 'pp_worker.py'), '--root', str(root),
               '--crop-root', str(crop_root), '--id', identifier, '--output', str(output / identifier)]
    samples = []
    timed_out = False
    start = time.perf_counter()
    with (output / (identifier + '.stdout.log')).open('x') as out, (output / (identifier + '.stderr.log')).open('x') as err:
        process = subprocess.Popen(command, env=env, stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            elapsed = time.perf_counter() - start
            if elapsed >= 180:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                break
            status = Path('/proc') / str(process.pid) / 'status'
            row = {'elapsed': elapsed}
            if status.exists():
                try:
                    row.update({k: v.strip() for line in status.read_text().splitlines() if ':' in line for k, v in [line.split(':', 1)] if k in ['VmRSS', 'VmHWM', 'Threads']})
                except FileNotFoundError:
                    pass
            query = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if query.returncode == 0:
                for line in query.stdout.splitlines():
                    parts = [v.strip() for v in line.split(',')]
                    if len(parts) == 2 and parts[0] == str(process.pid) and parts[1].isdigit():
                        row['process_gpu_memory_MiB'] = int(parts[1])
            samples.append(row)
            time.sleep(.2)
        process.wait(timeout=10)
    result = {'id': identifier, 'exit_code': process.returncode, 'timed_out': timed_out, 'wall_seconds': time.perf_counter() - start,
              'deadline_seconds': 180, 'process_cleanup_verified': not Path('/proc', str(process.pid)).exists(), 'samples': samples,
              'sampled_process_gpu_peak_bytes': max([s.get('process_gpu_memory_MiB', 0) for s in samples] or [0]) * 1024**2,
              'gpu_peak_caveat': 'nvidia-smi process samples in MiB; lower bound, may miss transient peaks; not directly comparable to framework allocator counters',
              'command': command, 'LD_LIBRARY_PATH_modified': False}
    (output / (identifier + '.resource.json')).write_text(json.dumps(result, indent=2) + '\n')
    prediction = json.loads((output / identifier / 'prediction.json').read_text()) if (output / identifier / 'prediction.json').exists() else None
    success = bool(not timed_out and process.returncode == 0 and prediction and prediction['status'] == 'RETURNED' and prediction['raw_latex'])
    print(json.dumps({'id': identifier, 'success': success, 'exit_code': process.returncode, 'timed_out': timed_out, 'prediction': prediction}), flush=True)
    return success


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--crop-root', type=Path, required=True)
    parser.add_argument('--id', required=True)
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.root, args.crop_root, args.id) else 1)
