"""Official binary-only isolated runtime plus the explicit formula decoder closure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def run(root, uv, interpreter):
    root = Path(root)
    commands = []
    begin = time.perf_counter()

    def command(args, label, timeout=900):
        commands.append(args)
        with (root / (label + '.log')).open('x') as stream:
            process = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        if process.returncode:
            raise RuntimeError(label + ' failed; preserve evidence and stop')

    try:
        artifact = json.loads((root / 'paddle-artifact.json').read_text())
        available = os.statvfs(root).f_bavail * os.statvfs(root).f_frsize
        assert available > artifact['compressed_bytes'] + artifact['declared_unpacked_bytes'], 'Known Paddle archive+install does not fit'
        (root / 'wheels').mkdir(exist_ok=True)
        wheel = root / 'wheels' / artifact['filename']
        assert artifact['url'].startswith('https://paddle-whl.cdn.bcebos.com/stable/cu126/paddlepaddle-gpu/')
        digest = hashlib.sha256()
        count = 0
        tick = time.perf_counter()
        with urllib.request.urlopen(artifact['url'], timeout=60) as response, wheel.open('xb') as output:
            while block := response.read(4 * 1024**2):
                count += len(block)
                assert count <= artifact['compressed_bytes']
                output.write(block)
                digest.update(block)
        assert count == artifact['compressed_bytes']
        if artifact.get('recorded_sha256'):
            assert digest.hexdigest() == artifact['recorded_sha256'], 'Observed runtime wheel identity changed'
        write(root / 'paddle-acquisition.json', {'url': artifact['url'], 'bytes': count, 'sha256': digest.hexdigest(), 'expected_publisher_sha256': None, 'seconds': time.perf_counter() - tick})
        command([uv, 'venv', '--seed', '--no-python-downloads', '--python', interpreter, str(root / 'runtime')], 'venv')
        assert 'include-system-site-packages = false' in (root / 'runtime/pyvenv.cfg').read_text()
        python = str(root / 'runtime/bin/python')
        prefix = [python, '-I', '-B', '-X', 'pycache_prefix=' + str(root / 'pycache')]
        # No CUDA-13 dependency constraints are carried to this CUDA-12.6 runtime.
        command(prefix + ['-m', 'pip', 'install', '--dry-run', '--only-binary=:all:', '--report', str(root / 'base-resolution.json'), '--constraint', str(root / 'base-constraints.txt'), str(wheel), 'paddleocr==3.7.0', 'paddlex==3.7.2'], 'base-resolve')
        base = json.loads((root / 'base-resolution.json').read_text())['install']
        forbidden = {'torch', 'torchvision', 'torchaudio', 'triton', 'docling', 'paddlepaddle'}
        assert not {r['metadata']['name'].lower().replace('_', '-') for r in base} & forbidden

        def lock_rows(plan):
            result = []
            for row in plan:
                name = row['metadata']['name']
                url = row['download_info']['url']
                value = row['download_info']['archive_info']['hashes']['sha256']
                if name.lower() == 'paddlepaddle-gpu':
                    assert url == wheel.as_uri() and value == digest.hexdigest()
                    pin = name + ' @ ' + url
                else:
                    assert url.startswith('https://files.pythonhosted.org/') and url.endswith('.whl')
                    pin = name + '==' + row['metadata']['version']
                result.append(pin + ' --hash=sha256:' + value)
            return result

        (root / 'base.lock').write_text('\n'.join(lock_rows(base)) + '\n')
        command(prefix + ['-m', 'pip', 'install', '--no-deps', '--no-cache-dir', '--require-hashes', '--only-binary=:all:', '--report', str(root / 'base-installed.json'), '-r', str(root / 'base.lock')], 'base-install')
        # The narrow amendment is resolved independently after restoring base deps.
        command(prefix + ['-m', 'pip', 'install', '--dry-run', '--only-binary=:all:', '--report', str(root / 'decoder-resolution.json'), 'tokenizers==0.23.3'], 'decoder-resolve')
        addition = json.loads((root / 'decoder-resolution.json').read_text())['install']
        assert [row['metadata']['name'].lower() for row in addition] == ['tokenizers'], 'Unexpected dependency replacement/addition; stop for review'
        assert addition[0]['metadata']['version'] == '0.23.3'
        (root / 'decoder.lock').write_text('\n'.join(lock_rows(addition)) + '\n')
        command(prefix + ['-m', 'pip', 'install', '--no-deps', '--no-cache-dir', '--require-hashes', '--only-binary=:all:', '--report', str(root / 'decoder-installed.json'), '-r', str(root / 'decoder.lock')], 'decoder-install')
        command(prefix + ['-m', 'pip', 'check'], 'pip-check')
        write(root / 'setup-result.json', {'status': 'PASS', 'seconds': time.perf_counter() - begin, 'commands': commands, 'binary_only': True, 'new_decoder_packages': ['tokenizers==0.23.3'], 'existing_package_replacements': []})
    except Exception as error:
        write(root / 'setup-result.json', {'status': 'FAIL', 'seconds': time.perf_counter() - begin, 'commands': commands, 'error_type': type(error).__name__, 'error': str(error)})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--uv', required=True)
    parser.add_argument('--interpreter', required=True)
    args = parser.parse_args()
    run(args.root, args.uv, args.interpreter)
