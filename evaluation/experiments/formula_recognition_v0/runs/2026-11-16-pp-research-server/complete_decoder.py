"""One bounded completion of the official decoder's method-local dependencies."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess


def run(root):
    python = str(root / 'runtime/bin/python')
    prefix = [python, '-I', '-B', '-X', 'pycache_prefix=' + str(root / 'pycache')]
    source = root / 'runtime/lib/python3.12/site-packages/paddlex/inference/models/formula_recognition/processors.py'
    tree = ast.parse(source.read_text())
    decoder = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'UniMERNetDecode')
    imports = sorted({n.module for n in ast.walk(decoder) if isinstance(n, ast.ImportFrom)})
    assert imports == ['ftfy']  # tokenizers is declared by the class decorator, already constructed
    audit = {'active_decoder_method_local_imports': imports, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'reason': 'First real predict reached official post_process, whose ftfy import was omitted by ocr-core and by the initial class-declaration-only audit',
             'package_replacements': [], 'model_or_implementation_changes': False}
    (root / 'decoder-source-audit.json').write_text(json.dumps(audit, indent=2))

    def call(args, label):
        with (root / (label + '.log')).open('x') as out:
            subprocess.run(prefix + args, stdout=out, stderr=subprocess.STDOUT, check=True, timeout=180)

    call(['-m', 'pip', 'install', '--dry-run', '--only-binary=:all:', '--report', str(root / 'postprocess-resolution.json'), 'ftfy==6.3.1'], 'postprocess-resolve')
    plan = json.loads((root / 'postprocess-resolution.json').read_text())['install']
    names = {p['metadata']['name'].lower() for p in plan}
    assert 'ftfy' in names and names <= {'ftfy', 'wcwidth'}
    lock = []
    for row in plan:
        url = row['download_info']['url']
        assert url.startswith('https://files.pythonhosted.org/') and url.endswith('.whl')
        digest = row['download_info']['archive_info']['hashes']['sha256']
        lock.append(row['metadata']['name'] + '==' + row['metadata']['version'] + ' --hash=sha256:' + digest)
    (root / 'postprocess.lock').write_text('\n'.join(lock) + '\n')
    call(['-m', 'pip', 'install', '--no-deps', '--no-cache-dir', '--only-binary=:all:', '--require-hashes', '--report', str(root / 'postprocess-installed.json'), '-r', str(root / 'postprocess.lock')], 'postprocess-install')
    call(['-m', 'pip', 'check'], 'postprocess-pip-check')
    # Check the exact failing method, using a neutral diagnostic string rather
    # than any frozen reference or expected formula.
    call(['-c', 'import importlib.util; assert importlib.util.find_spec("torch") is None; from paddlex.inference.models.formula_recognition.processors import UniMERNetDecode; import ftfy; assert UniMERNetDecode.post_process(UniMERNetDecode.__new__(UniMERNetDecode), "x") == "x"; print("Official post_process including ftfy: PASS; no Torch")'], 'postprocess-check')
    (root / 'postprocess-amendment.json').write_text(json.dumps({'status': 'PASS', 'new_packages': [row['metadata']['name'] + '==' + row['metadata']['version'] for row in plan], **audit}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
