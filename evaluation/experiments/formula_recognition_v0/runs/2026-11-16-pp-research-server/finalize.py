"""Non-neural final identity, runtime and storage snapshot before evidence export."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def run(root):
    manifest = json.loads((root / 'inputs.json').read_text())
    hashes = {}
    for row in manifest['crops']:
        path = root / 'crops' / (row['id'] + '.png')
        digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        assert path.stat().st_size == row['bytes'] and digest == row['sha256']
        hashes['crops/' + path.name] = digest
    for row in manifest['model']['files']:
        path = root / 'model' / row['file']
        digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        assert path.stat().st_size == row['bytes'] and digest == row['expected_sha256']
        hashes['model/' + path.name] = digest
    code = 'import importlib.metadata as m,importlib.util,json,sys,site,os; assert importlib.util.find_spec("torch") is None; print(json.dumps({"python":sys.version,"packages":{d.metadata["Name"]:d.version for d in m.distributions()},"system_site_packages":False,"user_site_enabled":site.ENABLE_USER_SITE,"torch_visible":False,"cpu_affinity":sorted(os.sched_getaffinity(0))},indent=2))'
    with (root / 'final-runtime.json').open('x') as stream:
        subprocess.run([str(root / 'runtime/bin/python'), '-I', '-B', '-X', 'pycache_prefix=' + str(root / 'pycache'), '-c', code], stdout=stream, check=True, timeout=30)
    du = subprocess.run(['du', '-sk', str(root)], capture_output=True, text=True, check=True, timeout=30)
    fs = os.statvfs(root)
    result = {'verified_input_and_model_sha256': hashes, 'allocated_bytes_including_directories': int(du.stdout.split()[0]) * 1024,
              'available_filesystem_bytes': fs.f_bavail * fs.f_frsize, 'inference_finished': True,
              'note': 'This is a retained snapshot before final ZIP, not an exact transient peak. All candidate outputs/failed attempts remain separate.'}
    (root / 'final-directory.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
