"""Offline policy/launcher checks; never import or execute the neural candidate."""

import json
from pathlib import Path
import runpy

import pytest


ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'evaluation/experiments/006b/runs/2026-11-10-one-page-smoke'
m=runpy.run_path(str(RUN/'control.py'))


def test_prospective_cap_does_not_rewrite_previous_policy():
    assert m['POLICY']['installed_cache_cap_bytes']==6442450944
    previous=json.loads((RUN.parent/'2026-11-09-cpu-packaging/policy.json').read_text())
    assert previous['installed_cache_cap_bytes']==4294967296
    assert m['POLICY']['maximum_inference_invocations']==1
    assert not m['POLICY']['benchmark_authorized']


@pytest.mark.parametrize('available,allocated,pending',[
    (20*1024**3-1,0,0),
    (30*1024**3,6*1024**3-m['MARGIN']+1,0),
    (20*1024**3+100,0,101),
    (30*1024**3,6*1024**3-m['MARGIN']-100,101),
])
def test_preventive_resource_admission(available,allocated,pending):
    with pytest.raises(RuntimeError,match='STOP'):
        m['limits']({'host_available_bytes':available,'allocated_bytes':allocated},pending)


def test_unprivileged_networkless_memory_swap_flags():
    args=m['restricted_args']()
    assert args[args.index('--memory')+1]=='4294967296'
    assert args[args.index('--memory-swap')+1]=='4294967296'
    assert args[args.index('--network')+1]=='none'
    assert args[args.index('--user')+1]=='65534:65534'
    assert '--read-only' in args and '--privileged' not in args
    assert args[args.index('--cap-drop')+1]=='ALL'


def test_environment_is_offline_and_cpu_threads_bounded():
    args=m['candidate_env'](); values=dict(args[i+1].split('=',1) for i in range(0,len(args),2))
    assert values['HF_HUB_OFFLINE']==values['TRANSFORMERS_OFFLINE']=='1'
    assert values['OMP_NUM_THREADS']==values['RAYON_NUM_THREADS']=='4'
    assert values['CUDA_VISIBLE_DEVICES']==''
    assert values['PYTHONDONTWRITEBYTECODE']=='1'


def test_selection_is_one_previously_frozen_page():
    selection=json.loads((RUN/'selection.json').read_text())
    old=json.loads((ROOT/'evaluation/experiments/006b/selection.json').read_text())
    assert selection['page_range']==[6,6]
    assert selection['page_number_one_based'] in old['selected'][selection['document_id']]
    assert selection['independent_human_verifications']==0


@pytest.mark.parametrize('field,value',[
    ('memory.max','max'),('memory.max','4294967297'),('memory.swap.max','1'),
    ('cpu.max','max 100000'),('cpu.max','500000 100000'),
])
def test_actual_cgroup_values_reject_unbounded_or_excess_resources(field,value):
    page=runpy.run_path(str(RUN/'smoke_page.py'))
    values={'memory.max':'4294967296','memory.swap.max':'0','cpu.max':'400000 100000'}
    values[field]=value
    with pytest.raises((AssertionError,ValueError)):page['assert_cgroup'](values)


def test_second_page_or_second_prediction_is_rejected_before_model_call():
    from types import SimpleNamespace
    page=runpy.run_path(str(RUN/'smoke_page.py'));seen=[]
    valid=SimpleNamespace(metadata={'page_no':6},image=SimpleNamespace(size=(612,792)))
    page['single_batch']([valid],seen)
    with pytest.raises(AssertionError):page['single_batch']([valid],seen)
    invalid=SimpleNamespace(metadata={'page_no':9},image=valid.image)
    with pytest.raises(AssertionError):page['single_batch']([invalid],[])
    with pytest.raises(AssertionError):page['single_batch']([valid,valid],[])


@pytest.mark.parametrize('url',[
    'http://huggingface.co/x','https://user:secret@huggingface.co/x',
    'https://huggingface.co.example/x','https://example.com/x','file:///tmp/a',
])
def test_model_redirect_does_not_expand_to_untrusted_or_credentialed_origins(url):
    host=runpy.run_path(str(RUN/'one_page.py'))
    assert not host['model_redirect_allowed'](url)
