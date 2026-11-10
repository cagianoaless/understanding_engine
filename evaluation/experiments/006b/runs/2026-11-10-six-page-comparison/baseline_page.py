"""One unchanged Structure 0.2 call in its frozen host dependency environment."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import time
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--page', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    kernel = None
    if platform.system() == 'Linux':
        from docling_page import cgroup
        kernel = cgroup()
        assert int(kernel['memory.max']) <= 4294967296 and kernel['memory.swap.max'] == '0'
        quota, period = kernel['cpu.max'].split()
        assert quota != 'max' and int(quota) <= 4*int(period)
    started = time.perf_counter()
    from understanding_engine.contracts import json_bytes
    from understanding_engine.structure_v2 import reconstruct, RobustSettings
    from dataclasses import asdict
    settings_path = Path('/run/baseline-settings.json') if kernel else Path(__file__).parents[2]/'baseline-settings.json'
    settings = json.loads(settings_path.read_text())['settings']
    assert asdict(RobustSettings()) == settings
    raw = args.source.read_bytes()
    begin = time.perf_counter()
    native = reconstruct(raw, page_numbers=[args.page])
    payload = json_bytes(native)
    args.output.mkdir(exist_ok=False)
    (args.output / 'structure.json').write_bytes(payload)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    record = {'status': 'success', 'page': args.page, 'python': platform.python_version(),
        'reconstruction_validation_serialization_seconds': time.perf_counter()-begin,
        'process_seconds': time.perf_counter()-started,
        'cpu_seconds': usage.ru_utime+usage.ru_stime,
        'peak_process_rss_bytes': usage.ru_maxrss if platform.system() == 'Darwin' else usage.ru_maxrss*1024,
        'initial_cgroup': kernel,
        'final_cgroup': cgroup() if kernel else None,
        'measurement_role': 'controlled Linux baseline' if kernel else 'original host environment decision-equivalence check only',
        'effective_computation_threads': 1,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'output_sha256': hashlib.sha256(payload).hexdigest(), 'output_bytes': len(payload),
        'algorithm': native['algorithm']}
    assert not any(n == 'torch' or n.startswith(('torch.', 'transformers.', 'docling.')) for n in sys.modules)
    (args.output / 'execution.json').write_bytes(json_bytes(record))
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == record['source_sha256']
    print(json.dumps(record))


if __name__ == '__main__':
    main()
