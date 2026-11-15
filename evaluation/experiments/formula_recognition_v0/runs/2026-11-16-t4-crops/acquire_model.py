"""Acquire only the eleven frozen public CodeFormulaV2 files on the remote VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request


def acquire(root):
    manifest = json.loads((root / 'inference-inputs.json').read_text())['model']
    assert manifest['repo'] == 'docling-project/CodeFormulaV2'
    assert manifest['revision'] == 'ecedbe111d15c2dc60bfd4a823cbe80127b58af4'
    destination = root / 'artifacts' / 'docling-project--CodeFormulaV2'
    destination.mkdir(parents=True, exist_ok=False)
    records = []
    for row in manifest['files']:
        assert Path(row['file']).name == row['file']
        url = row['source_url']
        assert url.startswith('https://huggingface.co/docling-project/CodeFormulaV2/resolve/' + manifest['revision'] + '/')
        expected = row['bytes']
        temporary = destination / (row['file'] + '.part')
        begin = time.perf_counter()
        request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('xb') as stream:
            parsed = urllib.parse.urlsplit(response.url)
            assert parsed.scheme == 'https' and (parsed.hostname == 'huggingface.co' or parsed.hostname.endswith('.hf.co') or parsed.hostname.endswith('.huggingface.co'))
            count = 0
            digest = hashlib.sha256()
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > expected:
                    raise ValueError('Payload larger than frozen artifact')
                stream.write(block)
                digest.update(block)
        assert count == expected and digest.hexdigest() == row['sha256']
        final = destination / row['file']
        os.replace(temporary, final)
        record = {'file': row['file'], 'bytes': count, 'sha256': digest.hexdigest(), 'allocated_bytes': final.stat().st_blocks * 512, 'seconds': time.perf_counter() - begin}
        records.append(record)
        print(json.dumps(record), flush=True)
    (root / 'model-acquisition.json').write_text(json.dumps({'revision': manifest['revision'], 'files': records, 'total_payload_bytes': sum(v['bytes'] for v in records)}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    acquire(parser.parse_args().root)
