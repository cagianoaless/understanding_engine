"""Offline diagnostics/admission tests; no candidate imports, network or installs."""
import importlib.util
import json
from pathlib import Path
import stat
import struct

import pytest

ROOT=Path(__file__).parents[1]
HERE=ROOT/'evaluation/experiments/formula_recognition_v0/runs/2026-11-15-latency-pp-s'


def module(name):
    spec=importlib.util.spec_from_file_location('formula_pp_'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def central(name='package/file.py',flag=0,mode=stat.S_IFREG|0o644,size=9):
    n=name.encode();return struct.pack('<4s6H3I5H2I',b'PK\x01\x02',(3<<8)|20,20,flag,8,0,0,123,2,size,len(n),0,0,0,0,mode<<16,0)+n


def test_vendor_index_accepts_unquoted_and_quoted_attributes():
    m=module('wheel_metadata');html='<a href=https://paddle-whl.cdn.bcebos.com/a.whl>a</a><a href="https://files.pythonhosted.org/b.whl">b</a>'
    assert m.official_links(html)==['https://paddle-whl.cdn.bcebos.com/a.whl','https://files.pythonhosted.org/b.whl']


def test_central_metadata_size_and_identity():
    rows=module('wheel_metadata').central_records(central());assert rows[0]['name']=='package/file.py'
    assert rows[0]['compressed_bytes']==2 and rows[0]['uncompressed_bytes']==9 and rows[0]['crc32']==123


@pytest.mark.parametrize('name',['../escape','/absolute','x\\y'])
def test_unsafe_zip_paths_rejected(name):
    with pytest.raises(ValueError):module('wheel_metadata').central_records(central(name))


@pytest.mark.parametrize('body',[central()+central(),central(flag=1),central(mode=stat.S_IFLNK|0o777),central(size=0xffffffff),b'PK\x01'])
def test_bad_zip_metadata_rejected(body):
    with pytest.raises(ValueError):module('wheel_metadata').central_records(body)


def test_ignored_range_never_reads_large_payload(monkeypatch):
    m=module('wheel_metadata')
    class Response:
        status=200;headers={}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,*a):pytest.fail('Full payload was read')
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda *a,**k:Response())
    with pytest.raises(ValueError):m.read_range('https://files.pythonhosted.org/a.whl',0,10,100)


@pytest.mark.parametrize('url,start,end,total',[
    ('http://files.pythonhosted.org/a',0,1,20),('https://evil.test/a',0,1,20),
    ('https://user:pw@files.pythonhosted.org/a',0,1,20),('https://files.pythonhosted.org/a',-1,1,20),
    ('https://files.pythonhosted.org/a',0,20,20)])
def test_unapproved_ranges_fail_before_request(url,start,end,total):
    with pytest.raises(ValueError):module('wheel_metadata').read_range(url,start,end,total)


def test_partial_fit_never_claims_full_installation():
    m=module('report_data');part={'declared_unpacked_logical_bytes':1,'rounded_4KiB_file_estimate_bytes':4096}
    result=m.budget_plan({'allocated_bytes':0},[part],1)
    assert result['admission']=='UNKNOWN_FULL_CLOSURE_NOT_RESOLVED' and not result['complete_dependency_closure']
    assert not result['measured_installed_fit']


def test_core_storage_failure_without_summing_wheels_as_installed_bytes():
    m=module('report_data');part={'declared_unpacked_logical_bytes':796399322,'rounded_4KiB_file_estimate_bytes':817713152}
    result=m.budget_plan({'allocated_bytes':6724931584},[part],0,0)
    assert result['admission']=='FAIL' and result['logical_excess_before_remaining_dependencies_bytes']==5138138
    assert result['rounded_excess_before_remaining_dependencies_bytes']==26451968


def test_generation_start_is_not_evidence_of_decoding_or_quality():
    m=module('report_data');events=[{'event':'generate_start'}]
    assert m.progress_status(events)=='before_instrumented_top_level_forward_and_no_decode_evidence'
    events.append({'event':'forward_start'});assert m.progress_status(events)=='forward_entered_without_observed_token_emission'
    events.append({'event':'tokens_observed','tokens':3});assert 'not full-formula correctness' in m.progress_status(events)


def test_256_guard_is_before_any_docker_call(tmp_path):
    m=module('diagnose');r=object.__new__(m.Run);r.raw=tmp_path;(tmp_path/'max64').mkdir()
    (tmp_path/'max64/execution.json').write_text(json.dumps({'status':'FAILED','returned':False}))
    r.capture=lambda *a,**k:pytest.fail('Docker called despite failed first diagnostic')
    with pytest.raises(AssertionError,match='did not return'):r.invoke(256)
    assert not (tmp_path/'max256.started.json').exists()


def test_parent_selection_and_reference_remain_frozen():
    import hashlib
    parent=HERE.parents[1];f=json.loads((parent/'freeze.json').read_text())
    for name in ['selection.json','references.json']:
        assert hashlib.sha256((parent/name).read_bytes()).hexdigest()==f['files_sha256'][name]
