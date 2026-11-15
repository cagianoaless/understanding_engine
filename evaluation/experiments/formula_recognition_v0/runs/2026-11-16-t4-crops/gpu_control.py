"""External per-crop deadline and first-failure boundary; never reads references."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def execute(root, identifier, phase='primary'):
    inputs = json.loads((root / 'inference-inputs.json').read_text())
    if identifier not in inputs['execution_order'] or phase not in {'primary', 'environment-correction'}:
        raise ValueError('Unregistered input/phase')
    target = root / 'outputs' / phase
    target.mkdir(parents=True, exist_ok=True)
    marker = target / (identifier + '.started.json')
    with marker.open('x') as stream:
        json.dump({'id': identifier, 'deadline_seconds': 180, 'worker_sha256': hashlib.sha256((root / 'gpu_worker.py').read_bytes()).hexdigest()}, stream)
    output = target / identifier
    environment = dict(os.environ)
    environment.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                        'DO_NOT_TRACK': '1', 'CUBLAS_WORKSPACE_CONFIG': ':4096:8', 'OMP_NUM_THREADS': '4',
                        'MKL_NUM_THREADS': '4', 'TOKENIZERS_PARALLELISM': 'false', 'PYTHONHASHSEED': '0',
                        'HF_HOME': str(root / 'cache'), 'XDG_CACHE_HOME': str(root / 'cache'),
                        'TMPDIR': str(root / 'tmp')})
    (root / 'tmp').mkdir(exist_ok=True)
    command = [str(root / 'cf-runtime/bin/python'), '-B', '-u', str(root / 'gpu_worker.py'), '--root', str(root), '--id', identifier, '--output', str(output)]
    started = time.perf_counter()
    samples = []
    timed_out = False
    with (target / (identifier + '.stdout.log')).open('x') as out, (target / (identifier + '.stderr.log')).open('x') as err:
        process = subprocess.Popen(command, env=environment, stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            elapsed = time.perf_counter() - started
            if elapsed >= 180:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                break
            status = Path('/proc') / str(process.pid) / 'status'
            if status.exists():
                try:
                    data = {k: v.strip() for line in status.read_text().splitlines() if ':' in line for k, v in [line.split(':', 1)] if k in {'VmRSS', 'VmHWM', 'Threads'}}
                    samples.append({'elapsed': elapsed, **data})
                except FileNotFoundError:
                    pass
            time.sleep(.1)
        process.wait(timeout=10)
    wall = time.perf_counter() - started
    record = {'id': identifier, 'phase': phase, 'command': command, 'exit_code': process.returncode, 'timed_out': timed_out, 'wall_seconds': wall, 'deadline_seconds': 180, 'process_cleanup_verified': not Path('/proc', str(process.pid)).exists(), 'rss_samples': samples}
    (target / (identifier + '.resource.json')).write_text(json.dumps(record, indent=2) + '\n')
    prediction = json.loads((output / 'prediction.json').read_text()) if (output / 'prediction.json').exists() else None
    returned = bool(process.returncode == 0 and prediction and prediction['status'] == 'RETURNED' and prediction.get('cleaned_latex') and not any(v['token_cap_reached'] for v in prediction['generated_calls']))
    print(json.dumps({'id': identifier, 'returned': returned, 'exit_code': process.returncode, 'timeout': timed_out, 'prediction': prediction}), flush=True)
    return returned


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--phase', default='primary')
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.root, args.id, args.phase) else 1)
