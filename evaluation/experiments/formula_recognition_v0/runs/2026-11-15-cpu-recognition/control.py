"""Bounded continuation; inherits tested 120-second watchdog, no old-file edits."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.parse

HERE=Path(__file__).resolve().parent
FORMULA=HERE.parents[1]
ROOT=HERE.parents[4]
OLD_DIR=ROOT/'evaluation/experiments/006b/runs/2026-11-10-six-page-comparison'
sys.path.insert(0,str(OLD_DIR))
OLD=runpy.run_path(str(OLD_DIR/'run.py'))
GiB=1024**3
CAP,RESERVE,MARGIN=7*GiB,12*GiB,128*1024**2
IMAGE=OLD['IMAGE']


def save(path,data):
    with path.open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def limits(s,pending=0):
    if s['host_available_bytes']-pending<RESERVE:raise RuntimeError('STOP: 12 GiB host reserve')
    if s['allocated_bytes']+pending+MARGIN>CAP:raise RuntimeError('STOP: 7 GiB inclusive cap with 128 MiB work margin')


def redirect_allowed(url):
    p=urllib.parse.urlsplit(url)
    return p.scheme=='https' and not p.username and not p.password and p.hostname is not None and (
        p.hostname=='huggingface.co' or p.hostname.endswith('.huggingface.co') or p.hostname.endswith('.hf.co'))


class Run(OLD['Run']):
    def __init__(self,raw):
        self.raw=raw.resolve(strict=True);self.cfg=json.loads((raw/'configuration.json').read_text());self.roots=json.loads((raw/'storage-roots.json').read_text());self.samples=[]
        assert subprocess.run(['git','rev-parse','--show-toplevel'],cwd=raw,capture_output=True).returncode
        self.env=dict(os.environ);self.env.pop('DOCKER_CONTEXT',None);self.env.pop('DOCKER_HOST',None);self.env['DOCKER_CONFIG']=self.cfg['docker_config']
        self.docker=['/opt/homebrew/bin/docker','--host',self.cfg['docker_host']]
        self.prefix=self.cfg['new_prefix'];self.volume=self.prefix+'-data'
        self.model=Path('/Users/Shared/understanding-engine-formula-model-'+self.prefix.rsplit('-',1)[-1]);self.roots['$FORMULA_MODEL_HOST']=str(self.model)
        self.policy=json.loads((HERE/'amendment.json').read_text());assert self.policy['host_reserve_bytes']==RESERVE and self.policy['installed_cache_cap_bytes']==CAP
        frozen=json.loads((FORMULA/'freeze.json').read_text())
        assert all(sha(FORMULA/p)==h for p,h in frozen['files_sha256'].items()),'Prior freeze changed'

    def snapshot(self,pending=0):
        s=OLD['ALLOCATION'](self.roots);self.samples.append(s);limits(s,pending);return s

    def setup(self):
        inventory=json.loads((FORMULA/'model-inventory.json').read_text());total=sum(r['bytes'] for r in inventory['files'] if r['file'] in inventory['runtime_files'])
        before=self.snapshot(2*total+64*1024**2);guest=self.guest()
        assert guest[-1]['available_bytes']>total+256*1024**2
        old=json.loads(self.capture(self.docker+['volume','inspect',self.cfg['volume']]).stdout)[0]
        assert old['Labels']['understanding-engine.run']==self.cfg['prefix']
        image=json.loads(self.capture(self.docker+['image','inspect',IMAGE]).stdout)[0];assert image['Architecture']=='arm64' and image['Os']=='linux'
        save(self.raw/'admission.json',dict(before=before,guest=guest,projected_runtime_model_bytes=total,
             conservative_two_copy_plus_work_bytes=before['allocated_bytes']+2*total+MARGIN,existing_image=IMAGE,
             context=self.capture(['/opt/homebrew/bin/docker','context','show']).stdout.strip(),colima_configuration_sha256=sha(Path.home()/'.colima/ue006b/colima.yaml')))
        assert self.capture(self.docker+['volume','inspect',self.volume],check=False).returncode!=0
        self.capture(self.docker+['volume','create','--label','understanding-engine.run='+self.prefix,self.volume])
        mounts=self.mounts()
        restricted=OLD['OLD']['restricted_args']
        self.capture(self.docker+['run','--pull=never','--name',self.prefix+'-init']+restricted(64*1024**2,1,'0:0')+mounts[:2]+[IMAGE,'python','-B','-c',"import os;os.chmod('/run',0o777)"])
        setup=self.prefix+'-setup'
        self.capture(self.docker+['run','--pull=never','-d','--name',setup]+restricted(128*1024**2,1)+mounts+[IMAGE,'python','-B','-c','import time;time.sleep(1800)'])
        self.capture(self.docker+['exec',setup,'python','-B','-c',"from pathlib import Path;[(Path('/run')/n).mkdir() for n in ['input','crops','tasks','output','artifacts','cache','tmp']];Path('/run/artifacts/docling-project--docling-layout-heron').symlink_to('/ue/artifacts/docling-project--docling-layout-heron')"])
        save(self.raw/'setup-complete.json',dict(container=setup,volume=self.volume,existing_candidate_readonly=True))
        print(json.dumps(dict(stage='setup',inclusive_bytes=self.snapshot()['allocated_bytes'],host_available_bytes=self.samples[-1]['host_available_bytes'])),flush=True)

    def mounts(self):
        return ['--mount','type=volume,source='+self.volume+',target=/run,volume-nocopy',
                '--mount','type=volume,source='+self.cfg['volume']+',target=/ue,readonly,volume-nocopy']

    def acquire(self):
        assert (self.raw/'setup-complete.json').exists();self.model.mkdir(exist_ok=False)
        inventory=json.loads((FORMULA/'model-inventory.json').read_text());rows=[r for r in inventory['files'] if r['file'] in inventory['runtime_files']];records=[];redirects=[]
        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):
                if not redirect_allowed(newurl):raise ValueError('Unapproved model redirect')
                redirects.append(dict(host=urllib.parse.urlsplit(newurl).hostname,status=code))
                return super().redirect_request(req,fp,code,msg,headers,newurl)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
        save(self.raw/'acquisition-start.json',dict(runtime_files=inventory['runtime_files'],expected_total_bytes=sum(r['bytes'] for r in rows),before=self.snapshot(sum(r['bytes'] for r in rows))))
        for row in rows:
            expected='https://huggingface.co/docling-project/CodeFormulaV2/resolve/ecedbe111d15c2dc60bfd4a823cbe80127b58af4/'+row['file'];assert row['url']==expected
            dest=self.model/row['file'];retained=Path(self.cfg['prior_evidence'])/'model-metadata'/row['file'];network=0;tick=time.monotonic()
            if retained.exists():
                data=retained.read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'];dest.write_bytes(data)
            else:
                h=hashlib.sha256();n=0
                req=urllib.request.Request(expected,headers={'Accept-Encoding':'identity','User-Agent':'UnderstandingEngine-formula-v0-pinned'})
                with opener.open(req,timeout=30) as response,(self.model/(row['file']+'.part')).open('xb') as f:
                    assert response.status==200
                    if response.headers.get('Content-Length'):assert int(response.headers['Content-Length'])==row['bytes']
                    while True:
                        self.snapshot(min(1024**2,max(0,row['bytes']-n)))
                        if time.monotonic()-tick>480:raise RuntimeError('Bounded acquisition timeout')
                        data=response.read(min(1024**2,row['bytes']-n+1));n+=len(data)
                        if n>row['bytes']:raise ValueError('Exact model length exceeded')
                        if not data:break
                        h.update(data);f.write(data)
                    f.flush();os.fsync(f.fileno())
                assert n==row['bytes']
                if row['sha256']:assert h.hexdigest()==row['sha256']
                (self.model/(row['file']+'.part')).rename(dest);network=n
            assert dest.stat().st_size==row['bytes'];digest=sha(dest)
            if row['sha256']:assert digest==row['sha256']
            if row['role']!='weights':assert hashlib.sha1(b'blob '+str(row['bytes']).encode()+b'\0'+dest.read_bytes()).hexdigest()==row['git_blob_sha1']
            records.append(dict(file=row['file'],bytes=row['bytes'],sha256=digest,source_url=expected,new_http_body_bytes=network,allocated_bytes=dest.stat().st_blocks*512))
            save(self.raw/(row['file']+'.acquired.json'),records[-1]);print(json.dumps(dict(stage='artifact_verified',file=row['file'],bytes=row['bytes'])),flush=True)
        save(self.raw/'model-manifest.json',records);self.snapshot(sum(r['bytes'] for r in records))
        setup=self.prefix+'-setup';self.capture(self.docker+['exec',setup,'mkdir','/run/artifacts/docling-project--CodeFormulaV2'])
        copy=self.job('copy-model',self.docker+['cp',str(self.model)+'/.',setup+':/run/artifacts/docling-project--CodeFormulaV2'],container=setup)
        assert copy['exit_code']==0 and not copy['timeout']
        save(self.raw/'model-complete.json',dict(records=records,redirects=redirects,after=self.snapshot(),new_http_body_bytes=sum(r['new_http_body_bytes'] for r in records)))

    def prepare(self):
        import pypdfium2 as pdfium
        from understanding_engine.viewer import _renderer_geometry
        registry=json.loads((FORMULA/'input-manifest.json').read_text());local=json.loads((self.raw/'inputs.local.json').read_text());docs={d['id']:d for d in local['documents']}
        for row in registry['documents']:
            for kind in ['pdf','source']:assert sha(Path(docs[row['id']][kind]))==row[kind+'_sha256']
        selection=json.loads((FORMULA/'selection.json').read_text())['expressions'];(self.raw/'crops').mkdir();crops=[];tasks=self.raw/'tasks';tasks.mkdir()
        for row in selection:
            with pdfium.PdfDocument(docs[row['document']]['pdf']) as pdf:
                page=pdf[row['page']-1]
                try:
                    _renderer_geometry(page,row['geometry']);bitmap=page.render(scale=row['crop_scale'],may_draw_forms=False,draw_annots=False)
                    try:image=bitmap.to_pil().copy().convert('RGB')
                    finally:bitmap.close()
                finally:page.close()
            sx,sy=image.width/row['geometry']['width'],image.height/row['geometry']['height'];b=row['crop_bbox'];pixels=[math.floor(b[0]*sx),math.floor(b[1]*sy),math.ceil(b[2]*sx),math.ceil(b[3]*sy)]
            crop=image.crop(pixels);path=self.raw/'crops'/(row['id']+'.png');crop.save(path)
            crops.append(dict(id=row['id'],pdf_sha256=row['pdf_sha256'],page=row['page'],bbox=row['crop_bbox'],pixel_box=pixels,image_dimensions=list(crop.size),sha256=sha(path),bytes=path.stat().st_size))
            save(tasks/('crop-'+row['id']+'.json'),dict(scenario='crop',id=row['id'],input='/run/crops/'+path.name,input_sha256=sha(path),output='/run/output/crop-'+row['id'],source_pdf_sha256=row['pdf_sha256'],source_page=row['page']))
        for document,page in sorted({(r['document'],r['page']) for r in selection}):
            pdf=Path(docs[document]['pdf']);label='page-'+document+'-'+str(page)
            save(tasks/(label+'.json'),dict(scenario='page',id=label,input='/run/input/'+document+'.pdf',input_sha256=sha(pdf),page=page,output='/run/output/'+label))
        save(self.raw/'crops-frozen.json',dict(crops=crops,selection_sha256=sha(FORMULA/'selection.json'),references_not_loaded=True,renderer_version=__import__('importlib.metadata').metadata.version('pypdfium2')))
        setup=self.prefix+'-setup'
        for src,target in [(self.raw/'crops','/run/crops'),(tasks,'/run/tasks')]:self.capture(self.docker+['cp',str(src)+'/.',setup+':'+target])
        for src,target in [(HERE/'worker.py','/run/worker.py'),(self.raw/'model-manifest.json','/run/model-manifest.json')]:self.capture(self.docker+['cp',str(src),setup+':'+target])
        for doc in docs.values():self.capture(self.docker+['cp',doc['pdf'],setup+':/run/input/'+doc['id']+'.pdf'])
        self.capture(self.docker+['stop','-t','1',setup]);self.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','sync'])
        save(self.raw/'prediction-code-freeze.json',dict(code_sha256={p.name:sha(p) for p in HERE.glob('*.py')},selection_sha256=sha(FORMULA/'selection.json'),references_sha256=sha(FORMULA/'references.json'),model_manifest_sha256=sha(self.raw/'model-manifest.json'),input_crops_frozen_sha256=sha(self.raw/'crops-frozen.json')))

    def invocation(self,label):
        name=self.prefix+'-'+label;task=self.raw/'tasks'/(label+'.json');assert task.exists()
        if label!='crop-attn_fraction':
            first=json.loads((self.raw/'native/crop-attn_fraction/execution.json').read_text())
            assert first['status']=='SUCCESS' and first['generate_calls'] and all(v.get('success') for v in first['generate_calls']),'First actual model invocation failed: no further inference'
        assert sha(HERE/'worker.py')==json.loads((self.raw/'prediction-code-freeze.json').read_text())['code_sha256']['worker.py']
        (self.raw/'native').mkdir(exist_ok=True);target=self.raw/'native'/label
        assert not target.exists();self.snapshot(128*1024**2);self.guest()
        env=OLD['OLD']['candidate_env']()+[v for k,value in {'PYTHONPATH':'/ue/candidate','TMPDIR':'/run/tmp','XDG_CACHE_HOME':'/run/cache','TORCH_HOME':'/run/cache/torch','HF_HOME':'/run/cache/hf'}.items() for v in ['--env',k+'='+value]]
        self.capture(self.docker+['create','--pull=never','--name',name]+OLD['OLD']['restricted_args']()+['--cpuset-cpus','0-3']+self.mounts()+env+[IMAGE,'python','-B','-u','/run/worker.py','--task','/run/tasks/'+task.name])
        info=json.loads(self.capture(self.docker+['inspect',name]).stdout)[0];h=info['HostConfig']
        assert h['Memory']==h['MemorySwap']==4*GiB and h['NanoCpus']==4*1000000000 and h['NetworkMode']=='none' and h['ReadonlyRootfs'] and not h['Privileged']
        assert len(info['Mounts'])==2 and all(v['Type']=='volume' for v in info['Mounts']) and not next(v for v in info['Mounts'] if v['Destination']=='/ue')['RW']
        result=self.job(label,self.docker+['start','-a',name],container=name)
        info=json.loads(self.capture(self.docker+['inspect',name]).stdout)[0];assert not info['State']['Running']
        self.capture(self.docker+['cp',name+':/run/output/'+label,str(target)],check=False)
        summary=dict(resource=result,state=info['State'],host_config={k:h[k] for k in ['Memory','MemorySwap','NanoCpus','CpusetCpus','NetworkMode','ReadonlyRootfs','Privileged']},mounts=info['Mounts'])
        save(self.raw/(label+'.complete.json'),summary);print(json.dumps(dict(stage='invocation_complete',id=label,exit_code=info['State']['ExitCode'],timeout=result['timeout'],oom=info['State']['OOMKilled'])),flush=True)
        return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--phase',choices=['setup','acquire','prepare','invoke'],required=True);p.add_argument('--label');a=p.parse_args();r=Run(a.raw)
    try:
        if a.phase=='invoke':r.invocation(a.label)
        else:getattr(r,a.phase)()
    finally:
        path=r.raw/(a.phase+('-'+a.label if a.label else '')+'.samples.json')
        if not path.exists():save(path,r.samples)


if __name__=='__main__':main()
