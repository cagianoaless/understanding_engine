"""Existing runtime reuse; fresh output volume, unchanged old assets/configuration."""
import argparse
import json
import os
from pathlib import Path
import runpy
import subprocess
import threading
import time

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'2026-11-15-cpu-recognition'
BASE=runpy.run_path(str(PRIOR/'control.py'))
IMAGE=BASE['IMAGE']


class Run(BASE['Run']):
    def __init__(self,raw):
        self.raw=raw.resolve(strict=True);self.cfg=json.loads((raw/'configuration.json').read_text());self.roots=json.loads((raw/'storage-roots.json').read_text());self.samples=[]
        self.env=dict(os.environ);self.env.pop('DOCKER_CONTEXT',None);self.env.pop('DOCKER_HOST',None);self.env['DOCKER_CONFIG']=self.cfg['docker_config']
        self.docker=['/opt/homebrew/bin/docker','--host',self.cfg['docker_host']];self.prefix=self.cfg['diagnostic_prefix'];self.volume=self.prefix+'-output'
        self.roots['$CF_MODEL']='/Users/Shared/understanding-engine-formula-model-9elmxp5o'
    def mounts(self):
        return ['--mount','type=volume,source='+self.volume+',target=/diag,volume-nocopy',
                '--mount','type=volume,source='+self.cfg['new_prefix']+'-data,target=/run,readonly,volume-nocopy',
                '--mount','type=volume,source='+self.cfg['volume']+',target=/ue,readonly,volume-nocopy']
    def setup(self):
        self.snapshot(64*1024**2);self.guest();assert self.capture(self.docker+['volume','inspect',self.volume],check=False).returncode
        self.capture(self.docker+['volume','create','--label','understanding-engine.run='+self.prefix,self.volume])
        name=self.prefix+'-init';restricted=BASE['OLD']['OLD']['restricted_args']
        self.capture(self.docker+['run','--pull=never','--name',name]+restricted(64*1024**2,1,'0:0')+self.mounts()[:2]+[IMAGE,'python','-B','-c',"import os;from pathlib import Path;os.chmod('/diag',0o777);[(Path('/diag')/x).mkdir() for x in ['output','cache','tmp']];[os.chmod('/diag/'+x,0o777) for x in ['output','cache','tmp']]"])
        self.capture(self.docker+['cp',str(HERE/'latency_worker.py'),name+':/diag/latency_worker.py'])
        BASE['save'](self.raw/'diagnostic-code-freeze.json',dict(worker_sha256=BASE['sha'](HERE/'latency_worker.py'),controller_sha256=BASE['sha'](Path(__file__)),caps=[64,256],first_crop_sha256='9b9b3cccafa6e482c591d1ad81c52c4d7daade04b5e63a730af286b8508c1e9d',historical_accuracy_run_unchanged=True))
    def invoke(self,cap):
        assert cap in [64,256]
        if cap==256:
            first=json.loads((self.raw/'max64/execution.json').read_text());assert first['status']=='RETURNED' and first['returned'],'First diagnostic did not return'
        assert BASE['sha'](HERE/'latency_worker.py')==json.loads((self.raw/'diagnostic-code-freeze.json').read_text())['worker_sha256']
        BASE['save'](self.raw/('max'+str(cap)+'.started.json'),dict(max_new_tokens=cap,external_deadline=120))
        self.snapshot(64*1024**2);name=self.prefix+'-max'+str(cap);restricted=BASE['OLD']['OLD']['restricted_args'];env=BASE['OLD']['OLD']['candidate_env']()
        for k,v in {'PYTHONPATH':'/ue/candidate','TMPDIR':'/diag/tmp','HF_HOME':'/diag/cache/hf','XDG_CACHE_HOME':'/diag/cache','TORCH_HOME':'/diag/cache/torch'}.items():env+=['--env',k+'='+v]
        self.capture(self.docker+['create','--pull=never','--name',name]+restricted()+['--cpuset-cpus','0-3']+self.mounts()+env+[IMAGE,'python','-B','-u','/diag/latency_worker.py','--max-new-tokens',str(cap),'--out','/diag/output/max'+str(cap)])
        info=json.loads(self.capture(self.docker+['inspect',name]).stdout)[0];h=info['HostConfig'];assert h['Memory']==h['MemorySwap']==4*1024**3 and h['NanoCpus']==4_000_000_000 and h['NetworkMode']=='none'
        expired=threading.Event();begin=time.monotonic();errors=[]
        with (self.raw/('max'+str(cap)+'.stdout.log')).open('x') as out,(self.raw/('max'+str(cap)+'.stderr.log')).open('x') as err:
            process=subprocess.Popen(self.docker+['start','-a',name],env=self.env,stdout=out,stderr=err)
            def stop():
                expired.set()
                try:self.capture(self.docker+['kill',name],check=False,timeout=10)
                except Exception as exc:errors.append(str(exc))
            timer=threading.Timer(120,stop);timer.start()
            try:
                while process.poll() is None:
                    self.snapshot();time.sleep(.2)
            except Exception as exc:errors.append(str(exc));stop()
            finally:
                timer.cancel();timer.join();process.wait(timeout=15)
        info=json.loads(self.capture(self.docker+['inspect',name]).stdout)[0];assert not info['State']['Running']
        self.capture(self.docker+['cp',name+':/diag/output/max'+str(cap),str(self.raw/('max'+str(cap)))],check=False)
        BASE['save'](self.raw/('max'+str(cap)+'.result.json'),dict(state=info['State'],timeout=expired.is_set(),wall_seconds=time.monotonic()-begin,controller_errors=errors,host_config={k:h[k] for k in ['Memory','MemorySwap','NanoCpus','CpusetCpus','NetworkMode']},snapshot=self.snapshot()))
        print(json.dumps(dict(cap=cap,timeout=expired.is_set(),exit=info['State']['ExitCode'],oom=info['State']['OOMKilled'])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--phase',choices=['setup','64','256'],required=True);a=p.parse_args();r=Run(a.raw)
    try:r.setup() if a.phase=='setup' else r.invoke(int(a.phase))
    finally:
        path=r.raw/(a.phase+'.allocation-samples.json')
        if not path.exists():BASE['save'](path,r.samples)
