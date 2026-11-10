"""Exactly six frozen development pages; prediction and scoring are separate stages."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import threading
import time

import comparison as C

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
OLD = runpy.run_path(str(HERE.parent/'2026-11-10-one-page-smoke/control.py'))
ALLOCATION = OLD['OLD']['allocation_snapshot']
IMAGE = 'python@sha256:18ce9b03d18802119f4f9270d10a1ceb45d0acb768c305b7fbbd7c6b5b5a020b'
PYTHON = Path.home()/'.local/share/uv/python/cpython-3.11.13-macos-aarch64-none/bin/python3.11'
CAP, RESERVE, MARGIN = 6*1024**3, 20*1024**3, 128*1024**2


def save(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def files(root):
    return {str(p.relative_to(root)): {'bytes': p.stat().st_size, 'sha256': C.sha(p.read_bytes())}
            for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}


class Run:
    def __init__(self, raw):
        self.raw = raw.resolve(strict=True)
        self.cfg = json.loads((self.raw/'configuration.json').read_text())
        self.roots = json.loads((self.raw/'storage-roots.json').read_text())
        assert self.roots['$STAGE_D_RAW'] == str(self.raw)
        assert subprocess.run(['git','rev-parse','--show-toplevel'], cwd=self.raw, capture_output=True).returncode
        self.env = dict(os.environ)
        self.env.pop('DOCKER_CONTEXT', None); self.env.pop('DOCKER_HOST', None)
        self.env['DOCKER_CONFIG'] = self.cfg['docker_config']
        self.docker = ['/opt/homebrew/bin/docker','--host',self.cfg['docker_host']]
        self.prefix = 'ue006b-stage-d-'+self.raw.name.rsplit('-', 1)[-1]
        self.volume = self.prefix+'-data'
        self.samples = []

    def capture(self, argv, check=True, timeout=30):
        p = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=timeout)
        with (self.raw/'commands.jsonl').open('a') as f:
            f.write(json.dumps({'argv': argv, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})+'\n')
        if check and p.returncode:
            raise RuntimeError('Command failed: '+p.stderr[-2000:])
        return p

    def snapshot(self, pending=0):
        s = ALLOCATION(self.roots); self.samples.append(s)
        if s['host_available_bytes']-pending < RESERVE or s['allocated_bytes']+pending+MARGIN > CAP:
            raise RuntimeError('STOP: inclusive storage cap / host reserve')
        return s

    def guest(self):
        p = self.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','df','-Pk','/','/var/lib/docker'])
        rows = [{'available_bytes': int(line.split()[3])*1024, 'mount': line.split()[-1]}
                for line in p.stdout.splitlines()[1:]]
        assert len(rows) == 2 and min(r['available_bytes'] for r in rows) > 256*1024**2
        return rows

    def job(self, name, argv, container=None):
        before = self.snapshot(64*1024**2)
        began = time.monotonic(); expired = threading.Event(); stop_reason = None
        with (self.raw/(name+'.stdout.log')).open('x') as out, (self.raw/(name+'.stderr.log')).open('x') as err:
            p = subprocess.Popen(argv, env=self.env, stdout=out, stderr=err, start_new_session=True)

            def terminate():
                expired.set()
                if container:
                    self.capture(self.docker+['kill',container], check=False)
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGKILL)
            watchdog = threading.Timer(120, terminate); watchdog.start()
            last_guest = 0
            try:
                while p.poll() is None:
                    self.snapshot()
                    if time.monotonic()-last_guest > 2:
                        self.guest(); last_guest = time.monotonic()
                    time.sleep(.2)
            except Exception as exc:
                stop_reason = str(exc); terminate()
            finally:
                p.wait(); watchdog.cancel(); watchdog.join()
        result = {'argv': argv, 'exit_code': p.returncode, 'timeout': expired.is_set() and stop_reason is None,
                  'stop_reason': stop_reason, 'external_wall_seconds': time.monotonic()-began,
                  'deadline_seconds': 120, 'before': before, 'after': self.snapshot()}
        save(self.raw/(name+'.resources.json'), result)
        with (self.raw/'commands.jsonl').open('a') as f:
            f.write(json.dumps({'argv':argv, 'exit_code':p.returncode, 'timeout':result['timeout']})+'\n')
        if stop_reason:
            raise RuntimeError(stop_reason)
        return result

    def predictions(self):
        gate = json.loads((self.raw/'source-compatibility.json').read_text())
        assert gate['gate'] == 'PASS' and all(d['byte_identical_to_original_cache'] for d in gate['documents'])
        runpy.run_path(str(EXPERIMENT/'references.py'))['verify_freeze'](EXPERIMENT)
        assert not (self.raw/'predictions-frozen.json').exists()
        source_rows = json.loads((EXPERIMENT/'source-inputs.json').read_text())
        mapping_path = Path('/Users/Shared/understanding-engine-006b-inputs-20261110-ygw4041v/input-remapping.complete.local.json')
        restore = runpy.run_path(str(HERE.parent/'2026-11-10-input-restoration/restore_inputs.py'))
        restore['verify_local'](mapping_path)
        mapping = json.loads(mapping_path.read_text())
        pdfs = {r['document_id']: Path(r['accepted_path']) for r in mapping['entries']}
        code = {p.name:C.sha(p.read_bytes()) for p in HERE.glob('*.py')}
        save(self.raw/'pre-prediction-code-freeze.json', {'code_sha256': code, 'reference_sha256': C.sha((EXPERIMENT/'annotations.json').read_bytes()),
             'candidate_prediction_selection': 'source-inputs.json selected_pages only; annotations not read by prediction workers',
             'adapter_units': 'all native document items, each provenance box retained, no reference-dependent merging',
             'baseline_resource_domain': 'unchanged frozen source in Linux ARM64 cgroup; existing Linux validator dependencies; exact decisions checked against original host dependency environment',
             'docling_resource_domain': 'fresh Linux ARM64 cgroup per page, same installed candidate/model'})
        self.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','sync'])
        before = self.snapshot(256*1024**2); guest_before = self.guest()
        context_before = self.capture(['/opt/homebrew/bin/docker','context','show']).stdout.strip()
        config_path = Path.home()/'.colima/ue006b/colima.yaml'
        config_hash = C.sha(config_path.read_bytes())
        image = json.loads(self.capture(self.docker+['image','inspect',IMAGE]).stdout)[0]
        assert image['Architecture'] == 'arm64' and image['Os'] == 'linux'
        old_volume = json.loads(self.capture(self.docker+['volume','inspect',self.cfg['volume']]).stdout)[0]
        assert old_volume['Labels']['understanding-engine.run'] == self.cfg['prefix']
        if self.capture(self.docker+['volume','inspect',self.volume],check=False).returncode == 0:
            raise ValueError('New comparison volume already exists; refusing overwrite')
        self.capture(self.docker+['volume','create','--label','understanding-engine.run='+self.prefix,self.volume])
        new_mount = ['--mount','type=volume,source='+self.volume+',target=/run,volume-nocopy']
        old_mount = ['--mount','type=volume,source='+self.cfg['volume']+',target=/ue,readonly,volume-nocopy']
        self.capture(self.docker+['run','--pull=never','--name',self.prefix+'-init']+
            OLD['restricted_args'](64*1024**2,1,'0:0')+new_mount+[IMAGE,'python','-B','-c',"import os;os.chmod('/run',0o777)"])
        setup = self.prefix+'-setup'
        self.capture(self.docker+['run','--pull=never','-d','--name',setup]+OLD['restricted_args'](128*1024**2,1)+
            old_mount+new_mount+[IMAGE,'python','-B','-c','import time;time.sleep(1800)'])
        self.capture(self.docker+['exec',setup,'python','-B','-c',"from pathlib import Path;[(Path('/run')/n).mkdir() for n in ['input','output','tmp','cache','source','sources']]"])
        try:
            for script in ['docling_page.py','baseline_page.py']:
                self.capture(self.docker+['cp',str(HERE/script),setup+':/run/'+script])
            self.capture(self.docker+['cp',str(EXPERIMENT/'baseline-settings.json'),setup+':/run/baseline-settings.json'])
            self.capture(self.docker+['cp',str(HERE.parents[4]/'src/understanding_engine'),setup+':/run/source/understanding_engine'])
            for source in (self.raw/'sources').glob('*.json'):
                self.snapshot(source.stat().st_size+16*1024**2)
                self.capture(self.docker+['cp',str(source),setup+':/run/sources/'+source.name])
            for name, path in pdfs.items():
                self.snapshot(path.stat().st_size+16*1024**2)
                self.capture(self.docker+['cp',str(path),setup+':/run/input/'+name+'.pdf'])
        finally:
            self.capture(self.docker+['stop','-t','1',setup])
        native = self.raw/'native'; native.mkdir()
        host_checks = self.raw/'baseline-host-equivalence'; host_checks.mkdir()
        executions = []
        repo = HERE.parents[4]
        for row in source_rows:
            for page in row['selected_pages']:
                page_id = row['document_id']+'-p'+str(page).zfill(2)
                for engine in ['structure','docling']:
                    label = engine+'-'+page_id
                    target = native/label
                    if engine == 'structure':
                        argv = [str(PYTHON),'-B',str(HERE/'baseline_page.py'),'--source',str(self.raw/'sources'/(row['document_id']+'-extraction.json')),
                                '--page',str(page),'--output',str(host_checks/page_id)]
                        old_pythonpath = self.env.get('PYTHONPATH')
                        self.env['PYTHONPATH'] = str(repo/'src')+':'+str(repo/'.venv/lib/python3.11/site-packages')
                        host_result = self.job('host-equivalence-'+page_id, argv)
                        if old_pythonpath is None:self.env.pop('PYTHONPATH')
                        else:self.env['PYTHONPATH'] = old_pythonpath
                        if host_result['exit_code']:
                            raise RuntimeError('Original environment baseline verification failed')
                    name = self.prefix+'-'+label
                    values = {'TMPDIR':'/run/tmp','XDG_CACHE_HOME':'/run/cache','TORCH_HOME':'/run/cache/torch','HF_HOME':'/run/cache/hf'}
                    if engine == 'structure':
                        values['PYTHONPATH'] = '/run/source:/ue/candidate'
                    env = OLD['candidate_env']()+[v for k,value in values.items() for v in ['--env',k+'='+value]]
                    worker = '/run/baseline_page.py' if engine == 'structure' else '/run/docling_page.py'
                    source_path = '/run/sources/'+row['document_id']+'-extraction.json' if engine == 'structure' else '/run/input/'+row['document_id']+'.pdf'
                    self.capture(self.docker+['create','--pull=never','--name',name]+OLD['restricted_args']()+
                        ['--cpuset-cpus','0-3']+old_mount+new_mount+env+[IMAGE,'python','-B',worker,
                        '--source',source_path,'--page',str(page),'--output','/run/output/'+label])
                    result = self.job(label, self.docker+['start','-a',name], container=name)
                    info = json.loads(self.capture(self.docker+['inspect',name]).stdout)[0]
                    assert not info['State']['Running']
                    assert info['HostConfig']['NetworkMode'] == 'none' and info['HostConfig']['ReadonlyRootfs']
                    assert all(m['Type'] == 'volume' for m in info['Mounts'])
                    save(self.raw/(label+'.container.json'), info)
                    cp = self.capture(self.docker+['cp',name+':/run/output/'+label,str(target)], check=False)
                    result['container_exit_code'] = info['State']['ExitCode']
                    result['oom_killed'] = info['State']['OOMKilled']
                    result['output_copy_exit_code'] = cp.returncode
                    if engine == 'structure' and result['exit_code'] == 0:
                        host_native = json.loads((host_checks/page_id/'structure.json').read_bytes())
                        linux_native = json.loads((target/'structure.json').read_bytes())
                        equivalent = C.semantic_structure(host_native) == C.semantic_structure(linux_native)
                        save(self.raw/('equivalence-'+page_id+'.json'), {'all_page_decisions_geometry_and_source_ids_identical':equivalent,
                            'host_algorithm':host_native['algorithm'],'linux_algorithm':linux_native['algorithm'],
                            'comparison_excludes_only_generated_structure_identity_prefixes':True})
                        if not equivalent:
                            raise RuntimeError('STOP: Linux baseline changed frozen host decisions')
                    execution = json.loads((target/'execution.json').read_text()) if (target/'execution.json').exists() else None
                    executions.append({'engine':engine,'page_id':page_id,'page_number':page,'document_id':row['document_id'],
                        'resource':result,'execution':execution,'output_relative_path':str(target.relative_to(self.raw))})
                    save(self.raw/(label+'.complete.json'), executions[-1])
                    self.capture(['/opt/homebrew/bin/colima','-p','ue006b','ssh','--','sync'])
                    self.snapshot()
                    print(json.dumps({'engine':engine,'page':page_id,'exit':result['exit_code'],
                        'status':execution.get('status') if execution else 'no_output'}),flush=True)
        assert C.sha(config_path.read_bytes()) == config_hash
        assert self.capture(['/opt/homebrew/bin/docker','context','show']).stdout.strip() == context_before
        save(self.raw/'predictions-frozen.json', {'schema_version':'006b.predictions-freeze.1','code_sha256':code,
            'native_files':files(native),'executions':executions,'before':before,'after':self.snapshot(),
            'guest_before':guest_before,'guest_after':self.guest(),'colima_configuration_sha256':config_hash,
            'docker_context_preserved':True,'old_candidate_volume_readonly':True,'neural_page_attempts':6,
            'comparison_scoring_not_yet_run':True})
        save(self.raw/'prediction-storage-samples.json', {'samples':self.samples})

    def score(self):
        frozen = json.loads((self.raw/'predictions-frozen.json').read_text())
        assert files(self.raw/'native') == frozen['native_files']
        assert {p.name:C.sha(p.read_bytes()) for p in HERE.glob('*.py')} == frozen['code_sha256']
        runpy.run_path(str(EXPERIMENT/'references.py'))['verify_freeze'](EXPERIMENT)
        annotations = json.loads((EXPERIMENT/'annotations.json').read_text())
        plan = json.loads((EXPERIMENT/'plan.json').read_text())
        pages = {p['id']:p for p in annotations['pages']}
        sources = {p.stem.removesuffix('-extraction'):json.loads(p.read_bytes()) for p in (self.raw/'sources').glob('*.json')}
        output = self.raw/'comparison'; output.mkdir()
        results = []
        for execution in frozen['executions']:
            page_id, engine = execution['page_id'], execution['engine']
            source = sources[execution['document_id']]['pages'][execution['page_number']-1]
            target = self.raw/execution['output_relative_path']
            begin = time.perf_counter()
            try:
                if execution['resource']['exit_code'] or not execution['execution'] or execution['execution']['status'] != 'success':
                    raise ValueError('Candidate page failed; full frozen denominator retained')
                if engine == 'structure':
                    adapted = C.adapt_structure(json.loads((target/'structure.json').read_bytes()),source,plan['type_mapping']['structure_0_2'])
                else:
                    adapted = C.adapt_docling(json.loads((target/'items.json').read_bytes()),
                        json.loads((target/'docling.json').read_bytes()),source,plan['type_mapping']['docling'])
                C.ground(adapted,source)
                adapted['status'] = 'success'
            except Exception as exc:
                adapted = {'engine':engine,'regions':[],'relations':[],'status':'FAILED',
                           'error_type':type(exc).__name__,'error':str(exc)}
            adapter_seconds = time.perf_counter()-begin
            result = C.score(adapted,pages[page_id],source)
            result.update(adapter_seconds=adapter_seconds,adapter_status=adapted['status'],
                          adapter_error=adapted.get('error'),execution_status=execution['execution']['status'] if execution['execution'] else 'missing',
                          external_wall_seconds=execution['resource']['external_wall_seconds'])
            save(output/(engine+'-'+page_id+'-adapted.json'),adapted)
            save(output/(engine+'-'+page_id+'-scores.json'),result);results.append(result)
        summary = {'schema_version':'006b.frozen-comparison.1','references':'agent_visual_checked',
                   'human_verified_count':0,'quality_metrics_provisional':True,'pages_per_candidate':6,'engines':{}}
        for engine in ['structure','docling']:
            rows = [r for r in results if r['engine'] == engine]
            documents = {d:C.aggregate([r for r in rows if r['document_id']==d]) for d in sources}
            layouts = {l:C.aggregate([r for r in rows if r['layout']==l]) for l in sorted({r['layout'] for r in rows})}
            macro = {}
            for metric in ['precision','recall','f1']:
                values = [d['localization'][metric] for d in documents.values()]
                valid = [v for v in values if v is not None]
                macro['region_'+metric] = {'value':sum(valid)/len(valid) if valid else None,
                    'defined_documents':len(valid),'all_documents':len(values),'reason':None if valid else 'undefined denominators'}
            summary['engines'][engine] = {'micro':C.aggregate(rows),'documents':documents,'layouts':layouts,
                'document_macro':macro,'page_results':rows,
                'completed_pages':sum(r['execution_status']=='success' for r in rows),
                'adapted_pages':sum(r['adapter_status']=='success' for r in rows)}
        save(output/'summary.json',summary)
        save(self.raw/'scoring-storage-samples.json', {'samples':self.samples+[self.snapshot()]})
        print(json.dumps({e:{'completed':r['completed_pages'],'adapted':r['adapted_pages'],'localization':r['micro']['localization'],
                            'order':r['micro']['order'],'paragraph_accuracy':r['micro']['paragraph_accuracy']}
                          for e,r in summary['engines'].items()},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--phase',choices=['predictions','score'],required=True)
    args = parser.parse_args()
    getattr(Run(args.raw),args.phase)()
