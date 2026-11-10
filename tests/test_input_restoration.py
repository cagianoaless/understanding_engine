"""Relevant offline verification only: identities, page bounds and redirects."""

import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'evaluation/experiments/006b/runs/2026-11-10-input-restoration/restore_inputs.py'))


def fixture_row(name='multi.pdf',pages=None):
    path=ROOT/'tests/fixtures'/name
    return path,{'pdf_bytes':path.stat().st_size,'pdf_sha256_verified':hashlib.sha256(path.read_bytes()).hexdigest(),'selected_pages':pages or [1,2]}


def test_frozen_registry_selected_pages_unchanged():
    rows=m['registry']()
    assert {r['document_id']:r['selected_pages'] for r in rows}=={'attention':[6,9],'bert':[6,10],'tabpfn_nature_2025':[15,19]}


def test_page_tree_only_verification():
    path,row=fixture_row();verified=m['verify_pdf'](path,row)
    assert verified['page_count']==2 and verified['all_selected_pages_exist']
    assert verified['actual_sha256']==row['pdf_sha256_verified']


def test_same_length_wrong_bytes_rejected_before_pdf_reader(tmp_path,monkeypatch):
    path,row=fixture_row();bad=tmp_path/'wrong.pdf';content=bytearray(path.read_bytes());content[-1]^=1;bad.write_bytes(content)
    with pytest.raises(m['VerificationError'],match='SHA-256'):
        m['verify_pdf'](bad,row)


def test_wrong_length_rejected(tmp_path):
    path,row=fixture_row();bad=tmp_path/'short.pdf';bad.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(m['VerificationError'],match='length'):m['verify_pdf'](bad,row)


def test_unavailable_selected_page_rejected():
    path,row=fixture_row(pages=[1,3])
    with pytest.raises(m['VerificationError'],match='page number'):m['verify_pdf'](path,row)


def test_symlink_not_accepted_as_original(tmp_path):
    path,row=fixture_row();alias=tmp_path/'alias.pdf';alias.symlink_to(path)
    with pytest.raises(m['VerificationError'],match='real PDF'):m['verify_pdf'](alias,row)


@pytest.mark.parametrize('url',[
    'https://arxiv.org/pdf/1810.04805v3','https://arxiv.org/pdf/1810.04805',
    'http://arxiv.org/pdf/1810.04805v2','https://evil.example/pdf/1810.04805v2',
    'https://user:secret@arxiv.org/pdf/1810.04805v2',
])
def test_bert_redirect_cannot_change_revision_or_authority(url):
    assert not m['redirect_allowed']('bert',url)


def test_exact_version_redirect_and_publisher_cdn():
    assert m['redirect_allowed']('bert','https://arxiv.org/pdf/1810.04805v2.pdf')
    assert m['redirect_allowed']('tabpfn_nature_2025','https://media.springernature.com/a.pdf')
    assert not m['redirect_allowed']('tabpfn_nature_2025','https://www.nature.com.example/a.pdf')
    assert m['redirect_allowed']('tabpfn_nature_2025','https://idp.nature.com/authorize')


def test_publisher_resume_cannot_ignore_pdf_hash_mismatch():
    base={'entries':[{'document_id':'attention','status':'ACCEPTED'},{'document_id':'bert','status':'ACCEPTED'},
        {'document_id':'tabpfn_nature_2025','status':'REJECTED','content_type':'text/html','reason':'Publisher Content-Length mismatch','verification_failure':{'actual_sha256':None}}]}
    m['allow_html_transport_resume'](base)
    base['entries'][-1]['content_type']='application/pdf'
    with pytest.raises(AssertionError):m['allow_html_transport_resume'](base)
    base['entries'][-1]['content_type']='text/html';base['entries'][-1]['verification_failure']['actual_sha256']='a'*64
    with pytest.raises(AssertionError):m['allow_html_transport_resume'](base)


def test_incomplete_mapping_is_not_input_ready(tmp_path):
    mapping=tmp_path/'mapping.json';mapping.write_text(json.dumps({'registry_sha256':m['REGISTRY_SHA256'],'entries':[]}))
    with pytest.raises(ValueError,match='incomplete'):m['verify_local'](mapping)
