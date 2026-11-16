"""Reverify the exact official model after transfer from the acquisition host."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    manifest = json.loads((root / 'inputs.json').read_text())['model']
    assert manifest['repo'] == 'PaddlePaddle/PP-FormulaNet-S'
    assert manifest['revision'] == '0572450e501be9eb1b1cdb7e00fccf4b22fab4df'
    records = []
    for row in manifest['files']:
        path = root / 'model' / row['file']
        assert not path.is_symlink() and path.is_file()
        assert path.stat().st_size == row['bytes']
        value = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        assert value == row['expected_sha256']
        records.append({'file': row['file'], 'bytes': row['bytes'], 'sha256': value, 'allocated_bytes': path.stat().st_blocks * 512, 'verified_expected_sha256': True})
    with (root / 'model-acquisition.json').open('x') as stream:
        json.dump({'repo': manifest['repo'], 'revision': manifest['revision'], 'files': records, 'route': 'Official pinned HTTPS acquisition on client; SSH transfer; independent full hash verification on server', 'direct_server_acquisition': 'Failed before any file was created: network unreachable'}, stream, indent=2)
    print('All three pinned model hashes verified on server', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    verify(parser.parse_args().root)
