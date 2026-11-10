"""Pinned minimal model acquisition, then one networkless, timed invocation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


HERE=Path(__file__).resolve().parent
HOST=runpy.run_path(str(HERE/'control.py'))


def model_redirect_allowed(url):
    p=urllib.parse.urlsplit(url)
    return p.scheme=='https' and p.hostname is not None and not p.username and not p.password and (
        p.hostname=='huggingface.co' or p.hostname.endswith('.huggingface.co') or p.hostname.endswith('.hf.co'))


def model(c):
    assert json.loads((c.raw/'installation-complete.json').read_text())['gate']=='PASS'
    frozen=json.loads((HERE.parent/'2026-11-09-linux-preflight/model.json').read_text())
    required=[x for x in frozen['files'] if x['filename'] in ['config.json','preprocessor_config.json','model.safetensors']]
    assert len(required)==3 and sum(x['bytes'] for x in required)==171662708
    dest=c.raw/'model';dest.mkdir(exist_ok=False);records=[];redirects=[]
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not model_redirect_allowed(newurl):raise ValueError('Unapproved model redirect')
            p=urllib.parse.urlsplit(newurl);redirects.append({'host':p.hostname,'path_sha256':hashlib.sha256(p.path.encode()).hexdigest(),'status':code})
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
    for row in required:
        c.snapshot();HOST['limits'](c.snapshot(),row['bytes'])
        final=dest/row['filename'];cache=Path(c.cfg['model_metadata_cache'])/row['filename']
        received=0;h=hashlib.sha256();begin=time.monotonic();samples=[]
        if row['filename']!='model.safetensors' and cache.exists():
            data=cache.read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
            final.write_bytes(data);received=len(data);h.update(data);network=0
        else:
            request=urllib.request.Request(row['url'],headers={'Accept-Encoding':'identity','User-Agent':'understanding-engine-006b-smoke'})
            try:
                with opener.open(request,timeout=30) as response,(dest/(row['filename']+'.part')).open('xb') as stream:
                    if response.status!=200:raise ValueError('Unexpected model HTTP status')
                    if response.headers.get('Content-Length') is not None:assert int(response.headers['Content-Length'])==row['bytes']
                    while True:
                        s=c.snapshot();HOST['limits'](s,min(1024**2,row['bytes']-received+1));samples.append(s)
                        if time.monotonic()-begin>240:raise RuntimeError('Model acquisition timeout')
                        data=response.read(min(1024**2,row['bytes']-received+1))
                        received+=len(data)
                        if received>row['bytes']:raise ValueError('Model payload exceeded exact length')
                        if not data:break
                        h.update(data);stream.write(data)
                    stream.flush();os.fsync(stream.fileno())
            except urllib.error.HTTPError as exc:
                raise RuntimeError('Model HTTP error '+str(exc.code)+'; no fallback or token used') from None
            assert received==row['bytes'] and h.hexdigest()==row['sha256']
            (dest/(row['filename']+'.part')).rename(final);network=received
        assert received==row['bytes'] and h.hexdigest()==row['sha256']
        records.append({'filename':row['filename'],'bytes':received,'sha256':h.hexdigest(),'source_url':row['url'],'new_http_body_bytes':network,'allocated_bytes':final.stat().st_blocks*512})
        HOST['write'](c.raw/('model-'+row['filename']+'.samples.json'),samples)
    name=c.cfg['prefix']+'-install';c.capture(c.docker+['start',name])
    c.capture(c.docker+['exec',name,'python','-B','-c',"from pathlib import Path;Path('/ue/artifacts/docling-project--docling-layout-heron').mkdir(parents=True,exist_ok=False)"])
    copied=c.job('copy-model',c.docker+['cp',str(dest)+'/.',name+':/ue/artifacts/docling-project--docling-layout-heron'],growth=171662708+64*1024**2,owner=name)
    manifest=c.raw/'model-manifest.json';HOST['write'](manifest,records)
    for path,target in [(manifest,'model-manifest.json'),(HERE/'smoke_page.py','smoke_page.py'),(HERE/'selection.json','selection.json'),(Path(c.cfg['pdf']),'input/original.pdf')]:
        c.capture(c.docker+['cp',str(path),name+':/ue/'+target])
    check="""import json,hashlib
