"""Regenerate frozen source caches, without generating structure predictions."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import runpy
import subprocess
import time

from understanding_engine.contracts import json_bytes
from understanding_engine.pdf_parser import extract_pdf

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
BASELINE = 'ba82b2c7f71604d5bcc2859b1a05de112723107d'


def save(path, data):
    with path.open('xb') as stream:
        stream.write(json_bytes(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args()
    raw = args.raw.resolve(strict=True)
    assert subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=raw,
                          capture_output=True).returncode != 0
    assert not subprocess.check_output(['git', 'diff', BASELINE, '--', 'src', 'pyproject.toml', 'uv.lock'])
    references = runpy.run_path(str(EXPERIMENT / 'references.py'))
    freeze = references['verify_freeze'](EXPERIMENT)
    annotations = json.loads((EXPERIMENT / 'annotations.json').read_bytes())
    geometries = json.loads((EXPERIMENT / 'page_geometry.json').read_bytes())
    counts = references['validate_annotations'](annotations, geometries)
    restoration = runpy.run_path(str(HERE.parent / '2026-11-10-input-restoration/restore_inputs.py'))
    restoration['verify_local'](args.mapping)
    mapping = json.loads(args.mapping.read_bytes())
    paths = {r['document_id']: Path(r['accepted_path']) for r in mapping['entries']}
    registry = json.loads((EXPERIMENT / 'source-inputs.json').read_bytes())
    roots = json.loads((raw / 'storage-roots.json').read_bytes())
    allocation = runpy.run_path(str(HERE.parent / '2026-11-09-cpu-archive-audit/archive_audit.py'))['allocation_snapshot']
    samples = []

    def guard(pending=0):
        sample = allocation(roots)
        samples.append(sample)
        assert sample['host_available_bytes'] - pending >= 20 * 1024**3, 'Host reserve'
        assert sample['allocated_bytes'] + pending + 128 * 1024**2 <= 6 * 1024**3, 'Inclusive cap'

    guard(256 * 1024**2)
    destination = raw / 'sources'
    destination.mkdir()
    result = {'schema_version': '006b.source-regeneration.1', 'baseline_commit': BASELINE,
              'python': platform.python_version(), 'freeze': freeze, 'reference_counts': counts,
              'mapping_sha256': hashlib.sha256(args.mapping.read_bytes()).hexdigest(),
              'all_inputs_reverified': True, 'documents': [], 'comparative_scoring_run': False}
    try:
        for row in registry:
            started = time.perf_counter()
            document = extract_pdf(paths[row['document_id']])
            payload = json_bytes(document)
            actual = hashlib.sha256(payload).hexdigest()
            record = {'document_id': row['document_id'], 'source_pdf_sha256': document['source_sha256'],
                      'page_count': document['page_count'], 'extraction_sha256': actual,
                      'original_extraction_sha256': row['authoritative_cached_extraction_sha256'],
                      'byte_identical_to_original_cache': actual == row['authoritative_cached_extraction_sha256'],
                      'bytes': len(payload), 'seconds': time.perf_counter()-started,
                      'parser': document['parser'], 'selected_pages': []}
            assert document['source_sha256'] == row['pdf_sha256_verified']
            for annotation in annotations['pages']:
                if annotation['document_id'] != row['document_id']:
                    continue
                page = document['pages'][annotation['page_number'] - 1]
                chars = {c['id']: c for c in page['characters']}
                geometry = page['geometry']
                assert geometry == geometries[annotation['id']], 'Frozen geometry mismatch'
                all_refs = [ref for decision in annotation['paragraph_decisions']
                            for group in decision['source_character_ids'] for ref in group]
                assert all(ref in chars for ref in all_refs), 'Missing original character IDs'
                for decision in annotation['paragraph_decisions']:
                    for box, group in zip(decision['line_strips'], decision['source_character_ids']):
                        for ref in group:
                            x0, y0, x1, y1 = chars[ref]['bbox']
                            assert box[0] <= (x0+x1)/2 <= box[2] and box[1] <= (y0+y1)/2 <= box[3], 'Frozen source strip differs'
                record['selected_pages'].append({'id': annotation['id'], 'page_number': page['page_number'],
                    'geometry': geometry, 'character_count': len(chars), 'frozen_strip_references': len(all_refs),
                    'all_frozen_ids_exist_and_centers_match': True,
                    'character_layer_sha256': hashlib.sha256(json_bytes({'characters': page['characters']})).hexdigest()})
            # Retain a differing extraction for diagnosis; never substitute its IDs.
            (destination / (row['document_id'] + '-extraction.json')).write_bytes(payload)
            result['documents'].append(record)
            save(raw / (row['document_id']+'-source-check.json'), record)
            guard()
            print(json.dumps({k: record[k] for k in ['document_id', 'byte_identical_to_original_cache', 'bytes', 'seconds']}), flush=True)
            if not record['byte_identical_to_original_cache']:
                raise ValueError('STOP: original full-cache identity not reproduced; investigate before scoring')
        result['gate'] = 'PASS'
    except Exception as exc:
        result.update(gate='BLOCKED', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        save(raw / 'source-compatibility.json', result)
        save(raw / 'source-storage-samples.json', {'samples': samples})


if __name__ == '__main__':
    main()
