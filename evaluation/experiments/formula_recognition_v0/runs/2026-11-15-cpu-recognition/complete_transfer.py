"""Complete an exact partial artifact by validated HTTP Range, never model retry.

Only used if the original bounded transfer expires. No artifact/version changes,
no truncated-file replacement, no inference, no discard of the original evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

from control import Run,FORMULA,save,sha,redirect_allowed


def validate_range(status,content_range,start,total):
    if start:
        if status!=206 or content_range!=f'bytes {start}-{total-1}/{total}':
            raise ValueError('Server did not honor the exact remaining byte range')
    elif status!=200:raise ValueError('Unexpected artifact status')


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);a=p.parse_args();r=Run(a.raw)
    assert not (r.raw/'model-manifest.json').exists() and not (r.raw/'native').exists()
    manifest=json.loads((FORMULA/'model-inventory.json').read_text());records=[];transfers=[]
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not redirect_allowed(newurl):raise ValueError('Unapproved artifact redirect')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
    for row in [v for v in manifest['files'] if v['file'] in manifest['runtime_files']]:
        dest=r.model/row['file'];partial=r.model/(row['file']+'.part');record=r.raw/(row['file']+'.acquired.json')
        if dest.exists():
            assert record.exists();rec=json.loads(record.read_text());assert dest.stat().st_size==rec['bytes'] and sha(dest)==rec['sha256'];records.append(rec);continue
        cached=Path(r.cfg['prior_evidence'])/'model-metadata'/row['file'];start=partial.stat().st_size if partial.exists() else 0
        assert not partial.is_symlink() and 0<=start<row['bytes']
        received=0
        if not start and cached.exists():
            data=cached.read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'];dest.write_bytes(data)
        else:
            tick=time.monotonic();headers={'Accept-Encoding':'identity','User-Agent':'UnderstandingEngine-formula-pinned-transfer'}
            if start:headers['Range']='bytes='+str(start)+'-'
            with opener.open(urllib.request.Request(row['url'],headers=headers),timeout=30) as response:
                validate_range(response.status,response.headers.get('Content-Range'),start,row['bytes'])
                with partial.open('ab' if start else 'xb') as f:
                    while True:
                        r.snapshot(min(1024**2,row['bytes']-start-received))
                        if time.monotonic()-tick>480:raise RuntimeError('Continuation transfer deadline')
                        data=response.read(min(1024**2,row['bytes']-start-received+1));received+=len(data)
                        if start+received>row['bytes']:raise ValueError('Excess artifact body')
                        if not data:break
                        f.write(data)
                    f.flush();os.fsync(f.fileno())
            assert start+received==row['bytes'];assert not row['sha256'] or sha(partial)==row['sha256'];partial.rename(dest)
            transfers.append(dict(file=row['file'],previous_exact_bytes=start,new_range_body_bytes=received,total_bytes=row['bytes'],sha256=sha(dest)))
        assert dest.stat().st_size==row['bytes'];digest=sha(dest)
        if row['sha256']:assert digest==row['sha256']
        if row['role']!='weights':assert hashlib.sha1(b'blob '+str(row['bytes']).encode()+b'\0'+dest.read_bytes()).hexdigest()==row['git_blob_sha1']
        rec=dict(file=row['file'],bytes=row['bytes'],sha256=digest,source_url=row['url'],new_http_body_bytes=start+received,allocated_bytes=dest.stat().st_blocks*512)
        records.append(rec);save(record,rec);print(json.dumps(dict(stage='artifact_verified',file=row['file'],bytes=row['bytes'])),flush=True)
    save(r.raw/'transfer-continuation.json',dict(transfers=transfers,original_transfer_preserved=True,inference_attempts=0,reason='Original 480-second artifact transfer deadline; per-inference limit remains 120 seconds'))
    save(r.raw/'model-manifest.json',records);r.snapshot(sum(v['bytes'] for v in records));setup=r.prefix+'-setup'
    r.capture(r.docker+['exec',setup,'mkdir','/run/artifacts/docling-project--CodeFormulaV2'])
    copied=r.job('copy-model',r.docker+['cp',str(r.model)+'/.',setup+':/run/artifacts/docling-project--CodeFormulaV2'],container=setup)
    assert copied['exit_code']==0 and not copied['timeout']
    save(r.raw/'model-complete.json',dict(records=records,transfer_continuation=True,after=r.snapshot(),new_http_body_bytes=sum(v['new_http_body_bytes'] for v in records)))
    save(r.raw/'transfer-continuation.samples.json',r.samples)


if __name__=='__main__':main()
