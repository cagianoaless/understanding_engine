"""Model-free safety regressions; never load or import the neural candidate."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).parents[1]
HERE=ROOT/'evaluation/experiments/formula_recognition_v0/runs/2026-11-15-cpu-recognition'


def load(name):
    spec=importlib.util.spec_from_file_location('formula_execution_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.fixture
def control():return load('control')


def test_amendment_preserves_previous_protocol():
    previous=json.loads((HERE.parents[1]/'protocol.json').read_text());new=json.loads((HERE/'amendment.json').read_text())
    assert previous['installed_cache_cap_bytes']==6*1024**3 and previous['host_reserve_bytes']==20*1024**3
    assert new['installed_cache_cap_bytes']==7*1024**3 and new['host_reserve_bytes']==12*1024**3
    assert new['container_memory_bytes']==previous['container_memory_bytes']==4*1024**3
    assert new['seconds_per_invocation']==previous['timeout_seconds_per_page']==120
    assert new['stop_additional_inference_if_first_fails']


def test_prospective_admission_and_pending_bytes(control):
    s=dict(host_available_bytes=17*1024**3,allocated_bytes=5400000000)
    control.limits(s,2*639797175)
    with pytest.raises(RuntimeError):control.limits(s,2*1024**3)
    with pytest.raises(RuntimeError):control.limits(dict(host_available_bytes=12*1024**3-1,allocated_bytes=0))


@pytest.mark.parametrize('url,allowed',[
    ('https://huggingface.co/model',True),('https://cas-bridge.xethub.hf.co/x?signature=example',True),
    ('http://huggingface.co/x',False),('https://evil-huggingface.co/x',False),
    ('https://huggingface.co.evil.test/x',False),('https://user:password@huggingface.co/x',False)])
def test_redirect_boundaries(control,url,allowed):assert control.redirect_allowed(url)==allowed


@pytest.mark.parametrize('damage',['memory','swap','quota','unlimited','zero_quota','affinity'])
def test_worker_rejects_weakened_cgroups(monkeypatch,damage):
    worker=load('worker');values={'memory.max':str(4*1024**3),'memory.swap.max':'0','cpu.max':'400000 100000'}
    monkeypatch.setattr(worker.os,'sched_getaffinity',lambda p:set(range(5 if damage=='affinity' else 4)),raising=False)
    monkeypatch.setattr(worker.Path,'exists',lambda p:False)
    if damage=='memory':values['memory.max']=str(4*1024**3+1)
    elif damage=='swap':values['memory.swap.max']='1'
    elif damage=='quota':values['cpu.max']='400001 100000'
    elif damage=='unlimited':values['cpu.max']='max 100000'
    elif damage=='zero_quota':values['cpu.max']='0 100000'
    with pytest.raises(AssertionError):worker.verify_limits(values)


def test_worker_accepts_exact_limits(monkeypatch):
    worker=load('worker');monkeypatch.setattr(worker.os,'sched_getaffinity',lambda p:{0,1,2,3},raising=False);monkeypatch.setattr(worker.Path,'exists',lambda p:False)
    worker.verify_limits({'memory.max':str(4*1024**3),'memory.swap.max':'0','cpu.max':'400000 100000'})


def test_no_additional_invocation_after_first_failure(control,tmp_path):
    run=object.__new__(control.Run);run.raw=tmp_path;run.prefix='owned';(tmp_path/'tasks').mkdir();(tmp_path/'tasks/crop-log_eq2.json').write_text('{}')
    p=tmp_path/'native/crop-attn_fraction';p.mkdir(parents=True);(p/'execution.json').write_text(json.dumps(dict(status='FAILED',generate_calls=[])))
    run.capture=lambda *a,**k:pytest.fail('Docker called after failed first invocation')
    with pytest.raises(AssertionError,match='First actual model invocation failed'):run.invocation('crop-log_eq2')


def test_parent_reference_and_selection_hashes_unchanged():
    folder=HERE.parents[1];freeze=json.loads((folder/'freeze.json').read_text())
    for name in ['selection.json','references.json','model-inventory.json']:
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==freeze['files_sha256'][name]


def test_component_comparison_exposes_wrong_fraction_and_script():
    scorer=load('scoring');result=scorer.compare(r'\frac{x_i}{\sqrt{y}}',r'\frac{x^i}{y}')
    assert result['components']['fractions']['correct']==0
    assert result['components']['subscripts']['missing']==1
    assert result['components']['superscripts']['incorrect_proposals']==1
    assert result['components']['radicals']['missing']==1
    assert result['complete_expression_correct'] is None


def test_component_parse_is_separate_from_frozen_string_normalization():
    scorer=load('scoring');a=scorer.compare(r'\frac{1}{2}',r'\frac12')
    assert a['exact'] is False and a['formatting_normalized'] is False
    assert a['components']['fractions']['correct']==1
    assert scorer.compare('x', '\r\nx\r\n')['formatting_normalized']
    assert not scorer.compare('x_i','x^i')['formatting_normalized']


def test_summation_limits_and_unexecuted_not_success():
    scorer=load('scoring');a=scorer.compare(r'\sum_{j=1}^{M}x_j',r'\sum_j x_j')
    assert a['components']['summation_limits']['missing']==1
    assert scorer.compare('x',None)['components'] is None
    assert scorer.relationships(r'\frac{x}')['features'] is None


@pytest.mark.parametrize('status,header,start,total,valid',[
    (206,'bytes 10-19/20',10,20,True),(200,None,10,20,False),
    (206,'bytes 0-19/20',10,20,False),(200,None,0,20,True)])
def test_range_continuation_never_replaces_a_partial(monkeypatch,control,status,header,start,total,valid):
    import sys
    monkeypatch.setitem(sys.modules,'control',control);helper=load('complete_transfer')
    if valid:helper.validate_range(status,header,start,total)
    else:
        with pytest.raises(ValueError):helper.validate_range(status,header,start,total)


@pytest.mark.parametrize('returned_generation',[False,True])
def test_timeout_summary_keeps_denominators_without_fabricating_quality(monkeypatch,control,tmp_path,returned_generation):
    import sys
    monkeypatch.setitem(sys.modules,'control',control);monkeypatch.setitem(sys.modules,'scoring',load('scoring'));summary=load('summarize')
    folder=HERE.parents[1];raw=tmp_path/'raw';native=raw/'native/crop-attn_fraction';native.mkdir(parents=True)
    def write(path,data):path.write_text(json.dumps(data))
    write(raw/'prediction-code-freeze.json',dict(selection_sha256=control.sha(folder/'selection.json'),references_sha256=control.sha(folder/'references.json'),
        code_sha256={n:control.sha(HERE/n) for n in ['worker.py','control.py','scoring.py','complete_transfer.py']}))
    write(raw/'crop-attn_fraction.complete.json',dict(resource=dict(timeout=True,external_wall_seconds=120.3),state=dict(ExitCode=137,Running=False,OOMKilled=False),host_config={}))
    events=[dict(event='model_initialization_success',elapsed=1,seconds=.5),dict(event='predictor_start',elapsed=1),dict(event='generate_start',elapsed=1)]
    if returned_generation:events.append(dict(event='generate_success',elapsed=100))
    (native/'events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in events))
    sample={'elapsed':120,'memory.peak':'1024','memory.events':'oom 0\noom_kill 0','cpu.stat':'usage_usec 300000000',
            'memory.max':str(4*1024**3),'memory.swap.max':'0','cpu.max':'400000 100000'}
    (native/'cgroup-samples.jsonl').write_text(json.dumps(sample)+'\n');write(native/'formula-options.json',{})
    write(raw/'model-manifest.json',[]);selection=json.loads((folder/'selection.json').read_text())['expressions']
    write(raw/'crops-frozen.json',dict(crops=[dict(id=r['id']) for r in selection]))
    if returned_generation:
        with pytest.raises(AssertionError):summary.collect(raw,tmp_path/'out')
    else:
        summary.collect(raw,tmp_path/'out');result=json.loads((tmp_path/'out/results.json').read_text())
        assert result['selected_targets']==8 and result['crop_attempted']==1 and result['crop_unexecuted']==7
        assert result['crop_timeout']==1 and result['crop_completed']==0
        assert result['mathematical_accuracy'] is None and result['quality_scoreable_predictions']==0
        assert all(v['component_correctness'] is None for v in result['expressions'])
