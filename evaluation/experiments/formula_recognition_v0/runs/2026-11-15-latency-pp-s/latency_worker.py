"""At most two explicitly authorized latency diagnostics, no accuracy pooling."""
import argparse
import functools
import json
import os
from pathlib import Path
import runpy
import threading
import time
import traceback

OLD=runpy.run_path('/run/worker.py') if Path('/run/worker.py').exists() else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--max-new-tokens',type=int,choices=[64,256],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out;out.mkdir(exist_ok=False);started=time.perf_counter();done=threading.Event()
    assert OLD is not None
    dump,sha,cgroup=OLD['dump'],OLD['sha'],OLD['cgroup'];initial=cgroup();OLD['verify_limits'](initial)
    record=dict(status='STARTING',purpose='LATENCY_DIAGNOSTIC_NOT_FROZEN_2048_ACCURACY_RUN',max_new_tokens=a.max_new_tokens,
                initial_cgroup=initial,forward_calls=[],generation_entered=False,returned=False,streamed_ids=[])
    def event(kind,**data):
        with (out/'events.jsonl').open('a') as f:f.write(json.dumps(dict(event=kind,elapsed=time.perf_counter()-started,**data))+'\n')
    def monitor():
        with (out/'cgroup.jsonl').open('x') as f:
            while not done.is_set():
                f.write(json.dumps(dict(elapsed=time.perf_counter()-started,**cgroup()))+'\n');f.flush();done.wait(.1)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        rows=json.loads(Path('/run/model-manifest.json').read_text())
        for r in rows:assert sha(Path('/run/artifacts/docling-project--CodeFormulaV2')/r['file'])==r['sha256']
        crop=Path('/run/crops/attn_fraction.png');assert sha(crop)=='9b9b3cccafa6e482c591d1ad81c52c4d7daade04b5e63a730af286b8508c1e9d'
        record['input_crop_sha256']=sha(crop)
        event('imports_start')
        import torch
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0);assert torch.__version__=='2.15.0+cpu' and torch.version.cuda is None
        from PIL import Image
        from transformers.generation.streamers import BaseStreamer
        from docling.datamodel.pipeline_options import CodeFormulaVlmOptions
        from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
        from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
        from docling.models.inference_engines.vlm import VlmEngineInput
        options=CodeFormulaVlmOptions.from_preset('codeformulav2',engine_options=TransformersVlmEngineOptions(compile_model=False),extract_code=False,extract_formulas=True)
        options.model_spec=options.model_spec.model_copy(deep=True);options.model_spec.revision=OLD['REVISION'];assert options.expansion_factor==.18
        dump(out/'options.json',options.model_dump(mode='json'));tick=time.perf_counter();event('load_start')
        stage=CodeFormulaVlmModel(enabled=True,enable_remote_services=False,artifacts_path=Path('/run/artifacts'),options=options,
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4))
        record['load_seconds']=time.perf_counter()-tick;event('load_success',seconds=record['load_seconds'])
        engine=stage.engine;model=engine.vlm_model;tokenizer=engine._get_tokenizer();record['parameter_dtype']=str(next(model.parameters()).dtype)
        original_forward=model.forward
        @functools.wraps(original_forward)
        def observed_forward(*args,**kwargs):
            i=len(record['forward_calls']);value=kwargs.get('input_ids');n=int(value.shape[-1]) if value is not None else None
            row=dict(index=i,phase='first_forward_prefill' if i==0 else 'subsequent_forward_decode',input_tokens=n,start=time.perf_counter()-started)
            record['forward_calls'].append(row);event('forward_start',**row);t=time.perf_counter()
            result=original_forward(*args,**kwargs);row['seconds']=time.perf_counter()-t;event('forward_end',index=i,seconds=row['seconds']);return result
        model.forward=observed_forward
        class Progress(BaseStreamer):
            def __init__(self):self.prompt=True
            def put(self,value):
                ids=value.tolist()
                if self.prompt:
                    self.prompt=False;record['prompt_token_count']=len(ids[0]) if ids and isinstance(ids[0],list) else len(ids);event('prompt_observed',tokens=record['prompt_token_count']);return
                if ids and isinstance(ids[0],list):assert len(ids)==1;ids=ids[0]
                record['streamed_ids'].extend(ids);text=tokenizer.decode(record['streamed_ids'],skip_special_tokens=False)
                partial=dict(tokens=len(record['streamed_ids']),token_ids=record['streamed_ids'],raw_partial_text=text,elapsed=time.perf_counter()-started,
                             incomplete=True,not_a_complete_recognition_result=True)
                tmp=out/'progress.tmp';dump(tmp,partial);tmp.replace(out/'progress.json');event('tokens_observed',tokens=len(record['streamed_ids']))
            def end(self):event('stream_end',tokens=len(record['streamed_ids']))
        original_generate=model.generate
        @functools.wraps(original_generate)
        def observed_generate(*args,**kwargs):
            assert kwargs['generation_config'].max_new_tokens==a.max_new_tokens
            record['effective_generation']=kwargs['generation_config'].to_dict();record['generation_entered']=True;event('generate_start')
            kwargs['streamer']=Progress()  # Observes emitted IDs only; never changes logits/stopping.
            return original_generate(*args,**kwargs)
        model.generate=observed_generate
        extra=dict(skip_special_tokens=False,custom_stopping_criteria=[stage._repetition_stopper])
        tick=time.perf_counter();event('predictor_start')
        with Image.open(crop) as image:
            outputs=engine.predict_batch([VlmEngineInput(image=image.convert('RGB'),prompt='<formula>',temperature=0,max_new_tokens=a.max_new_tokens,extra_generation_config=extra)])
        record['inference_seconds']=time.perf_counter()-tick;record['returned']=True;record['outputs']=[o.model_dump(mode='json') for o in outputs]
        raw=outputs[0].text;clean=stage._post_process([raw])[0]
        if stage._repetition_stopper:clean=stage._repetition_stopper.strip(clean)
        record.update(status='RETURNED',raw_text=raw,cleaned_latex=clean,stop_reason=outputs[0].stop_reason,
                      output_is_truncated=outputs[0].stop_reason=='length',complete_formula_correctness=None)
        event('predictor_return',seconds=record['inference_seconds'],stop_reason=outputs[0].stop_reason)
    except Exception as exc:
        record.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc());event('failure',error_type=type(exc).__name__);raise
    finally:
        done.set();thread.join(timeout=2);record.update(total_seconds=time.perf_counter()-started,final_cgroup=cgroup());dump(out/'execution.json',record)
        print(json.dumps(record,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
