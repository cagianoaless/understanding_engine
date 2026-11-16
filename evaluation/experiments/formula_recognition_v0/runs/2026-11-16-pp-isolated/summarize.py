"""Report measured initialization failure without inventing recognition quality."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / '2026-11-16-t4-crops'


def classify(evidence):
    first = json.loads((evidence / 'outputs/attn_fraction/prediction.json').read_text())
    events = [json.loads(line) for line in (evidence / 'outputs/attn_fraction/events.jsonl').read_text().splitlines()]
    resource = json.loads((evidence / 'outputs/attn_fraction.resource.json').read_text())
    assert first['status'] == 'FAILED' and first['raw_latex'] is None
    assert 'tokenizers' in first['traceback'] and 'UniMERNetDecode' in first['traceback']
    assert not any(row['event'] == 'predictor_invoked' for row in events)
    assert resource['exit_code'] == 1 and not resource['timed_out'] and resource['process_cleanup_verified']
    start = next(row['elapsed'] for row in events if row['event'] == 'model_initialization_start')
    end = next(row['elapsed'] for row in events if row['event'] == 'failed')
    return {'failure_phase': 'PREDICTOR_CONSTRUCTION', 'cause': 'Missing optional tokenizers dependency required by UniMERNetDecode',
            'target_attempted': True, 'neural_predictor_invoked': False, 'latex_returned': False,
            'recognition_seconds': None, 'successful_initialization_seconds': None,
            'failed_constructor_observed_interval_seconds': end - start,
            'failed_worker_seconds': first['total_seconds'], 'external_wall_seconds': resource['wall_seconds'],
            'exit_code': resource['exit_code'], 'timeout': resource['timed_out'], 'oom_observed': False,
            'peak_process_rss_bytes': first['peak_process_rss_bytes'],
            'paddle_peak_allocated_bytes': first['paddle_peak_allocated_bytes'],
            'paddle_peak_reserved_bytes': first['paddle_peak_reserved_bytes'],
            'sampled_process_gpu_peak_bytes': resource['sampled_process_gpu_peak_bytes'],
            'memory_scope': 'Failed initialization, not inference cost; NVML samples are a lower bound and Paddle tensor counters may exclude native allocations',
            'traceback': first['traceback']}


def summarize(evidence, destination):
    destination.mkdir(exist_ok=False)
    manifest = json.loads((HERE / 'inputs.json').read_text())
    policy = json.loads((HERE / 'protocol.json').read_text())
    assert hashlib.sha256((PRIOR / 'predictions.json').read_bytes()).hexdigest() == policy['preserved_codeformula_predictions_sha256']
    assert hashlib.sha256((PRIOR / 'results.json').read_bytes()).hexdigest() == policy['preserved_codeformula_results_sha256']
    baseline = json.loads((PRIOR / 'results.json').read_text())
    failure = classify(evidence)
    setup = json.loads((evidence / 'setup-result.json').read_text())
    assert setup['status'] == 'PASS' and setup['environment_corrections'] == 1
    assert json.loads((evidence / 'codeformula-final.json').read_text())['unchanged']
    complete = json.loads((evidence / 'completion.json').read_text())
    assert complete['attempted'] == ['attn_fraction'] and complete['returned'] == []
    rows = []
    for identifier in manifest['execution_order']:
        crop = next(row for row in manifest['crops'] if row['id'] == identifier)
        rows.append({'id': identifier, 'input': crop,
                     'status': 'INITIALIZATION_FAILED' if identifier == 'attn_fraction' else 'NOT_EXECUTED',
                     'neural_predictor_invoked': False, 'raw_latex': None, 'exact': None, 'formatting_normalized': None,
                     'syntax_render': None, 'formula_core_structural_fidelity': None, 'full_output_correct': None,
                     'fractions_radicals': None, 'scripts': None, 'summation_limits': None,
                     'named_identifier_grouping': None, 'vector_scalar_typography': None, 'extraneous_prose': None,
                     'reason': 'No model prediction exists; initialization failure/unexecuted target is not mathematical incorrectness'})
    result = {'schema_version': 'pp-isolated-results.1', 'comparison_status': 'INDETERMINATE', 'selected_denominator': 8,
              'target_attempts': 1, 'initialization_failures': 1, 'neural_predictor_invocations': 0, 'completed_expressions': 0,
              'timeouts': 0, 'unexecuted_targets': 7, 'scoreable_predictions': 0,
              'exact_latex': {'numerator': None, 'selected_denominator': 8, 'scoreable_denominator': 0},
              'full_output_correctness': None, 'component_metrics': None, 'model_quality_winner': None,
              'gates': {'clean_isolation': 'PASS', 'paddleocr_import': 'PASS', 'tiny_paddle_cuda_probe': 'PASS',
                        'declared_base_dependency_resolution': 'PASS', 'formula_specific_dependency_closure': 'FAIL',
                        'predictor_construction': 'FAIL', 'recognition': 'NOT_EXECUTED', 'mathematical_quality': 'UNKNOWN'},
              'root_cause_note': 'paddleocr installs paddlex[ocr-core]; retained PaddleX metadata declares tokenizers>=0.19 under ocr/base and other extras, not ocr-core. The install plan omitted this model-specific optional dependency.',
              'environment_corrections_used': 1, 'further_installs_or_retries': 0, 'failure_measurements': failure,
              'baseline_codeformula': {'source': '../2026-11-16-t4-crops/results.json', 'preserved': True, 'rerun': False,
                                      'attempted': baseline['attempted'], 'returned': baseline['returned'], 'eos_returns': baseline['eos_returns'],
                                      'incomplete': baseline['incomplete_native_stop'], 'agent_full_expression': baseline['agent_full_expression'],
                                      'exact': baseline['exact'], 'tex_compile': baseline['tex_compile']},
              'reference_status': 'agent_visual_checked', 'independent_human_verifications': 0,
              'reference_discrepancy_preserved': '../2026-11-16-t4-crops/reference-discrepancies.json',
              'architectural_decision': 'No PP-versus-CodeFormula quality ranking. Neither recognizer is authoritative; retain original PDF evidence. No AST-readiness conclusion for PP without predictions.',
              'per_formula': rows}
    predictions = {'schema_version': 'pp-isolated-predictions.1', 'model': manifest['model'], 'formulas': rows,
                   'raw_failed_worker': json.loads((evidence / 'outputs/attn_fraction/prediction.json').read_text()),
                   'baseline_predictions_sha256': policy['preserved_codeformula_predictions_sha256'], 'references_uploaded': False}
    for name, data in [('results.json', result), ('predictions.json', predictions), ('first-failure.json', failure)]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    value = summarize(args.evidence, args.destination)
    print(json.dumps({k: value[k] for k in ['comparison_status', 'target_attempts', 'neural_predictor_invocations', 'unexecuted_targets', 'gates']}, indent=2))