from pathlib import Path
rows=json.loads(Path('/ue/model-manifest.json').read_text())
for r in rows:
 p=Path('/ue/artifacts/docling-project--docling-layout-heron')/r['filename'];assert p.stat().st_size==r['bytes'];assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
assert hashlib.sha256(Path('/ue/input/original.pdf').read_bytes()).hexdigest()=='bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
print(json.dumps({'verified_guest_model_files':len(rows),'pdf_hash_verified':True}))
"""
    check_result=c.capture(c.docker+['exec',name,'python','-B','-c',check],timeout=30)
    c.capture(c.docker+['stop','-t','1',name])
    c.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','sync'])
    HOST['write'](c.raw/'model-complete.json',{'gate':'PASS','revision':frozen['revision'],'files':records,'redirects_without_tokens':redirects,
               'new_http_body_bytes':sum(r['new_http_body_bytes'] for r in records),'guest_verification':json.loads(check_result.stdout),
               'copy_resources':copied,'retained_storage':c.snapshot()})
    print(json.dumps({'model_gate':'PASS','new_http_body_bytes':sum(r['new_http_body_bytes'] for r in records),'files':len(records)}))


def smoke(c):
    assert json.loads((c.raw/'model-complete.json').read_text())['gate']=='PASS'
    assert json.loads((c.raw/'installation-complete.json').read_text())['gate']=='PASS'
    c.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','sync'])
    HOST['write'](c.raw/'single-attempt.json',{'page':6,'maximum_inference_attempts':1,'source_sha256':'bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697',
                'source_script_sha256':hashlib.sha256((HERE/'smoke_page.py').read_bytes()).hexdigest()})
    name=c.cfg['prefix']+'-one-page';volume=c.cfg['volume']
    mount=['--mount','type=volume,source='+volume+',target=/ue,volume-nocopy']
    c.capture(c.docker+['create','--name',name,'--label','understanding-engine.run='+c.cfg['prefix']]+HOST['restricted_args']()+['--cpuset-cpus','0-3']+mount+HOST['candidate_env']()+[c.image,'python','-B','-u','/ue/smoke_page.py'])
    info=json.loads(c.capture(c.docker+['inspect',name]).stdout)[0];h=info['HostConfig']
    assert h['Memory']==h['MemorySwap']==4294967296 and h['NanoCpus']==4000000000
    assert h['NetworkMode']=='none' and h['ReadonlyRootfs'] and not h['Privileged']
    assert len(info['Mounts'])==1 and info['Mounts'][0]['Name']==volume and info['Mounts'][0]['Type']=='volume'
    timed_out=threading.Event()
    def timeout():
        timed_out.set();c.capture(c.docker+['kill',name],check=False,timeout=5)
    watchdog=threading.Timer(120,timeout);watchdog.daemon=True;watchdog.start()
    result=None;error=None
    try:result=c.job('single-page',c.docker+['start','-a',name],timeout=120,growth=512*1024**2,owner=name)
    except Exception as exc:error=str(exc)
    finally:watchdog.cancel()
    inspect=json.loads(c.capture(c.docker+['inspect',name]).stdout)[0]
    c.capture(c.docker+['cp',name+':/ue/output/.',str(c.raw/'page-output')],check=False)
    HOST['write'](c.raw/'smoke-execution.json',{'timed_out':timed_out.is_set(),'error':error,'resources':result,
               'container_inspect':inspect,'storage':c.snapshot(enforce=False),'six_page_benchmark_executed':False})
    if error or timed_out.is_set() or inspect['State']['ExitCode']!=0:raise RuntimeError('Single-page attempt failed; no retry: '+str(error))
    page=json.loads((c.raw/'page-output/smoke-result.json').read_text())
    assert page['status']=='success' and page['page_numbers']==[6] and len(page['model_prediction_batches'])==1
    print(json.dumps({'smoke_gate':'PASS','page':6,'conversion_seconds':page['conversion_wall_seconds'],
                      'peak_cgroup_memory_bytes':page['final_cgroup']['memory.peak'],'items':page['item_count']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',required=True);p.add_argument('--phase',choices=['model','smoke'],required=True)
    a=p.parse_args();c=HOST['Control'](a.raw)
    try:globals()[a.phase](c)
    except Exception as exc:
        HOST['write'](c.raw/(a.phase+'-failure.json'),{'error_type':type(exc).__name__,'error':str(exc),'storage':c.snapshot(enforce=False)})
        raise
