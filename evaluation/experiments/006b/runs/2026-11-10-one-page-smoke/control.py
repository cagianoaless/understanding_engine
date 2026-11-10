"""Host-side bounded jobs for this one-page experiment, not a benchmark runner."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import time


HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "policy.json").read_text())
OLD = runpy.run_path(str(HERE.parent / "2026-11-09-cpu-archive-audit/archive_audit.py"))
GiB = 1024 ** 3
MARGIN = 128 * 1024 ** 2


def write(path, data):
    with Path(path).open("x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def limits(snapshot, pending=0):
    if snapshot["host_available_bytes"] - pending < POLICY["host_reserve_bytes"]:
        raise RuntimeError("STOP: host reserve")
    if snapshot["allocated_bytes"] + pending + MARGIN > POLICY["installed_cache_cap_bytes"]:
        raise RuntimeError("STOP: inclusive storage admission/guard")


def restricted_args(memory=4*GiB, cpus=4, user="65534:65534"):
    return ["--network", "none", "--read-only", "--user", user,
            "--memory", str(memory), "--memory-swap", str(memory),
            "--cpus", str(cpus), "--pids-limit", "256", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777"]


def candidate_env():
    values = {"PYTHONDONTWRITEBYTECODE":"1", "PYTHONPATH":"/ue/candidate",
              "TMPDIR":"/ue/tmp", "XDG_CACHE_HOME":"/ue/cache", "TORCH_HOME":"/ue/cache/torch",
              "HF_HOME":"/ue/cache/hf", "HF_HUB_OFFLINE":"1", "TRANSFORMERS_OFFLINE":"1",
              "HF_HUB_DISABLE_TELEMETRY":"1", "TOKENIZERS_PARALLELISM":"false",
              "CUDA_VISIBLE_DEVICES":"", "OMP_NUM_THREADS":"4", "MKL_NUM_THREADS":"4",
              "OPENBLAS_NUM_THREADS":"4", "NUMEXPR_NUM_THREADS":"4", "RAYON_NUM_THREADS":"4"}
    return [arg for k,v in values.items() for arg in ("--env",k+"="+v)]


class Control:
    def __init__(self, raw):
        p=Path(raw)
        if p.is_symlink():raise ValueError("Unexpected raw symlink")
        self.raw=p.resolve(strict=True)
        if subprocess.run(["git","rev-parse","--show-toplevel"],cwd=self.raw,capture_output=True).returncode==0:
            raise ValueError("Raw evidence inside Git")
        self.cfg=json.loads((self.raw/"configuration.json").read_text())
        self.roots=json.loads((self.raw/"storage-roots.json").read_text())
        assert self.roots["$SMOKE_RAW"]==str(self.raw)
        self.env=dict(os.environ)
        self.env.pop("DOCKER_CONTEXT",None);self.env.pop("DOCKER_HOST",None)
        self.env["DOCKER_CONFIG"]=self.cfg["docker_config"]
        self.docker=["/opt/homebrew/bin/docker","--host",self.cfg["docker_host"]]
        self.image=json.loads((self.raw/"image-lock.json").read_text())["image"]

    def capture(self, args, check=True, timeout=30):
        p=subprocess.run(args,env=self.env,capture_output=True,text=True,timeout=timeout)
        with (self.raw/"commands.jsonl").open("a") as f:
            f.write(json.dumps({"argv":args,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr})+"\n")
        if check and p.returncode:raise RuntimeError("Command failed: "+str(args[:4])+"; "+p.stderr[-1500:])
        return p

    def guest(self):
        p=self.capture(["/opt/homebrew/bin/colima","-p","ue006b","ssh","--","df","-Pk","/","/var/lib/docker"])
        rows=p.stdout.splitlines()[1:]
        data=[{"filesystem":x.split()[0],"available_bytes":int(x.split()[3])*1024,"mount":x.split()[-1]} for x in rows]
        if len(data)!=2 or min(r["available_bytes"] for r in data)<256*1024**2:
            raise RuntimeError("STOP: guest filesystem reserve/capacity")
        return data

    def snapshot(self, enforce=True):
        s=OLD["allocation_snapshot"](self.roots)
        if enforce:limits(s)
        return s

    def job(self, name, args, timeout=180, growth=0, owner=None, guest_probe=None):
        before=self.snapshot();limits(before,growth);guest_before=self.guest()
        if guest_before[-1]["available_bytes"] < growth+256*1024**2:
            raise RuntimeError("STOP: insufficient guest capacity for bounded stage")
        samples=[];reason=None;begin=time.monotonic();last_guest=0
        with (self.raw/(name+".stdout.log")).open("x") as out,(self.raw/(name+".stderr.log")).open("x") as err:
            p=subprocess.Popen(args,env=self.env,stdout=out,stderr=err,start_new_session=True)
            try:
                while p.poll() is None:
                    now=time.monotonic();s=self.snapshot();s["elapsed_seconds"]=now-begin
                    samples.append(s)
                    if s["allocated_bytes"]-before["allocated_bytes"]>growth:
                        raise RuntimeError("STOP: stage growth reservation exceeded")
                    if now-begin>=timeout:raise RuntimeError("STOP: external timeout")
                    if now-last_guest>=2:
                        s["guest_filesystems"]=self.guest()
                        if guest_probe:
                            probe=self.capture(self.docker+["exec",owner,"python","-c",guest_probe],check=False,timeout=5)
                            s["guest_probe"]={"exit_code":probe.returncode,"stdout":probe.stdout}
                        last_guest=now
                    time.sleep(0.2)
            except Exception as exc:
                reason=str(exc)
                if owner:
                    self.capture(self.docker+["kill",owner],check=False)
                if p.poll() is None:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid,signal.SIGKILL);p.wait()
            p.wait()
        after=self.snapshot(enforce=False);samples.append(dict(after,elapsed_seconds=time.monotonic()-begin))
        try:
            limits(after)
            if after["allocated_bytes"]-before["allocated_bytes"]>growth:
                raise RuntimeError("STOP: post-stage growth reservation exceeded")
        except Exception as exc:
            reason=reason or str(exc)
        result={"argv":args,"exit_code":p.returncode,"stop_reason":reason,"elapsed_seconds":time.monotonic()-begin,
                "before":before,"after":after,"guest_before":guest_before,"guest_after":self.guest(),
                "observed_max_allocated_bytes":max([before["allocated_bytes"]]+[x["allocated_bytes"] for x in samples]),
                "observed_min_host_available_bytes":min([before["host_available_bytes"]]+[x["host_available_bytes"] for x in samples]),
                "sample_count":len(samples),"growth_reservation_bytes":growth,"timeout_seconds":timeout,
                "control_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        write(self.raw/(name+".resources.json"),result);write(self.raw/(name+".samples.json"),samples)
        if reason or p.returncode:raise RuntimeError(name+" failed: "+str(reason or p.returncode))
        return result

    def runtime(self):
        assert json.loads((HERE/"licensing.json").read_text())["local_execution_gate"]=="PASS"
        lock=json.loads((self.raw/"image-lock.json").read_text())
        if lock["expected_compressed_layer_bytes"]>128*1024**2:raise ValueError("Unexpected runtime download")
        result=self.job("runtime-pull",self.docker+["pull","--platform","linux/arm64",self.image],growth=512*1024**2)
        info=json.loads(self.capture(self.docker+["image","inspect",self.image]).stdout)[0]
        config=json.loads((self.raw/"python-arm64-config.json").read_text())
        assert info["Architecture"]=="arm64" and info["Os"]=="linux"
        assert info["RootFS"]["Layers"]==config["rootfs"]["diff_ids"]
        proposal=json.loads((HERE.parent/"2026-11-09-cpu-packaging/archive-audit-proposal.json").read_text())
        script="""import sys,platform,json,os,hashlib
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename
assert sys.version_info[:3]==(3,11,13) and platform.machine()=='aarch64'
tags=set(sys_tags()); names=json.loads(sys.argv[1]); bad=[n for n in names if not tags.intersection(parse_wheel_filename(n)[3])]
assert not bad,bad
print(json.dumps({'python':sys.version,'architecture':platform.machine(),'libc':platform.libc_ver(),'compatible_wheels':len(names),'incompatible_wheels':bad,'memory_max':open('/sys/fs/cgroup/memory.max').read().strip(),'swap_max':open('/sys/fs/cgroup/memory.swap.max').read().strip(),'cpu_max':open('/sys/fs/cgroup/cpu.max').read().strip()}))
"""
        name=self.cfg["prefix"]+"-runtime-check"
        output=self.capture(self.docker+["run","--name",name]+restricted_args(128*1024**2,1)+[self.image,"python","-B","-c",script,json.dumps([r["filename"] for r in proposal["artifacts"]])],timeout=40)
        verification=json.loads(output.stdout)
        assert verification["swap_max"]=="0"
        write(self.raw/"runtime-complete.json",{"gate":"PASS","image":lock,"inspect":info,"verification":verification,"pull":result})
        print(json.dumps({"runtime_gate":"PASS","image":self.image,"python":verification["python"].split()[0],"compressed_layers":lock["expected_compressed_layer_bytes"],"docker_reported_size_bytes_not_allocation":info["Size"],"retained_inclusive_allocated_bytes":self.snapshot()["allocated_bytes"]}))

    def install(self):
        assert json.loads((self.raw/"runtime-complete.json").read_text())["gate"]=="PASS"
        rows=OLD["load_allowlist"]();manifest=[]
        for r in rows:
            path=Path(self.cfg["archives"])/r["filename"]
            assert path.is_file() and not path.is_symlink()
            h=hashlib.sha256()
            with path.open("rb") as f:
                for b in iter(lambda:f.read(1024**2),b""):h.update(b)
            assert path.stat().st_size==r["bytes"] and h.hexdigest()==r["sha256"]
            manifest.append({"name":r["name"],"version":r["version"],"filename":r["filename"],"bytes":r["bytes"],"sha256":h.hexdigest()})
        assert {p.name for p in Path(self.cfg["archives"]).iterdir()}=={r["filename"] for r in rows}
        write(self.raw/"pre-install-hashes.json",manifest)
        volume=self.cfg["volume"];name=self.cfg["prefix"]+"-install"
        if self.capture(self.docker+["volume","inspect",volume],check=False).returncode==0:
            raise ValueError("New experiment volume already exists")
        self.capture(self.docker+["volume","create","--label","understanding-engine.run="+self.cfg["prefix"],volume])
        mount=["--mount","type=volume,source="+volume+",target=/ue,volume-nocopy"]
        self.capture(self.docker+["run","--name",self.cfg["prefix"]+"-volume-init"]+restricted_args(64*1024**2,1,"0:0")+mount+[self.image,"python","-B","-c","import os;os.chmod('/ue',0o777)"],timeout=40)
        self.capture(self.docker+["run","-d","--name",name]+restricted_args()+["--cpuset-cpus","0-3"]+mount+candidate_env()+[self.image,"python","-B","-c","import time;time.sleep(1800)"])
        self.capture(self.docker+["exec",name,"python","-B","-c","import os;[os.makedirs('/ue/'+p,exist_ok=False) for p in ['wheels','tmp','output','cache','input']]"])
        self.job("copy-wheels",self.docker+["cp",self.cfg["archives"]+"/.",name+":/ue/wheels"],growth=379580121+64*1024**2,owner=name)
        for path,target in [(HERE.parent/"2026-11-09-cpu-packaging/requirements.cpu.lock","requirements.cpu.lock"),(HERE/"validate_install.py","validate_install.py"),(self.raw/"pre-install-hashes.json","expected.json")]:
            self.capture(self.docker+["cp",str(path),name+":/ue/"+target])
        return self.finish_install()

    def finish_install(self):
        name=self.cfg["prefix"]+"-install";volume=self.cfg["volume"]
        assert json.loads((self.raw/"runtime-complete.json").read_text())["gate"]=="PASS"
        v=json.loads(self.capture(self.docker+["volume","inspect",volume]).stdout)[0]
        assert v["Labels"]["understanding-engine.run"]==self.cfg["prefix"]
        container=json.loads(self.capture(self.docker+["inspect",name]).stdout)[0]
        assert container["State"]["Running"] and container["HostConfig"]["NetworkMode"]=="none"
        assert container["HostConfig"]["ReadonlyRootfs"]
        assert len(container["Mounts"])==1 and container["Mounts"][0]["Name"]==volume
        self.capture(self.docker+["exec",name,"python","-B","-c","from pathlib import Path;assert not Path('/ue/candidate').exists();assert not Path('/ue/install-report.json').exists();assert len(list(Path('/ue/wheels').glob('*.whl')))==103"])
        probe="""import os,json
