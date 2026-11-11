"""Offline contract demonstration from retained PR17 files, never a benchmark.

No annotations, scoring, PDFs, candidate imports, Docker or inference are used.
The source is the complete original BERT extraction; only retained BERT page 6
predictions are supplied. Other source pages remain available and source-only.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from understanding_engine.contracts import json_bytes
from understanding_engine.hybrid import build_hybrid, order_hypothesis
from understanding_engine.hybrid_contract import validate_hybrid

REPO = Path(__file__).resolve().parents[2]
PR17 = REPO/'evaluation/experiments/006b/runs/2026-11-10-six-page-comparison'


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def publish(output, payloads):
    """Publish a complete new directory; failed private staging stays diagnostic."""
    lock = output.with_name('.'+output.name+'.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError('Choose a new output directory')
        staging = Path(tempfile.mkdtemp(prefix='.'+output.name+'-', dir=output.parent))
        for name, payload in payloads.items():
            with (staging/name).open('xb') as stream:
                stream.write(payload)
        staging.rename(output)
    finally:
        os.close(fd)
        lock.unlink()


def demonstrate(root, output):
    assert not output.exists(), 'Choose a new output directory'
    assert subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=output.parent,
                          capture_output=True).returncode != 0, 'Large artifacts must be outside Git'
    records = {r['relative_path']: r for r in json.loads((PR17/'external-evidence-manifest.json').read_bytes())['records']}
    inputs = []

    def read(relative):
        path = root/relative
        assert path.is_file() and not path.is_symlink()
        payload = path.read_bytes(); registered = records[relative]
        assert len(payload) == registered['bytes'] and digest(payload) == registered['sha256'], 'Evidence changed'
        inputs.append({'relative_path': relative, 'bytes': len(payload), 'sha256': digest(payload)})
        return json.loads(payload)

    source = read('sources/bert-extraction.json')
    docling = read('native/docling-bert-p06/docling.json')
    traversal = read('native/docling-bert-p06/items.json')
    execution = read('native/docling-bert-p06/execution.json')
    structure = read('native/structure-bert-p06/structure.json')
    assert source['source_sha256'] == execution['source_pdf_sha256'] == structure['source']['pdf_sha256']
    assert execution['status'] == 'success' and execution['page_range'] == [6, 6]
    predictions = [
        {'provider': 'structure_0_2', 'version': '0.2.0', 'source_pdf_sha256': source['source_sha256'],
         'status': 'available', 'native': {'document': structure},
         'provenance': {'baseline_commit': 'ba82b2c7f71604d5bcc2859b1a05de112723107d',
                        'native_file_sha256': next(x['sha256'] for x in inputs if x['relative_path'].endswith('structure.json'))}, 'error': None},
        {'provider': 'docling', 'version': '2.148.0', 'source_pdf_sha256': execution['source_pdf_sha256'],
         'status': 'available', 'native': {'document': docling, 'items': traversal},
         'provenance': {'identity_basis': 'Registered original SHA256 in hash-verified frozen page execution ledger; Docling binary_hash is not SHA256',
                        'heron_revision': execution['heron_revision'], 'execution_sha256': inputs[-2]['sha256'],
                        'native_document_sha256': inputs[1]['sha256'], 'native_traversal_sha256': inputs[2]['sha256']}, 'error': None}]
    original = json_bytes(source)
    result = build_hybrid(source, predictions)
    validate_hybrid(result, source)
    assert json_bytes(source) == original
    assert all(h['status'] == 'available' for h in result['hypotheses']), [h['issues'] for h in result['hypotheses']]
    h = result['hypotheses'][1]
    selected = [r for r in h['regions'] if r['native_item_id'] == '#/texts/65']
    assert len(selected) == 2
    order = order_hypothesis(result, h['id'], selected[0]['id'], selected[1]['id'])
    assert order['direction'] == 'unresolved'
    payload = json_bytes(result)
    summary = {'schema_version': 'hybrid-v0-retained-demonstration.1',
        'post_hoc_interface_demonstration': True, 'independent_validation': False,
        'new_inference_calls': 0, 'benchmark_metrics_recalculated': False,
        'frozen_annotations_loaded': False, 'inputs': inputs,
        'full_hybrid': {'relative_path': 'hybrid.json', 'bytes': len(payload), 'sha256': digest(payload)},
        'source_pages_conserved': len(source['pages']),
        'source_characters_conserved': sum(len(p['characters']) for p in source['pages']),
        'source_page_6_characters': len(source['pages'][5]['characters']),
        'source_only_pages': result['source_only_pages'],
        'hypotheses': [{'provider': x['prediction']['provider'], 'status': x['status'],
                       'items': len(x['items']), 'regions': len(x['regions']),
                       'region_association_states': dict(Counter(r['status'] for r in x['regions']))}
                      for x in result['hypotheses']],
        'multi_box_item_order': order,
        'verification': 'agent_visual_checked inherited references; no references used by builder',
        'independent_human_verifications': 0}
    # Small inspection view, explicitly not a complete HybridDocument. No source
    # PDF, full paper text or private path is committed through this excerpt.
    selected_ids = {ref for region in selected for ref in region['geometric_character_ids'][:2]}
    excerpt = {'schema_version': 'hybrid-v0-inspection-excerpt.1', 'is_complete_hybrid_document': False,
        'full_hybrid': summary['full_hybrid'], 'source_pdf_sha256': source['source_sha256'], 'page_number': 6,
        'source_geometry': source['pages'][5]['geometry'],
        'source_characters': [c for c in source['pages'][5]['characters'] if c['id'] in selected_ids],
        'native_hierarchy_items': [{k: v for k, v in i.items() if k != 'diagnostic_model_text'} for i in h['items'] if i['native_id'] in {'#/tables/0', '#/groups/0', '#/texts/65'}],
        'multi_box_regions': [{k: v for k, v in region.items() if k != 'geometric_character_ids'} |
                              {'geometric_character_ids_excerpt': region['geometric_character_ids'][:2],
                               'geometric_character_count': len(region['geometric_character_ids'])} for region in selected],
        'order_hypothesis': order, 'caveat': 'Partial inspection view only; complete authoritative source and all associations remain in the hashed external hybrid.json. No accuracy claim.'}
    publish(output, {'hybrid.json': payload, 'demonstration.json': json_bytes(summary),
                     'inspection-excerpt.json': json_bytes(excerpt)})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.evidence_root, args.output), indent=2))
