"""Offline integrity and sequencing checks; no Paddle/remote inference imports."""
import hashlib
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-pp-isolated'
WORKER = runpy.run_path(str(HERE / 'pp_worker.py'))
CONTROL = runpy.run_path(str(HERE / 'pp_control.py'))


def fixture(root):
    crop_root = root / 'crops'
    crop_root.mkdir()
    crop = crop_root / 'first.png'
    crop.write_bytes(b'exact synthetic image bytes')
    def metadata(path):
        return {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    model = root / 'model'
    model.mkdir()
    files = []
    for name in ['inference.json', 'inference.yml', 'inference.pdiparams']:
        path = model / name
        path.write_bytes(('fixture ' + name).encode())
        files.append({'file': name, **metadata(path)})
    manifest = {'reference_inputs_uploaded': False, 'crops': [{'id': 'first', **metadata(crop)}], 'model': {'repo': 'PaddlePaddle/PP-FormulaNet-S', 'revision': '0572450e501be9eb1b1cdb7e00fccf4b22fab4df', 'files': [{'file': r['file'], 'bytes': r['bytes'], 'expected_sha256': r['sha256']} for r in files]}}
    (root / 'inputs.json').write_text(json.dumps(manifest))
    (root / 'model-acquisition.json').write_text(json.dumps({'revision': manifest['model']['revision'], 'files': files}))
    return crop_root, manifest


def test_frozen_same_eight_crops():
    value = json.loads((HERE / 'inputs.json').read_text())
    old = json.loads((HERE.parent / '2026-11-16-t4-crops/inference-inputs.json').read_text())
    assert value['crops'] == old['crops']
    assert value['execution_order'] == old['execution_order']
    assert value['execution_order'][0] == 'attn_fraction'
    assert len(value['crops']) == 8
    assert value['reference_inputs_uploaded'] is False
    assert 'latex' not in json.dumps(value).lower()
    assert value['recognition_configuration']['model_name'] == 'PP-FormulaNet-S'


def test_frozen_code_and_baseline_identity():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    for name, digest in protocol['inference_code_sha256'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    for path, digest in protocol['frozen_files_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    baseline = HERE.parent / '2026-11-16-t4-crops'
    assert hashlib.sha256((baseline / 'predictions.json').read_bytes()).hexdigest() == protocol['preserved_codeformula_predictions_sha256']
    assert protocol['environment_corrections_allowed'] == 1
    assert protocol['library_path_hacks'] is False


def test_exact_artifact_integrity(tmp_path):
    crops, expected = fixture(tmp_path)
    manifest, row, path = WORKER['verify'](tmp_path, crops, 'first')
    assert manifest == expected and path.name == 'first.png'
    assert row['id'] == 'first'


@pytest.mark.parametrize('corruption', ['crop', 'model', 'hash', 'revision', 'reference'])
def test_integrity_rejection(tmp_path, corruption):
    crops, manifest = fixture(tmp_path)
    if corruption == 'crop':
        (crops / 'first.png').write_bytes(b'changed')
    elif corruption == 'model':
        (tmp_path / 'model/inference.yml').write_bytes(b'wrong')
    elif corruption == 'hash':
        manifest['model']['files'][-1]['expected_sha256'] = '0' * 64
    elif corruption == 'revision':
        manifest['model']['revision'] = 'main'
    else:
        manifest['reference_inputs_uploaded'] = True
    (tmp_path / 'inputs.json').write_text(json.dumps(manifest))
    with pytest.raises(AssertionError):
        WORKER['verify'](tmp_path, crops, 'first')


@pytest.mark.parametrize('failed,timeout,expected', [(0, False, True), (1, False, False), (0, True, False)])
def test_prior_failure_blocks_continuation(tmp_path, failed, timeout, expected):
    (tmp_path / 'first').mkdir()
    (tmp_path / 'first/prediction.json').write_text(json.dumps({'status': 'RETURNED', 'raw_latex': 'x'}))
    (tmp_path / 'first.resource.json').write_text(json.dumps({'exit_code': failed, 'timed_out': timeout}))
    assert CONTROL['prior_success'](tmp_path, 'first') is expected


def test_second_before_first_does_not_launch(tmp_path):
    (tmp_path / 'inputs.json').write_text(json.dumps({'execution_order': ['first', 'second']}))
    (tmp_path / 'setup-result.json').write_text(json.dumps({'status': 'PASS'}))
    with pytest.raises(FileNotFoundError):
        CONTROL['execute'](tmp_path, tmp_path, 'second')
    assert not (tmp_path / 'outputs/second.started.json').exists()


def test_unregistered_input_rejected(tmp_path):
    (tmp_path / 'inputs.json').write_text(json.dumps({'execution_order': ['first']}))
    with pytest.raises(ValueError):
        CONTROL['execute'](tmp_path, tmp_path, 'another')


def test_no_reference_loader_or_library_path_override():
    for name in ['pp_worker.py', 'pp_control.py', 'setup_clean.py', 'acquire.py']:
        source = (HERE / name).read_text()
        assert 'references.json' not in source
        assert 'LD_LIBRARY_PATH=' not in source
        assert "['LD_LIBRARY_PATH'] =" not in source
    setup = (HERE / 'setup_clean.py').read_text()
    assert 'include-system-site-packages = false' in setup
    assert 'find_spec("torch") is None' in setup
    assert '--only-binary=:all:' in setup

SUMMARIZE = runpy.run_path(str(HERE / 'summarize.py'))


def failure_fixture(root, include_forward=False):
    worker = json.loads((HERE / 'predictions.json').read_text())['raw_failed_worker']
    native = root / 'outputs/attn_fraction'
    native.mkdir(parents=True)
    (native / 'prediction.json').write_text(json.dumps(worker))
    events = [{'event': 'model_initialization_start', 'elapsed': 1}, {'event': 'failed', 'elapsed': 2}]
    if include_forward:
        events.append({'event': 'predictor_invoked', 'elapsed': 1.5})
    (native / 'events.jsonl').write_text('\n'.join(json.dumps(r) for r in events))
    resource = {'exit_code': 1, 'timed_out': False, 'process_cleanup_verified': True, 'wall_seconds': 3, 'sampled_process_gpu_peak_bytes': 100}
    (native.parent / 'attn_fraction.resource.json').write_text(json.dumps(resource))
    return root


def test_allocation_does_not_prove_neural_execution(tmp_path):
    evidence = failure_fixture(tmp_path)
    value = SUMMARIZE['classify'](evidence)
    assert value['neural_predictor_invoked'] is False
    assert value['recognition_seconds'] is None
    assert value['successful_initialization_seconds'] is None
    assert value['failure_phase'] == 'PREDICTOR_CONSTRUCTION'


def test_forward_event_cannot_be_reported_as_initialization_only(tmp_path):
    evidence = failure_fixture(tmp_path, include_forward=True)
    with pytest.raises(AssertionError):
        SUMMARIZE['classify'](evidence)


def test_failure_summary_preserves_denominator_nulls_and_baseline(tmp_path):
    evidence = failure_fixture(tmp_path / 'native')
    for name, data in [
        ('setup-result.json', {'status': 'PASS', 'environment_corrections': 1}),
        ('codeformula-final.json', {'unchanged': True}),
        ('completion.json', {'attempted': ['attn_fraction'], 'returned': []}),
    ]:
        (evidence / name).write_text(json.dumps(data))
    for target in ['one', 'two']:
        result = SUMMARIZE['summarize'](evidence, tmp_path / target)
        assert result['selected_denominator'] == 8
        assert result['neural_predictor_invocations'] == 0
        assert result['scoreable_predictions'] == 0
        assert result['exact_latex']['numerator'] is None
        assert result['model_quality_winner'] is None
        assert result['gates']['clean_isolation'] == 'PASS'
        assert result['gates']['formula_specific_dependency_closure'] == 'FAIL'
        assert all(row['full_output_correct'] is None for row in result['per_formula'])
    assert (tmp_path / 'one/results.json').read_bytes() == (tmp_path / 'two/results.json').read_bytes()