def size(p):
 total=0
 for root,dirs,files in os.walk(p,followlinks=False):
  for n in files:
   try:total+=os.lstat(os.path.join(root,n)).st_blocks*512
   except FileNotFoundError:pass
 return total
s=os.statvfs('/ue');print(json.dumps({'guest_available_bytes':s.f_bavail*s.f_frsize,'tmp_allocated_bytes':size('/ue/tmp'),'candidate_allocated_bytes':size('/ue/candidate')}))
"""
        pip=["exec",name,"python","-B","-m","pip","--isolated","install","--target","/ue/candidate",
             "--no-deps","--no-index","--no-cache-dir","--no-compile","--only-binary=:all:","--require-hashes",
             "--find-links","/ue/wheels","--report","/ue/install-report.json","-r","/ue/requirements.cpu.lock"]
        installed=self.job("candidate-install",self.docker+pip,timeout=300,growth=1318440960+656220160+128*1024**2,owner=name,guest_probe=probe)
        return self.check_imports()

    def check_imports(self):
        name=self.cfg["prefix"]+"-install";volume=self.cfg["volume"]
        v=json.loads(self.capture(self.docker+["volume","inspect",volume]).stdout)[0]
        assert v["Labels"]["understanding-engine.run"]==self.cfg["prefix"]
        info=json.loads(self.capture(self.docker+["inspect",name]).stdout)[0]
        assert info["HostConfig"]["NetworkMode"]=="none" and not info["State"]["OOMKilled"]
        if not info["State"]["Running"]:self.capture(self.docker+["start",name])
        self.capture(self.docker+["exec",name,"python","-B","-c","from pathlib import Path;assert Path('/ue/candidate').is_dir();assert Path('/ue/install-report.json').is_file()"])
        self.capture(["/opt/homebrew/bin/colima","-p","ue006b","ssh","--","sync"])
        checked=self.job("import-check-complete",self.docker+["exec",name,"python","-B","/ue/validate_install.py"],timeout=90,growth=512*1024**2,owner=name)
        for filename in ["install-report.json","import-report.json"]:
            self.capture(self.docker+["cp",name+":/ue/"+filename,str(self.raw/filename)])
        report=json.loads((self.raw/"import-report.json").read_text())
        info=json.loads(self.capture(self.docker+["inspect",name]).stdout)[0]
        self.capture(self.docker+["stop","-t","1",name])
        if report["gate"]!="PASS":raise ValueError("Installation/import gate failed")
        installed=json.loads((self.raw/"candidate-install.resources.json").read_text())
        write(self.raw/"installation-complete.json",{"gate":"PASS","report":report,"install_resources":installed,
              "import_resources":checked,"container_inspect":info,"retained_storage":self.snapshot(),"guest_filesystems":self.guest()})
        print(json.dumps({"installation_gate":"PASS","packages":len(report["installed"]),"candidate_allocated_bytes":report["candidate_allocated_bytes"],"python":report["python"],"imports":report["imports"]}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw",required=True)
    parser.add_argument("--phase",choices=["runtime","install","finish-install","check-imports"],required=True)
    args=parser.parse_args()
    c=Control(args.raw)
    try:getattr(c,args.phase.replace("-","_"))()
    except Exception as exc:
        write(c.raw/(args.phase+"-failure.json"),{"type":type(exc).__name__,"error":str(exc),"storage":c.snapshot(enforce=False)})
        raise
