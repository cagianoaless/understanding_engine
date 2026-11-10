"""Native macOS stdlib HTTPS delivery only; never accepts an unverified PDF.

Use existing /usr/bin/python3 when the portable client's publisher flow returns
HTML. No cookies, credentials, alternate source, export or package installation.
The separate CPython 3.11/pypdf step must still validate the original page tree.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import ssl
import sys
import time
import urllib.parse
import urllib.request


HERE=Path(__file__).resolve().parent


def main(raw):
    raw=Path(raw);root=Path(json.loads((raw/'output-root.json').read_text())['path'])
    registry=HERE.parents[1]/'source-inputs.json'
    assert hashlib.sha256(registry.read_bytes()).hexdigest()=='4609502f6dcfae904f90be522d9a0ee1682b45eb7e515ac32ea9f3bc899a9469'
    row=next(r for r in json.loads(registry.read_text()) if r['document_id']=='tabpfn_nature_2025')
    roots=json.loads((raw/'storage-roots.json').read_text());roots['$INPUT_ROOT']=str(root)
    allocated=runpy.run_path(str(HERE.parent/'2026-11-09-cpu-archive-audit/archive_audit.py'))['allocation_snapshot']
    records=[];samples=[];received=0;h=hashlib.sha256();started=time.monotonic()
    result={'source_url':row['source_url'],'python':sys.version,'ssl':ssl.OPENSSL_VERSION,'accepted_as_original':False}
    target=root/'documents/s41586-024-08328-6.pdf.native.part'
    def guard(pending=0):
        s=allocated(roots);samples.append(s)
        if s['allocated_bytes']+pending+16*1024**2>6442450944 or s['host_available_bytes']-pending<21474836480:
            raise RuntimeError('STOP: unchanged resource gates')
        if time.monotonic()-started>180:raise RuntimeError('STOP: transfer timeout')
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            p=urllib.parse.urlsplit(newurl)
            allowed=p.hostname and (p.hostname=='nature.com' or p.hostname.endswith('.nature.com') or p.hostname in {'media.springernature.com','link.springer.com'})
            if p.scheme!='https' or p.username or p.password or not allowed:raise ValueError('Unapproved publisher redirect')
            records.append({'status':code,'url':newurl})
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    try:
        guard(row['pdf_bytes'])
        request=urllib.request.Request(row['source_url'],headers={'Accept-Encoding':'identity','User-Agent':'UnderstandingEngine/006b-input-restoration'})
        with urllib.request.build_opener(Redirect()).open(request,timeout=45) as response:
            result.update(http_status=response.status,final_url=response.geturl(),content_type=response.headers.get('Content-Type'),advertised_content_length=response.headers.get('Content-Length'))
            assert response.status==200 and response.headers.get('Content-Type','').startswith('application/pdf')
            if response.headers.get('Content-Length'):assert int(response.headers['Content-Length'])==row['pdf_bytes']
            with target.open('xb') as output:
                while True:
                    guard(min(1024**2,row['pdf_bytes']-received+1));b=response.read(min(1024**2,row['pdf_bytes']-received+1));received+=len(b)
                    if received>row['pdf_bytes']:raise ValueError('Exact length exceeded')
                    if not b:break
                    h.update(b);output.write(b)
                output.flush();os.fsync(output.fileno())
        result.update(actual_bytes=received,actual_sha256=h.hexdigest())
        if received!=row['pdf_bytes'] or h.hexdigest()!=row['pdf_sha256_verified']:raise ValueError('Registered byte length/SHA-256 mismatch; reject')
        result.update(status='BYTES_VERIFIED_PENDING_PAGE_TREE',path=str(target))
    except Exception as exc:
        result.update(status='REJECTED',error_type=type(exc).__name__,error=str(exc),actual_bytes=received,actual_sha256=h.hexdigest() if received else None)
    result.update(redirects=records,new_http_body_bytes=received)
    with (raw/'native-get.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    with (raw/'native-get.samples.json').open('x') as f:json.dump(samples,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['redirects','final_url']},indent=2))
    return result['status']=='BYTES_VERIFIED_PENDING_PAGE_TREE'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--raw',required=True)
    raise SystemExit(0 if main(parser.parse_args().raw) else 3)
