"""Local-only frozen-reference comparison after downloading all native outputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
FORMULA = HERE.parents[1]
COMPARE = runpy.run_path(str(FORMULA / 'runs/2026-11-15-cpu-recognition/scoring.py'))['compare']


def termination(prediction):
    calls = prediction['generated_calls']
    if not calls:
        return 'NO_GENERATION'
    call = calls[-1]
    if call['token_cap_reached']:
        return 'INCOMPLETE_TOKEN_LIMIT'
    if prediction['native_output'].get('stop_reason') == 'stop_sequence':
        return 'INCOMPLETE_NATIVE_REPETITION_STOP'
    eos = call['eos_token_id']
    if call['last_token_id'] in (eos if isinstance(eos, list) else [eos]):
        return 'EOS_RETURNED'
    return 'UNRESOLVED_TERMINATION'


def evaluate(evidence, pp_evidence, renders, destination):
    assert not destination.exists()
    destination.mkdir()
    inputs = json.loads((HERE / 'inference-inputs.json').read_text())
    references = {r['id']: r for r in json.loads((FORMULA / 'references.json').read_text())['expressions']}
    adjudications = {r['id']: r for r in json.loads((HERE / 'adjudications.json').read_text())['expressions']}
    render_by_id = {r['id']: r for r in json.loads(renders.read_text())}
    predictions = []
    per_formula = []
    totals = {}
    for identifier in inputs['execution_order']:
        path = evidence / 'outputs/primary' / identifier / 'prediction.json'
        value = json.loads(path.read_text())
        assert value['status'] == 'RETURNED' and value['input_crop_sha256'] == next(r['sha256'] for r in inputs['crops'] if r['id'] == identifier)
        assert termination(value) == adjudications[identifier]['completion']
        resource = json.loads((evidence / 'outputs/primary' / (identifier + '.resource.json')).read_text())
        assert not resource['timed_out'] and resource['exit_code'] == 0 and resource['process_cleanup_verified']
        predictions.append(value)
        comparison = COMPARE(references[identifier]['latex'], value['cleaned_latex'])
        review = adjudications[identifier]
        if termination(value) != 'EOS_RETURNED':
            assert review['full_expression_correct'] is None, 'Incomplete output cannot establish whole-expression correctness'
        for category, decisions in review['component_decisions'].items():
            counter = totals.setdefault(category, Counter())
            counter.update(r['decision'] for r in decisions)
        per_formula.append({'id': identifier, 'termination': termination(value), 'frozen_reference_comparison': comparison,
                            'agent_source_review': review, 'tex_render': render_by_id[identifier],
                            'recognition_seconds': value['recognition_seconds'], 'initialization_seconds': value['engine_initialization_seconds'],
                            'external_wall_seconds': resource['wall_seconds'], 'peak_gpu_allocated_bytes': value['peak_gpu_allocated_bytes'],
                            'peak_gpu_reserved_bytes': value['peak_gpu_reserved_bytes'], 'peak_process_rss_bytes': value['peak_process_rss_bytes'],
                            'generated_tokens': value['generated_calls'][-1]['generated_tokens']})
    pp = json.loads((pp_evidence / 'pp-outcome.json').read_text())
    results = {'schema_version': 'formula-gpu-results.1', 'reference_status': 'agent_visual_checked', 'independently_human_verified': 0,
               'selected_denominator': 8, 'attempted': 8, 'returned': 8, 'eos_returns': sum(r['termination'] == 'EOS_RETURNED' for r in per_formula),
               'incomplete_native_stop': sum(r['termination'].startswith('INCOMPLETE') for r in per_formula), 'crashes': 0, 'timeouts': 0, 'unexecuted': 0,
               'exact': {'numerator': sum(r['frozen_reference_comparison']['exact'] for r in per_formula), 'denominator': 8},
               'formatting_normalized': {'numerator': sum(r['frozen_reference_comparison']['formatting_normalized'] for r in per_formula), 'denominator': 8, 'policy': 'Unchanged frozen strip + line-ending normalization; not mathematical equivalence'},
               'agent_full_expression': {'correct': sum(r['agent_source_review']['full_expression_correct'] is True for r in per_formula),
                                         'incorrect': sum(r['agent_source_review']['full_expression_correct'] is False for r in per_formula),
                                         'incomplete_unknown': sum(r['agent_source_review']['full_expression_correct'] is None for r in per_formula),
                                         'selected_denominator': 8, 'caveat': 'Provisional source-checked assessment with explicit notation/typography policy; not independent validation or semantic proof'},
               'component_counts': {k: {'correct': v['correct'], 'incorrect': v['incorrect'], 'missing': v['missing'], 'ambiguous': v['ambiguous'], 'unscoreable': v['unscoreable'], 'denominator': sum(v.values()), 'scope': 'Explicitly enumerated source-checked core relations, including observable parts of incomplete output; not complete recognition accuracy'} for k, v in totals.items()},
               'tex_compile': {'passed': sum(r['tex_render']['exit'] == 0 for r in per_formula), 'denominator': 8, 'wrapper': 'Common align* for all unchanged bodies', 'semantic_validity_inferred': False},
               'per_formula': per_formula, 'pp_formulanet': pp, 'model_quality_winner': None,
               'winner_reason': 'PP has no predictions; CodeFormula source review is development-exposed and provisional.',
               'formula_structure_v0_recommendation': 'Research prototype justified for complete source-reviewed/validated hypotheses, with explicit rejection/uncertainty. Not reliable automatic mathematical ground truth; do not infer symbol-level PDF alignment.'}
    predictions_payload = {'schema_version': 'formula-gpu-predictions.1', 'reference_latex_loaded_by_remote_inference': False,
                           'codeformula': predictions, 'pp_formulanet': {'model_revision': pp['model_revision'], 'attempted': 0, 'selected_denominator': 8, 'status': 'SETUP_IMPORT_FAILURE',
                           'formulas': [{'id': i, 'status': 'NOT_EXECUTED', 'latex': None} for i in inputs['execution_order']]}}
    for name, data in [('predictions.json', predictions_payload), ('results.json', results)]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['evidence', 'pp-evidence', 'renders', 'destination']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.evidence, args.pp_evidence, args.renders, args.destination)
    print(json.dumps({k: result[k] for k in ['attempted', 'returned', 'eos_returns', 'incomplete_native_stop', 'exact', 'formatting_normalized', 'agent_full_expression', 'component_counts', 'tex_compile']}, indent=2))
