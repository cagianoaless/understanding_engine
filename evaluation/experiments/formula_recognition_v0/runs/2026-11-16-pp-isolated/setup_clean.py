"""One clean Paddle environment; no inherited packages or binary workarounds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def run(root, old):
    root.mkdir(exist_ok=False)
    begin = time.perf_counter()
    preserved = {}
    for path in sorted((old / 'outputs').rglob('*')):
        if path.is_file() and not path.is_symlink():
            preserved[path.relative_to(old).as_posix()] = sha(path)
    for name in ['cf-added.lock', 'cf-installed.json', 'inference-inputs.json', 'gpu_worker.py', 'gpu_control.py', 'inference-code-freeze.json']:
        preserved[name] = sha(old / name)
    write(root / 'codeformula-before.json', preserved)
    wheel = old / 'pp-packages/paddlepaddle_gpu-3.3.1-cp313-cp313-linux_x86_64.whl'
    assert wheel.stat().st_size == 1977882736
    assert sha(wheel) == 'dc920c514987a235ed1a54c6d2d3d82a9b8d8f056253a9fb80cc8fd2a176ac45'
    environment = dict(os.environ)
    for name in ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV']:
        environment.pop(name, None)
    environment.update({'PYTHONNOUSERSITE': '1', 'UV_PYTHON_DOWNLOADS': 'never', 'UV_CACHE_DIR': str(root / 'setup-cache')})
    commands = []

    def command(args, label, timeout=300):
        commands.append(args)
        with (root / (label + '.log')).open('x') as stream:
            result = subprocess.run(args, env=environment, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError(label + ' failed; stop after this environment correction')

    try:
        command(['uv', 'venv', '--seed', '--no-python-downloads', '--python', sys.executable, str(root / 'runtime')], 'venv')
        cfg = (root / 'runtime/pyvenv.cfg').read_text()
        assert 'include-system-site-packages = false' in cfg
        probe = 'import importlib.util,site,json,sys;assert importlib.util.find_spec("torch") is None;assert not site.ENABLE_USER_SITE;print(json.dumps({"torch_visible":False,"system_site":False,"sys_path":sys.path}))'
        command([str(root / 'runtime/bin/python'), '-I', '-c', probe], 'isolation-before')
        constraints = []
        for line in (old / 'pp-added.lock').read_text().splitlines():
            if line.startswith('paddlepaddle-gpu '):
                constraints.append('paddlepaddle-gpu==3.3.1')
            else:
                constraints.append(line.split(' --hash=')[0])
        (root / 'compatibility-constraints.txt').write_text('\n'.join(constraints) + '\n')
        python = str(root / 'runtime/bin/python')
        command([python, '-I', '-m', 'pip', 'install', '--dry-run', '--only-binary=:all:', '--report', str(root / 'resolution.json'), '--constraint', str(root / 'compatibility-constraints.txt'), str(wheel), 'paddleocr==3.7.0', 'paddlex==3.7.2'], 'resolve')
        plan = json.loads((root / 'resolution.json').read_text())['install']
        names = [row['metadata']['name'].lower().replace('_', '-') for row in plan]
        assert not set(names) & {'torch', 'torchvision', 'torchaudio', 'docling', 'docling-slim', 'triton', 'paddlepaddle'}
        lock = []
        for row in plan:
            name, version = row['metadata']['name'], row['metadata']['version']
            url = row['download_info']['url']
            digest = row['download_info']['archive_info']['hashes']['sha256']
            if name.lower() == 'paddlepaddle-gpu':
                assert url == wheel.as_uri()
                line = name + ' @ ' + url
            else:
                assert url.startswith('https://files.pythonhosted.org/') and url.endswith('.whl')
                line = name + '==' + version
            lock.append(line + ' --hash=sha256:' + digest)
        (root / 'complete.lock').write_text('\n'.join(lock) + '\n')
        command([python, '-I', '-m', 'pip', 'install', '--no-deps', '--no-cache-dir', '--only-binary=:all:', '--require-hashes', '--report', str(root / 'installed.json'), '-r', str(root / 'complete.lock')], 'install', timeout=600)
        probe = '''import importlib.util,sys,site,json,importlib.metadata as md
assert importlib.util.find_spec("torch") is None and not site.ENABLE_USER_SITE
import paddle
from paddleocr import FormulaRecognition
assert "torch" not in sys.modules and importlib.util.find_spec("torch") is None
assert paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count()==1
paddle.set_device("gpu:0")
assert float(paddle.ones([1]).numpy()[0])==1
print(json.dumps({"torch_visible":False,"torch_imported":False,"python":sys.version,"packages":{d.metadata["Name"]:d.version for d in md.distributions()},"cuda_compiled":True,"gpu_count":1,"cuda_version":paddle.version.cuda(),"cudnn_version":paddle.version.cudnn(),"gpu_probe":True,"paddleocr_import":True},indent=2))
'''
        command([python, '-I', '-c', probe], 'compatibility-import', timeout=120)
        write(root / 'setup-result.json', {'status': 'PASS', 'environment_corrections': 1, 'seconds': time.perf_counter() - begin, 'commands': commands, 'system_site_packages': False, 'torch_absent': True, 'library_paths_modified': False, 'binary_or_source_patches': False})
    except Exception as exc:
        write(root / 'setup-result.json', {'status': 'FAIL', 'environment_corrections': 1, 'seconds': time.perf_counter() - begin, 'commands': commands, 'error_type': type(exc).__name__, 'error': str(exc), 'stop': True})
        raise
    finally:
        unchanged = all(sha(old / name) == value for name, value in preserved.items())
        write(root / 'codeformula-after-setup.json', {'unchanged': unchanged, 'files': len(preserved)})
        assert unchanged


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--old', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.old)
