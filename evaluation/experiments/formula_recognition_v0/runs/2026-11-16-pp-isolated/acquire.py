"""Exact three-file PP-FormulaNet-S acquisition; no inference/reference access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request


def acquire(root):
    manifest = json.loads((root / 'inputs.json').read_text())['model']
    assert manifest['repo'] == 'PaddlePaddle/PP-FormulaNet-S'
    assert manifest['revision'] == '0572450e501be9eb1b1cdb7e00fccf4b22fab4df'
    assert {r['file'] for r in manifest['files']} == {'inference.json', 'inference.yml', 'inference.pdiparams'}
    target = root / 'model'
    target.mkdir(exist_ok=False)
    records = []
    for row in manifest['files']:
        assert Path(row['file']).name == row['file']
        assert row['url'].startswith('https://huggingface.co/PaddlePaddle/PP-FormulaNet-S/resolve/' + manifest['revision'] + '/')
        start = time.perf_counter()
        path = target / (row['file'] + '.part')
        digest = hashlib.sha256()
        blob = hashlib.sha1(b'blob ' + str(row['bytes']).encode() + b'\0')
        count = 0
        with urllib.request.urlopen(row['url'], timeout=60) as response, path.open('xb') as stream:
            parsed = urllib.parse.urlsplit(response.url)
            assert parsed.scheme == 'https' and (parsed.hostname == 'huggingface.co' or parsed.hostname.endswith('.hf.co') or parsed.hostname.endswith('.huggingface.co'))
            while block := response.read(1024 * 1024):
                count += len(block)
                assert count <= row['bytes']
                stream.write(block)
                digest.update(block)
                blob.update(block)
        assert count == row['bytes']
        if row['expected_sha256']:
            assert digest.hexdigest() == row['expected_sha256']
        else:
            assert blob.hexdigest() == row['git_blob_sha1']
        final = target / row['file']
        os.replace(path, final)
        records.append({'file': row['file'], 'bytes': count, 'sha256': digest.hexdigest(), 'allocated_bytes': final.stat().st_blocks * 512,
                        'verified_expected_sha256': row['expected_sha256'] is not None, 'verified_git_blob_sha1': row['expected_sha256'] is None,
                        'seconds': time.perf_counter() - start})
        print(json.dumps(records[-1]), flush=True)
    with (root / 'model-acquisition.json').open('x') as stream:
        json.dump({'repo': manifest['repo'], 'revision': manifest['revision'], 'files': records}, stream, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    acquire(parser.parse_args().root)
