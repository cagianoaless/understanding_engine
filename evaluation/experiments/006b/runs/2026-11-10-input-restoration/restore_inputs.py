"""Restore exact registered PDFs; byte/hash and page-tree checks only.

No text extraction, inference, scoring, runtime changes or source repair.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from pypdf import PdfReader


HERE=Path(__file__).resolve().parent
REGISTRY=HERE.parents[1]/'source-inputs.json'
REGISTRY_SHA256='4609502f6dcfae904f90be522d9a0ee1682b45eb7e515ac32ea9f3bc899a9469'
FILENAMES={'attention':'1706.03762v7.pdf','bert':'1810.04805v2.pdf','tabpfn_nature_2025':'s41586-024-08328-6.pdf'}
CAP=6442450944
RESERVE=21474836480
MARGIN=16*1024**2


class VerificationError(ValueError):
    def __init__(self,message,details):
        super().__init__(message)
        self.details=details


def registry():
    assert hashlib.sha256(REGISTRY.read_bytes()).hexdigest()==REGISTRY_SHA256,'Frozen registry changed'
    rows=json.loads(REGISTRY.read_text())
    selected=json.loads((REGISTRY.parent/'selection.json').read_text())['selected']
    assert {r['document_id'] for r in rows}==set(FILENAMES)
    assert all(r['selected_pages']==selected[r['document_id']] for r in rows)
    return rows


def verify_pdf(path,row):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise VerificationError('Not a real PDF file',{'path_type':'unacceptable'})
    actual=path.stat().st_size
    detail={'actual_bytes':actual,'expected_bytes':row['pdf_bytes'],'actual_sha256':None,
            'expected_sha256':row['pdf_sha256_verified']}
    if actual!=row['pdf_bytes']:
        raise VerificationError('Byte length mismatch',detail)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024**2),b''):h.update(data)
    detail['actual_sha256']=h.hexdigest()
    if h.hexdigest()!=row['pdf_sha256_verified']:
        raise VerificationError('SHA-256 mismatch',detail)
    with path.open('rb') as f:
        reader=PdfReader(f,strict=True)
        if reader.is_encrypted:raise VerificationError('Encrypted original cannot be page-verified',detail)
        count=len(reader.pages)
        pages=row['selected_pages']
        if not all(1<=p<=count for p in pages):
            raise VerificationError('Frozen page number outside original',dict(detail,page_count=count,selected_pages=pages))
        assert all(reader.pages[p-1].get('/Type')=='/Page' for p in pages)
    return dict(detail,page_count=count,selected_pages=pages,all_selected_pages_exist=True,metadata_only=True)


def outside_git(path):
    return subprocess.run(['git','rev-parse','--show-toplevel'],cwd=path,capture_output=True).returncode!=0


def redirect_allowed(document_id,url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:return False
    if document_id=='bert':
        return p.hostname in {'arxiv.org','export.arxiv.org'} and p.path in {'/pdf/1810.04805v2','/pdf/1810.04805v2.pdf'}
    if document_id=='tabpfn_nature_2025':
        return p.hostname=='nature.com' or p.hostname.endswith('.nature.com') or p.hostname in {'media.springernature.com','link.springer.com'}
    return False


def save(path,data):
    with Path(path).open('x') as f:json.dump(data,f,indent=2);f.write('\n')


def allow_html_transport_resume(previous):
    rejected=next(x for x in previous['entries'] if x['document_id']=='tabpfn_nature_2025')
    assert rejected['status']=='REJECTED' and rejected.get('content_type','').startswith('text/html')
    assert rejected['reason']=='Publisher Content-Length mismatch'
    assert rejected.get('verification_failure',{}).get('actual_sha256') is None
    assert {x['document_id'] for x in previous['entries'] if x['status']=='ACCEPTED'}=={'attention','bert'}


def restore(raw,parent,resume_html=False):
    raw=Path(raw).resolve(strict=True)
    if not outside_git(raw) or not outside_git(parent):raise ValueError('Output/evidence must be outside every Git root')
    previous=json.loads((raw/'restoration.json').read_text()) if resume_html else None
    if previous:
        allow_html_transport_resume(previous)
        assert previous['registry_sha256']==REGISTRY_SHA256
    root=Path(previous['root']) if previous else Path(tempfile.mkdtemp(prefix='understanding-engine-006b-inputs-20261110-',dir=parent))
    assert outside_git(root) and not root.is_symlink() and root.stat().st_uid==os.getuid()
    assert root.stat().st_dev==Path('/System/Volumes/Data').stat().st_dev,'Unexpected output filesystem'
    docs=root/'documents'
    if not previous:docs.mkdir(mode=0o700)
    roots=json.loads((raw/'storage-roots.json').read_text());roots['$INPUT_ROOT']=str(root)
    allocation=runpy.run_path(str(HERE.parent/'2026-11-09-cpu-archive-audit/archive_audit.py'))['allocation_snapshot']
    samples=[]
    def guard(pending=0):
        s=allocation(roots);samples.append(s)
        if s['host_available_bytes']-pending<RESERVE:raise RuntimeError('STOP: host 20 GiB reserve')
        if s['allocated_bytes']+pending+MARGIN>CAP:raise RuntimeError('STOP: unchanged 6 GiB inclusive cap')
    guard(sum(r['pdf_bytes'] for r in registry()))
    if not previous:save(raw/'output-root.json',{'path':str(root),'outside_all_git_roots':True,'mode':oct(root.stat().st_mode&0o777)})
    entries=[]
    for row in registry():
        name=row['document_id'];source=Path(row['pdf_path']);partial=docs/(FILENAMES[name]+'.part')
        if previous:
            prior=next(x for x in previous['entries'] if x['document_id']==name)
            if prior['status']=='ACCEPTED':
                verify_pdf(prior['accepted_path'],row);entries.append(prior);continue
        record={'document_id':name,'registered_path':row['pdf_path'],'source_url':row['source_url'],
                'registered_original_available':source.is_file(),'expected_bytes':row['pdf_bytes'],
                'expected_sha256':row['pdf_sha256_verified'],'selected_pages':row['selected_pages'],
                'status':'NOT_ACCEPTED','accepted_path':None,'redirects':[],
                'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        entries.append(record)
        try:
            guard(row['pdf_bytes'])
            if source.is_file():
                verified_source=verify_pdf(source,row)
                with source.open('rb') as src,partial.open('xb') as dst:
                    while True:
                        guard(1024**2);b=src.read(1024**2)
                        if not b:break
                        dst.write(b)
                    dst.flush();os.fsync(dst.fileno())
                record.update(method='verified_local_copy',new_http_body_bytes=0,original_verification=verified_source)
            else:
                if name=='attention':raise ValueError('Attention original unavailable; no substitute authorized')
                assert redirect_allowed(name,row['source_url'])
                class Redirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self,req,fp,code,msg,headers,newurl):
                        if not redirect_allowed(name,newurl):raise ValueError('Unapproved publisher/version redirect')
                        record['redirects'].append({'status':code,'url':newurl})
                        return super().redirect_request(req,fp,code,msg,headers,newurl)
                opener=urllib.request.build_opener(Redirect())
                request=urllib.request.Request(row['source_url'],headers={'Accept-Encoding':'identity','User-Agent':'UnderstandingEngine/006b-input-restoration'})
                received=0;started=time.monotonic()
                with opener.open(request,timeout=45) as response:
                    record.update(method='recorded_publisher_GET',http_status=response.status,final_url=response.geturl(),
                                  content_type=response.headers.get('Content-Type'),advertised_content_length=response.headers.get('Content-Length'))
                    if response.status!=200:raise ValueError('Unexpected publisher HTTP status')
                    if record['advertised_content_length'] is not None and int(record['advertised_content_length'])!=row['pdf_bytes']:
                        raise VerificationError('Publisher Content-Length mismatch',{'advertised_bytes':int(record['advertised_content_length']),'expected_bytes':row['pdf_bytes'],'actual_sha256':None})
                    with partial.open('xb') as dst:
                        while True:
                            if time.monotonic()-started>180:raise RuntimeError('STOP: bounded retrieval timeout')
                            guard(min(1024**2,row['pdf_bytes']-received+1))
                            data=response.read(min(1024**2,row['pdf_bytes']-received+1));received+=len(data)
                            record['new_http_body_bytes']=received
                            if received>row['pdf_bytes']:raise ValueError('Payload exceeds registered length; retained partial is not accepted')
                            if not data:break
                            dst.write(data)
                        dst.flush();os.fsync(dst.fileno())
            verified=verify_pdf(partial,row)
            final=docs/FILENAMES[name];assert not final.exists();partial.rename(final)
            record.update(verified,status='ACCEPTED',accepted_path=str(final),allocated_bytes=final.stat().st_blocks*512)
        except VerificationError as exc:
            record.update(status='REJECTED',reason=str(exc),verification_failure=exc.details)
        except urllib.error.HTTPError as exc:
            record.update(status='UNAVAILABLE_HTTP',http_status=exc.code,reason='Recorded publisher URL returned HTTP '+str(exc.code))
        except Exception as exc:
            record.update(status='FAILED',reason=type(exc).__name__+': '+str(exc))
            if isinstance(exc,RuntimeError):break
        guard()
    result={'schema_version':'006b.restored-inputs.local.1','registry_sha256':REGISTRY_SHA256,
            'root':str(root),'entries':entries,'all_inputs_ready':len(entries)==3 and all(x['status']=='ACCEPTED' for x in entries),
            'max_observed_inclusive_allocated_bytes':max(s['allocated_bytes'] for s in samples),
            'min_observed_host_available_bytes':min(s['host_available_bytes'] for s in samples),
            'new_http_body_bytes':sum(x.get('new_http_body_bytes',0) for x in entries),
            'benchmark_executed':False,'inference_invocations':0,'frozen_registry_modified':False}
    suffix='-publisher-resume' if previous else ''
    result['ordinary_publisher_transport_resume']=bool(previous)
    save(root/('input-remapping.verified.local.json' if previous and result['all_inputs_ready'] else 'input-remapping'+suffix+'.local.json'),result)
    save(raw/('restoration'+suffix+'.json'),result);save(raw/('storage-samples'+suffix+'.json'),samples)
    print(json.dumps({'root':str(root),'all_inputs_ready':result['all_inputs_ready'],'documents':[{k:v for k,v in e.items() if k in ['document_id','status','reason','actual_bytes','actual_sha256','page_count','selected_pages']} for e in entries]},indent=2))
    return result


def verify_local(mapping):
    data=json.loads(Path(mapping).read_text());assert data['registry_sha256']==REGISTRY_SHA256
    rows={r['document_id']:r for r in registry()};accepted={r['document_id']:r for r in data['entries'] if r['status']=='ACCEPTED'}
    if set(accepted)!=set(rows):raise ValueError('Restored input set is incomplete')
    for key,row in rows.items():
        path=Path(accepted[key]['accepted_path']);assert outside_git(path.parent)
        verify_pdf(path,row)
    return {'all_inputs_ready':True,'verified_documents':3,'selected_pages_verified':6,'inference_invocations':0}


def accept_native(raw):
    raw=Path(raw);previous=json.loads((raw/'restoration.json').read_text());allow_html_transport_resume(previous)
    native=json.loads((raw/'native-get.json').read_text());rows=registry()
    row=next(x for x in rows if x['document_id']=='tabpfn_nature_2025')
    assert native['status']=='BYTES_VERIFIED_PENDING_PAGE_TREE' and native['source_url']==row['source_url']
    root=Path(previous['root']);assert outside_git(root) and root.stat().st_uid==os.getuid()
    partial=Path(native['path']);assert partial==root/'documents/s41586-024-08328-6.pdf.native.part'
    verified=verify_pdf(partial,row)
    for old in previous['entries']:
        if old['status']=='ACCEPTED':verify_pdf(old['accepted_path'],next(r for r in rows if r['document_id']==old['document_id']))
    final=root/'documents'/FILENAMES['tabpfn_nature_2025'];assert not final.exists();partial.rename(final)
    entry=dict(next(x for x in previous['entries'] if x['document_id']=='tabpfn_nature_2025'))
    entry.update(verified,status='ACCEPTED',accepted_path=str(final),allocated_bytes=final.stat().st_blocks*512,
                 method='recorded_publisher_GET_using_existing_native_client',http_status=native['http_status'],
                 final_url=native['final_url'],content_type=native['content_type'],redirects=native['redirects'],
                 advertised_content_length=native['advertised_content_length'],new_http_body_bytes=native['new_http_body_bytes'],
                 previous_html_rejections_preserved=True)
    entry.pop('reason',None);entry.pop('verification_failure',None)
    result=dict(previous,entries=[entry if x['document_id']==entry['document_id'] else x for x in previous['entries']],
                all_inputs_ready=True,final_accepted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                new_http_body_bytes=775166+native['new_http_body_bytes'],native_client_delivery=True)
    mapping=root/'input-remapping.verified.local.json';save(mapping,result);save(raw/'restoration-verified.json',result)
    validation=verify_local(mapping);save(raw/'offline-input-verification.json',validation)
    print(json.dumps({'mapping':str(mapping),'nature':verified,'readiness':validation},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw');p.add_argument('--input-parent',default='/Users/Shared');p.add_argument('--verify-local');p.add_argument('--resume-publisher-html',action='store_true');p.add_argument('--accept-native',action='store_true')
    a=p.parse_args()
    if a.verify_local:print(json.dumps(verify_local(a.verify_local)))
    elif a.accept_native:accept_native(a.raw)
    else:raise SystemExit(0 if restore(a.raw,a.input_parent,a.resume_publisher_html)['all_inputs_ready'] else 3)
