"""Executed only inside the isolated Linux candidate, after offline installation."""

import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sys


def main():
    expected=json.loads(Path('/ue/expected.json').read_text())
    norm=lambda n:re.sub(r'[-_.]+','-',n).lower()
    installed={norm(d.metadata['Name']):d.version for d in importlib.metadata.distributions(path=['/ue/candidate'])}
    assert installed=={r['name']:r['version'] for r in expected},'Unexpected/missing version in candidate target'
    for row in expected:
        p=Path('/ue/wheels')/row['filename']; h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1024**2),b''):h.update(b)
        assert p.stat().st_size==row['bytes'] and h.hexdigest()==row['sha256']
    pip=json.loads(Path('/ue/install-report.json').read_text())
    assert len(pip['install'])==103
    for r in pip['install']:
        n=norm(r['metadata']['name']);e=next(x for x in expected if x['name']==n)
        assert r['metadata']['version']==e['version']
        assert r['download_info']['url'].startswith('file:///ue/wheels/')
        assert r['download_info']['archive_info']['hashes']['sha256']==e['sha256']
    imports={}
    for name in ['torch','torchvision','transformers','cv2','pypdfium2','docling_parse','docling.document_converter','docling.datamodel.pipeline_options']:
        try:module=importlib.import_module(name);imports[name]={'status':'PASS','file':getattr(module,'__file__',None)}
        except Exception as exc:imports[name]={'status':'FAIL','type':type(exc).__name__,'error':str(exc)}
    errors=[n for n,v in imports.items() if v['status']!='PASS']
    data={'gate':'FAIL' if errors else 'PASS','python':platform.python_version(),'architecture':platform.machine(),'libc':platform.libc_ver(),
          'installed':installed,'imports':imports,'import_errors':errors,'wheel_hashes_verified':103,
          'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),
          'memory_swap_max':Path('/sys/fs/cgroup/memory.swap.max').read_text().strip(),
          'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
          'candidate_allocated_bytes':sum(p.lstat().st_blocks*512 for p in Path('/ue/candidate').rglob('*') if p.is_file()),
          'candidate_logical_bytes':sum(p.stat().st_size for p in Path('/ue/candidate').rglob('*') if p.is_file()),
          'targeted_bytecode_files':len(list(Path('/ue/candidate').rglob('*.pyc')))}
    if not errors:
        import torch,torchvision
        assert torch.__version__=='2.15.0+cpu' and torchvision.__version__=='0.29.2+cpu'
        assert torch.version.cuda is None and not torch.cuda.is_available()
        data.update(torch=torch.__version__,torchvision=torchvision.__version__,cuda_version=torch.version.cuda)
    assert data['python']=='3.11.13' and data['architecture']=='aarch64'
    assert data['memory_max']=='4294967296' and data['memory_swap_max']=='0'
    Path('/ue/import-report.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))
    raise SystemExit(1 if errors else 0)


if __name__=='__main__':main()
