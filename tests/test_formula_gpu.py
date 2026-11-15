"""Model-free guards for the isolated GPU crop experiment."""
import hashlib
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-t4-crops'
WORKER = runpy.run_path(str(HERE / 'gpu_worker.py'))
CONTROL = runpy.run_path(str(HERE / 'gpu_control.py'))


def fixture(root):
    (root / 'crops').mkdir()
    (root / 'crops/a.png').write_bytes(b'not decoded by integrity check')
    model = root / 'artifacts/docling-project--CodeFormulaV2'
    model.mkdir(parents=True)
    (model / 'weights').write_bytes(b'test fixture, no neural weights')
    def row(path):
        return {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    value = {'reference_inputs_uploaded': False, 'model': {'revision': WORKER['REVISION'], 'files': [{'file': 'weights', **row(model / 'weights')}]}, 'crops': [{'id': 'a', **row(root / 'crops/a.png')}]}
    (root / 'inference-inputs.json').write_text(json.dumps(value))
    return value


def test_verified_frozen_manifest():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    for path, expected in protocol['frozen_files'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    for name, expected in protocol['inference_code'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected


def test_eight_original_crops_no_reference_text():
    value = json.loads((HERE / 'inference-inputs.json').read_text())
    original = json.loads((ROOT / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-15-cpu-recognition/crops-frozen.json').read_text())
    assert value['crops'] == original['crops']
    assert len(value['execution_order']) == 8
    assert value['execution_order'][0] == 'attn_fraction'
    assert set(value['execution_order']) == {r['id'] for r in value['crops']}
    assert 'latex' not in json.dumps(value).lower()
    assert value['reference_inputs_uploaded'] is False


def test_integrity_success(tmp_path):
    expected = fixture(tmp_path)
    row, crop = WORKER['verify_inputs'](tmp_path, 'a')
    assert row == expected['crops'][0]
    assert crop.name == 'a.png'


@pytest.mark.parametrize('corruption', ['crop', 'weights', 'revision', 'references', 'length'])
def test_fail_closed_integrity(tmp_path, corruption):
    value = fixture(tmp_path)
    if corruption == 'crop':
        (tmp_path / 'crops/a.png').write_bytes(b'wrong crop')
    elif corruption == 'weights':
        (tmp_path / 'artifacts/docling-project--CodeFormulaV2/weights').write_bytes(b'wrong')
    elif corruption == 'revision':
        value['model']['revision'] = 'main'
    elif corruption == 'references':
        value['reference_inputs_uploaded'] = True
    else:
        value['crops'][0]['bytes'] += 1
    (tmp_path / 'inference-inputs.json').write_text(json.dumps(value))
    with pytest.raises(AssertionError):
        WORKER['verify_inputs'](tmp_path, 'a')


def test_unknown_crop_rejected(tmp_path):
    fixture(tmp_path)
    with pytest.raises(StopIteration):
        WORKER['verify_inputs'](tmp_path, 'unregistered')


@pytest.mark.parametrize('identifier,phase', [('a', 'tuned'), ('not-selected', 'primary')])
def test_control_rejects_unfrozen_requests(tmp_path, identifier, phase):
    (tmp_path / 'inference-inputs.json').write_text(json.dumps({'execution_order': ['a']}))
    with pytest.raises(ValueError):
        CONTROL['execute'](tmp_path, identifier, phase)
    assert not (tmp_path / 'outputs').exists()


def test_existing_marker_prevents_repeat(tmp_path):
    (tmp_path / 'inference-inputs.json').write_text(json.dumps({'execution_order': ['a']}))
    output = tmp_path / 'outputs/primary'
    output.mkdir(parents=True)
    (output / 'a.started.json').write_text('{}')
    with pytest.raises(FileExistsError):
        CONTROL['execute'](tmp_path, 'a')


def test_inference_scripts_have_no_reference_loader():
    for name in ['gpu_worker.py', 'gpu_control.py', 'acquire_model.py']:
        value = (HERE / name).read_text()
        assert 'references.json' not in value
        assert 'scoring.py' not in value
    worker = (HERE / 'gpu_worker.py').read_text()
    assert "torch_dtype='float16'" in worker
    assert "cfg.do_sample is False" in worker
    assert 'backend_fallback_possible=False' in worker

EVALUATE = runpy.run_path(str(HERE / 'evaluate.py'))


@pytest.mark.parametrize('stop,last,cap,expected', [
    ('unspecified', 42, False, 'EOS_RETURNED'),
    ('stop_sequence', 7, False, 'INCOMPLETE_NATIVE_REPETITION_STOP'),
    ('unspecified', 7, True, 'INCOMPLETE_TOKEN_LIMIT'),
    ('unspecified', 7, False, 'UNRESOLVED_TERMINATION'),
])
def test_termination_does_not_invent_completion(stop, last, cap, expected):
    prediction = {'generated_calls': [{'token_cap_reached': cap, 'last_token_id': last, 'eos_token_id': 42}], 'native_output': {'stop_reason': stop}}
    assert EVALUATE['termination'](prediction) == expected


def test_no_generation_distinct_from_incorrect_formula():
    assert EVALUATE['termination']({'generated_calls': []}) == 'NO_GENERATION'


def test_published_denominators_and_incomplete_status():
    value = json.loads((HERE / 'results.json').read_text())
    assert value['selected_denominator'] == value['attempted'] == value['returned'] == 8
    assert value['eos_returns'] + value['incomplete_native_stop'] == 8
    row = next(v for v in value['per_formula'] if v['id'] == 'log_eq2')
    assert row['agent_source_review']['full_expression_correct'] is None
    assert row['termination'] == 'INCOMPLETE_NATIVE_REPETITION_STOP'
    assert value['pp_formulanet']['formula_invocations'] == 0
    assert value['model_quality_winner'] is None


def test_reference_discrepancy_not_silently_repaired():
    original = json.loads((ROOT / 'evaluation/experiments/formula_recognition_v0/references.json').read_text())
    row = next(r for r in original['expressions'] if r['id'] == 'nature_weights')
    assert 'a_{ij}' in row['latex']
    review = json.loads((HERE / 'adjudications.json').read_text())
    decision = next(r for r in review['expressions'] if r['id'] == 'nature_weights')
    assert decision['component_decisions']['reference_conflict'][0]['decision'] == 'unscoreable'
    assert review['independent_human_verifications'] == 0


def test_agent_core_counts_not_whole_output_accuracy():
    results = json.loads((HERE / 'results.json').read_text())
    assert results['component_counts']['fraction_membership']['denominator'] == 4
    assert 'core' in results['component_counts']['fraction_membership']['scope']
    assert results['agent_full_expression']['correct'] < results['selected_denominator']
    assert results['tex_compile']['semantic_validity_inferred'] is False


def test_offline_evaluation_repeatable_and_does_not_mutate_predictions(tmp_path):
    published = json.loads((HERE / 'predictions.json').read_text())
    result = json.loads((HERE / 'results.json').read_text())
    evidence = tmp_path / 'native'
    (evidence / 'outputs/primary').mkdir(parents=True)
    score_by_id = {r['id']: r for r in result['per_formula']}
    for row in published['codeformula']:
        folder = evidence / 'outputs/primary' / row['id']
        folder.mkdir()
        (folder / 'prediction.json').write_text(json.dumps(row))
        resource = {'timed_out': False, 'exit_code': 0, 'process_cleanup_verified': True, 'wall_seconds': score_by_id[row['id']]['external_wall_seconds']}
        (folder.parent / (row['id'] + '.resource.json')).write_text(json.dumps(resource))
    pp = tmp_path / 'pp'
    pp.mkdir()
    (pp / 'pp-outcome.json').write_text(json.dumps(result['pp_formulanet']))
    before = {p: p.read_bytes() for p in evidence.rglob('*.json')}
    for name in ['one', 'two']:
        EVALUATE['evaluate'](evidence, pp, HERE / 'render-results.json', tmp_path / name)
    assert (tmp_path / 'one/results.json').read_bytes() == (tmp_path / 'two/results.json').read_bytes()
    assert (tmp_path / 'one/predictions.json').read_bytes() == (tmp_path / 'two/predictions.json').read_bytes()
    assert all(p.read_bytes() == data for p, data in before.items())
