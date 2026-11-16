"""Offline safeguards; no GPU, SSH, downloads or model imports."""
import importlib.util
import json
import os
from pathlib import Path

import pytest


RUN = Path(__file__).resolve().parents[1] / 'evaluation/experiments/formula_recognition_v0/runs/2026-11-16-pp-research-server'


def load(name):
    spec = importlib.util.spec_from_file_location('server_' + name, RUN / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owned(tmp_path):
    root = tmp_path.resolve() / 'understanding-engine-pp-test'
    root.mkdir(mode=0o700)
    st = root.stat()
    expected = dict(root=str(root), run_id='test', uid=os.getuid(), device=st.st_dev, inode=st.st_ino)
    (root / '.experiment-owner.json').write_text(json.dumps(expected))
    return root, expected


def test_exact_owned_identity_required(tmp_path):
    cleanup = load('cleanup')
    root, expected = owned(tmp_path)
    assert cleanup.validate(root, expected)
    for key, value in [('inode', 0), ('uid', -1), ('run_id', 'wrong')]:
        with pytest.raises(AssertionError):
            cleanup.validate(root, dict(expected, **{key: value}))


def test_symlink_root_and_changed_marker_rejected(tmp_path):
    cleanup = load('cleanup')
    root, expected = owned(tmp_path)
    alias = tmp_path / 'alias'
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(AssertionError):
        cleanup.validate(alias, expected)
    (root / '.experiment-owner.json').write_text('{}')
    with pytest.raises((AssertionError, KeyError)):
        cleanup.validate(root, expected)


def test_descriptor_traversal_preserves_external_symlink_target(tmp_path):
    cleanup = load('cleanup')
    root, expected = owned(tmp_path)
    external = tmp_path / 'protected'
    external.mkdir()
    (external / 'keep').write_text('original')
    (root / 'link').symlink_to(external, target_is_directory=True)
    (root / 'nested').mkdir()
    (root / 'nested/file').write_text('owned')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        assert cleanup.inspect_tree(fd, os.getuid(), expected['device'])['symlinks'] == 1
        cleanup.remove_contents(fd, os.getuid(), expected['device'])
    finally:
        os.close(fd)
    assert not list(root.iterdir())
    assert (external / 'keep').read_text() == 'original'


def test_cleanup_requires_verified_local_download(tmp_path):
    cleanup = load('cleanup')
    root, expected = owned(tmp_path)
    (root / 'download-verified.json').write_text(json.dumps({'local_archive_sha256': 'wrong', 'archive_and_members_verified': True}))
    with pytest.raises(AssertionError):
        cleanup.cleanup(root, expected, 'expected')
    assert root.is_dir()


def test_export_excludes_weights_and_runtime(tmp_path):
    package = load('package')
    root = tmp_path.resolve()
    (root / 'model').mkdir()
    for name in ['inference.json', 'inference.yml']:
        (root / 'model' / name).write_text('{}')
    (root / 'model/inference.pdiparams').write_bytes(b'secret weights')
    (root / 'runtime').mkdir()
    (root / 'runtime/private').write_text('exclude')
    package.package(root, 'named-results.zip')
    import zipfile
    assert (root / 'named-results.summary.json').exists()
    with zipfile.ZipFile(root / 'named-results.zip') as archive:
        assert set(archive.namelist()) == {'model/inference.json', 'model/inference.yml', 'archive-members.json'}


def test_export_rejects_oversize_before_writing_archive(tmp_path, monkeypatch):
    package = load('package')
    root = tmp_path.resolve()
    (root / 'model').mkdir()
    for name in ['inference.json', 'inference.yml']:
        (root / 'model' / name).write_text('{}')
    monkeypatch.setattr(package, 'MAX_FILE', 1)
    with pytest.raises(AssertionError):
        package.package(root)
    assert not (root / 'results.zip').exists()


def test_archive_members_verified_before_extracting(tmp_path):
    import hashlib
    import zipfile
    verify = load('verify_archive')
    archive = tmp_path / 'test.zip'
    data = b'raw prediction'
    rows = [{'file': 'outputs/result.json', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr(rows[0]['file'], data)
        stream.writestr('archive-members.json', json.dumps(rows))
    summary = {'bytes': archive.stat().st_size, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'members': 1}
    ack = verify.verify(archive, summary, tmp_path / 'verified')
    assert ack['archive_and_members_verified'] is True
    assert (tmp_path / 'verified/outputs/result.json').read_bytes() == data
    with pytest.raises(AssertionError):
        verify.verify(archive, dict(summary, sha256='wrong'), tmp_path / 'wrong')
    assert not (tmp_path / 'wrong').exists()


def test_zip_traversal_rejected_before_extraction(tmp_path):
    import hashlib
    import zipfile
    verify = load('verify_archive')
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('../escape', 'bad')
    summary = {'bytes': archive.stat().st_size, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    with pytest.raises(AssertionError):
        verify.verify(archive, summary, tmp_path / 'destination')
    assert not (tmp_path / 'destination').exists() and not (tmp_path.parent / 'escape').exists()


def test_all_cache_destinations_inside_owned_root(tmp_path):
    isolate = load('isolate')
    root, _ = owned(tmp_path)
    env = isolate.environment(root)
    for key in ['HOME', 'XDG_CACHE_HOME', 'HF_HOME', 'MODELSCOPE_CACHE', 'PADDLE_PDX_CACHE_HOME', 'PIP_CACHE_DIR', 'UV_CACHE_DIR', 'TMPDIR', 'PYTHONPYCACHEPREFIX', 'CUDA_CACHE_PATH']:
        assert Path(env[key]).is_relative_to(root)
    assert env['UV_PYTHON_DOWNLOADS'] == 'never'
    assert env['OMP_NUM_THREADS'] == '4'


def test_frozen_inputs_match_prior_eight_crops():
    now = json.loads((RUN / 'inputs.json').read_text())
    prior = json.loads((RUN.parent / '2026-11-16-pp-isolated/inputs.json').read_text())
    assert now['crops'] == prior['crops']
    assert now['recognition_configuration'] == prior['recognition_configuration']
    assert now['reference_inputs_uploaded'] is False
    assert len(now['execution_order']) == 8 and now['execution_order'][0] == 'attn_fraction'


def test_real_results_keep_failures_and_eight_image_denominator():
    result = json.loads((RUN / 'results.json').read_text())
    predictions = json.loads((RUN / 'predictions.json').read_text())['formulas']
    assert len(predictions) == result['selected_denominator'] == 8
    assert result['neural_invocations_total'] == 9  # failed ftfy attempt retained
    assert result['returned'] == 8
    assert result['pp_full_expression'] == {'correct': 4, 'incorrect': 4, 'unknown': 0, 'selected_denominator': 8}
    assert result['component_counts']['reference_conflict']['unscoreable'] == 1
    assert result['component_counts']['fraction_membership']['missing'] == 2
    assert result['codeformula_component_counts_preserved']['fraction_membership']['correct'] == 4
    assert not result['codeformula_rerun']
    assert result['independent_human_verifications'] == 0


def test_component_totals_derive_from_explicit_review():
    from collections import Counter
    review = json.loads((RUN / 'adjudications.json').read_text())
    results = json.loads((RUN / 'results.json').read_text())
    for category, counts in results['component_counts'].items():
        observed = Counter(c['decision'] for e in review['expressions'] for c in e['component_decisions'].get(category, []))
        assert sum(observed.values()) == counts['reference_denominator']
        for name in ['correct', 'incorrect', 'missing', 'ambiguous', 'unscoreable']:
            assert counts[name] == observed[name]


def test_source_review_and_exact_spelling_remain_separate():
    import hashlib
    result = json.loads((RUN / 'results.json').read_text())
    references = RUN.parents[1] / 'references.json'
    assert hashlib.sha256(references.read_bytes()).hexdigest() == result['references_sha256']
    assert result['exact']['correct'] == result['formatting_normalized']['correct'] == 0
    assert result['pp_full_expression']['correct'] == 4
    for name, key in [('predictions.json', 'baseline_predictions_sha256'), ('results.json', 'baseline_results_sha256')]:
        assert hashlib.sha256((RUN.parent / '2026-11-16-t4-crops' / name).read_bytes()).hexdigest() == result[key]


def test_download_and_cleanup_are_explicitly_verified():
    receipt = json.loads((RUN / 'cleanup.json').read_text())
    evidence = json.loads((RUN / 'external-evidence.json').read_text())
    runtime = json.loads((RUN / 'runtime.json').read_text())
    assert evidence['archive_and_every_member_verified'] is True
    assert receipt['removed'] and receipt['identity_verified'] and receipt['owner_verified']
    assert receipt['remaining_owned_files'] == 0 and not receipt['open_process_references']
    assert receipt['independent_verification']['directory_absent']
    assert runtime['packages']['ftfy'] == '6.3.1' and runtime['packages']['tokenizers'] == '0.23.3'
    assert runtime['exception_user_authorized'] and not runtime['torch_visible']
