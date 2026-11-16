"""Local-only comparison of downloaded predictions and explicit source reviews."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / '2026-11-16-t4-crops'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def compare(evidence, review, rendering):
    manifest = json.loads((HERE / 'inputs.json').read_text())
    spec = importlib.util.spec_from_file_location('frozen_scorer', HERE.parent / '2026-11-15-cpu-recognition/scoring.py')
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    refs_path = HERE.parents[1] / 'references.json'
    references = {r['id']: r for r in json.loads(refs_path.read_text())['expressions']}
    baseline = {r['id']: r for r in json.loads((PRIOR / 'adjudications.json').read_text())['expressions']}
    decisions = {r['id']: r for r in review['expressions']}
    rows = []
    predictions = []
    counts = {}
    output_root = evidence / 'outputs-decoder-complete'
    for identifier in manifest['execution_order']:
        path = output_root / identifier / 'prediction.json'
        source = next(c for c in manifest['crops'] if c['id'] == identifier)
        if not path.exists():
            rows.append({'id': identifier, 'status': 'NOT_EXECUTED', 'exact': None, 'formatting_normalized': None, 'full_output_correct': None,
                         'codeformula_full_output_correct': baseline[identifier]['full_expression_correct']})
            continue
        prediction = json.loads(path.read_text())
        assert prediction['input_crop_sha256'] == source['sha256']
        events = [json.loads(line) for line in (path.parent / 'events.jsonl').read_text().splitlines()]
        called = any(r['event'] == 'predictor_invoked' for r in events)
        returned = prediction['status'] == 'RETURNED'
        assert not returned or called
        raw = prediction['raw_latex']
        resource = json.loads((output_root / (identifier + '.resource.json')).read_text())
        entry = {'id': identifier, 'status': prediction['status'], 'input': source, 'raw_latex': raw,
                 'native_result': prediction.get('native_result'), 'extra_cleanup_applied': False,
                 'model_revision': prediction['model_revision'], 'reference_inputs': False,
                 'prediction_file_sha256': sha(path)}
        # Native input paths are diagnostic only; retain the original bytes in
        # the external verified archive, publish only a portable crop identity.
        entry['native_result'] = json.loads(json.dumps(entry['native_result']).replace(json.loads((evidence / '.experiment-owner.json').read_text())['root'], '$RUN'))
        predictions.append(entry)
        score = scorer.compare(references[identifier]['latex'], raw)
        adjudication = decisions.get(identifier)
        if returned:
            assert adjudication and review['status'] == 'agent_visual_checked'
            assert review['independent_human_verifications'] == 0
            expected = baseline[identifier]['component_decisions']
            for category, components in expected.items():
                actual = adjudication['component_decisions'][category]
                assert [c['component'] for c in actual] == [c['component'] for c in components]
                allowed = {'correct', 'incorrect', 'missing', 'ambiguous', 'unscoreable'}
                assert all(c['decision'] in allowed for c in actual)
                counts.setdefault(category, Counter()).update(c['decision'] for c in actual)
        samples = resource['samples']
        rows.append({'id': identifier, 'status': prediction['status'], 'neural_invoked': called,
                     'exact': score['exact'], 'formatting_normalized': score['formatting_normalized'],
                     'reference_discrepancy': 'Frozen Latin a versus source alpha remains unscoreable' if identifier == 'nature_weights' else None,
                     'full_output_correct': adjudication['full_expression_correct'] if adjudication else None,
                     'codeformula_full_output_correct': baseline[identifier]['full_expression_correct'],
                     'review': adjudication, 'tex_compile': rendering.get(identifier),
                     'initialization_seconds': prediction.get('model_initialization_seconds'),
                     'recognition_seconds': prediction.get('recognition_seconds'),
                     'wall_seconds': resource['wall_seconds'], 'exit_code': resource['exit_code'], 'timeout': resource['timed_out'],
                     'peak_process_rss_bytes': prediction['peak_process_rss_bytes'],
                     'sampled_process_vram_bytes': max((s.get('process_vram_bytes', 0) for s in samples), default=0),
                     'paddle_peak_allocated_bytes': prediction.get('paddle_peak_allocated_bytes'),
                     'paddle_peak_reserved_bytes': prediction.get('paddle_peak_reserved_bytes'),
                     'sampled_process_cpu_seconds': max((s.get('process_cpu_seconds', 0) for s in samples), default=0)})
    def metric(key):
        return {'correct': sum(row.get(key) is True for row in rows), 'incorrect': sum(row.get(key) is False for row in rows), 'unknown': sum(row.get(key) is None for row in rows), 'selected_denominator': 8}
    result = {'schema_version': 'pp-research-comparison.1', 'reference_status': 'agent_visual_checked',
              'independent_human_verifications': 0, 'selected_denominator': 8,
              'attempted': sum(r['status'] != 'NOT_EXECUTED' for r in rows),
              'neural_invocations_total': sum(json.loads(line)['event'] == 'predictor_invoked' for folder in ['outputs', 'outputs-decoder-complete'] for path in (evidence / folder).glob('*/events.jsonl') for line in path.read_text().splitlines()),
              'first_postprocess_failure_preserved': 'outputs/attn_fraction; missing ftfy; no decoded LaTeX; separate from eight successful returns',
              'returned': sum(r['status'] == 'RETURNED' for r in rows),
              'exact': metric('exact'), 'formatting_normalized': metric('formatting_normalized'),
              'pp_full_expression': metric('full_output_correct'), 'codeformula_full_expression': metric('codeformula_full_output_correct'),
              'component_counts': {k: {'reference_denominator': sum(v.values()), **{x: v[x] for x in ['correct', 'incorrect', 'missing', 'ambiguous', 'unscoreable']}} for k, v in counts.items()},
              'codeformula_component_counts_preserved': json.loads((PRIOR / 'results.json').read_text())['component_counts'],
              'per_formula': rows, 'quality_scope': 'Eight development-exposed crops, provisional visual source review; not independent validation or proof of source-aligned AST',
              'performance_scope': 'PP uses RTX 5000 Ada / CUDA12.6 / FP32; preserved CodeFormula uses T4 / CUDA13 / FP16. Not a controlled hardware speed comparison',
              'baseline_predictions_sha256': sha(PRIOR / 'predictions.json'), 'baseline_results_sha256': sha(PRIOR / 'results.json'),
              'references_sha256': sha(refs_path), 'codeformula_rerun': False}
    return {'schema_version': 'pp-research-predictions.1', 'reference_inputs_uploaded': False, 'model': manifest['model'], 'formulas': predictions}, result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['evidence', 'review', 'rendering', 'destination']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    predictions, results = compare(args.evidence, json.loads(args.review.read_text()), json.loads(args.rendering.read_text()))
    args.destination.mkdir(exist_ok=False)
    dump(args.destination / 'predictions.json', predictions)
    dump(args.destination / 'results.json', results)
