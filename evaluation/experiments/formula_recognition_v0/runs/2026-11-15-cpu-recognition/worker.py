"""One bounded crop/page, existing pinned candidate; no evaluation references."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import threading
import time
import traceback

REVISION='ecedbe111d15c2dc60bfd4a823cbe80127b58af4'
HERON='8f39ad3c0b4c58e9c2d2c84a38465abf757272d8'


def dump(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def cgroup():
    return {n:(Path('/sys/fs/cgroup')/n).read_text().strip() for n in
            ['memory.max','memory.swap.max','cpu.max','memory.current','memory.peak','memory.events','cpu.stat']}


def verify_limits(values):
    assert 0<int(values['memory.max'])<=4*1024**3 and values['memory.swap.max']=='0'
    q,p=values['cpu.max'].split();assert q!='max' and 0<int(q)<=4*int(p) and int(p)>0
    assert 1<=len(os.sched_getaffinity(0))<=4
    assert not Path('/var/run/docker.sock').exists() and not Path('/Users').exists()


def main():
    p=argparse.ArgumentParser();p.add_argument('--task',type=Path,required=True);a=p.parse_args()
    task=json.loads(a.task.read_text());out=Path(task['output']);out.mkdir(exist_ok=False)
    started=time.perf_counter();initial=cgroup();verify_limits(initial);done=threading.Event()
    record=dict(task=task,model_revision=REVISION,initial_cgroup=initial,model_initializations=[],
                predictor_calls=[],generate_calls=[],status='STARTING',network='none',source_unicode_replaced=False)
    def event(kind,**data):
        with (out/'events.jsonl').open('a') as f:f.write(json.dumps(dict(event=kind,elapsed=time.perf_counter()-started,**data))+'\n')
    def monitor():
        with (out/'cgroup-samples.jsonl').open('x') as f:
            while not done.is_set():
                f.write(json.dumps(dict(elapsed=time.perf_counter()-started,**cgroup()))+'\n');f.flush();done.wait(.1)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        manifest=json.loads(Path('/run/model-manifest.json').read_text())
        for row in manifest:
            path=Path('/run/artifacts/docling-project--CodeFormulaV2')/row['file']
            assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
        for name,version in [('docling','2.148.0'),('torch','2.15.0+cpu'),('torchvision','0.29.2+cpu')]:
            assert importlib.metadata.version(name)==version
        event('neural_import_start')
        import torch
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0)
        assert torch.version.cuda is None
        from docling.datamodel.pipeline_options import CodeFormulaVlmOptions,PdfPipelineOptions
        from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
        from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
        from docling.models.inference_engines.vlm.transformers_engine import TransformersVlmEngine
        from docling.models.inference_engines.vlm import VlmEngineInput
        accelerator=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4)
        options=CodeFormulaVlmOptions.from_preset('codeformulav2',
            engine_options=TransformersVlmEngineOptions(compile_model=False),extract_code=False,extract_formulas=True)
        options.model_spec=options.model_spec.model_copy(deep=True);options.model_spec.revision=REVISION
        assert options.expansion_factor==.18 and options.stop_on_repetition
        CodeFormulaVlmModel.elements_batch_size=1
        dump(out/'formula-options.json',options.model_dump(mode='json'))
        initialize=TransformersVlmEngine.initialize
        def measured_initialize(self):
            row=dict(start_seconds=time.perf_counter()-started);record['model_initializations'].append(row);event('model_initialization_start')
            tick=time.perf_counter()
            try:
                result=initialize(self)
                row.update(success=True,seconds=time.perf_counter()-tick,device=self.device)
                model=self.vlm_model;original_generate=model.generate
                def measured_generate(*args,**kwargs):
                    call=dict(start_seconds=time.perf_counter()-started);record['generate_calls'].append(call);event('generate_start',call=len(record['generate_calls']))
                    t=time.perf_counter()
                    try:
                        value=original_generate(*args,**kwargs)
                        call.update(seconds=time.perf_counter()-t,success=True)
                        ids=value.tolist();dump(out/('generation-'+str(len(record['generate_calls']))+'.json'),dict(token_ids=ids,input_token_count=int(kwargs['input_ids'].shape[1])))
                        event('generate_success',seconds=call['seconds']);return value
                    except Exception as exc:
                        call.update(success=False,seconds=time.perf_counter()-t,error_type=type(exc).__name__,error=str(exc));event('generate_failed',error_type=type(exc).__name__);raise
                model.generate=measured_generate
                event('model_initialization_success',seconds=row['seconds']);return result
            except Exception as exc:
                row.update(success=False,seconds=time.perf_counter()-tick,error_type=type(exc).__name__,error=str(exc));event('model_initialization_failed',error_type=type(exc).__name__);raise
        TransformersVlmEngine.initialize=measured_initialize
        predict=TransformersVlmEngine.predict_batch
        def measured_predict(self,batch):
            if not batch:return predict(self,batch)
            assert len(batch)==1,'Batch must be one'
            row=dict(start_seconds=time.perf_counter()-started,prompt=batch[0].prompt,temperature=batch[0].temperature,
                     max_new_tokens=batch[0].max_new_tokens,image_size=list(batch[0].image.size));record['predictor_calls'].append(row)
            crop=out/('engine-crop-'+str(len(record['predictor_calls']))+'.png');batch[0].image.save(crop)
            row['crop_sha256']=sha(crop);row['crop_file']=crop.name
            assert row['prompt']=='<formula>' and row['temperature']==0 and row['max_new_tokens']==2048
            event('predictor_start',call=len(record['predictor_calls']));tick=time.perf_counter()
            try:
                result=predict(self,batch);row.update(success=True,seconds=time.perf_counter()-tick,outputs=[v.model_dump(mode='json') for v in result]);event('predictor_success',seconds=row['seconds'])
                dump(out/('predictor-'+str(len(record['predictor_calls']))+'.json'),row);return result
            except Exception as exc:
                row.update(success=False,seconds=time.perf_counter()-tick,error_type=type(exc).__name__,error=str(exc));dump(out/('predictor-'+str(len(record['predictor_calls']))+'.json'),row);event('predictor_failed',error_type=type(exc).__name__);raise
        TransformersVlmEngine.predict_batch=measured_predict
        if task['scenario']=='crop':
            from PIL import Image
            crop=Path(task['input']);assert sha(crop)==task['input_sha256'];record['input_crop_sha256']=sha(crop)
            begin=time.perf_counter();stage=CodeFormulaVlmModel(enabled=True,enable_remote_services=False,artifacts_path=Path('/run/artifacts'),options=options,accelerator_options=accelerator)
            record['stage_construction_seconds']=time.perf_counter()-begin
            extra=dict(skip_special_tokens=False,custom_stopping_criteria=[stage._repetition_stopper])
            with Image.open(crop) as im:
                begin=time.perf_counter();result=stage.engine.predict_batch([VlmEngineInput(image=im.convert('RGB'),prompt='<formula>',temperature=0,max_new_tokens=2048,extra_generation_config=extra)])
                record['recognition_wall_seconds']=time.perf_counter()-begin
            assert len(result)==1 and record['generate_calls'] and all(c.get('success') for c in record['generate_calls'])
            raw=result[0].text;clean=stage._post_process([raw])[0]
            if stage._repetition_stopper:clean=stage._repetition_stopper.strip(clean)
            record.update(raw_generated_text=raw,cleaned_latex=clean,engine_output=result[0].model_dump(mode='json'),no_backend_text_fallback_possible=True)
        else:
            from docling.document_converter import DocumentConverter,PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            source=Path(task['input']);assert sha(source)==task['input_sha256']
            opts=PdfPipelineOptions()
            for field in ['do_ocr','do_table_structure','do_code_enrichment','do_picture_classification','do_picture_description','do_chart_extraction','enable_remote_services','allow_external_plugins']:
                setattr(opts,field,False)
            opts.do_formula_enrichment=True;opts.code_formula_options=options;opts.artifacts_path=Path('/run/artifacts');opts.accelerator_options=accelerator
            opts.layout_options.model_spec.revision=HERON;opts.layout_options.engine_options.compile_model=False
            dump(out/'pipeline-options.json',opts.model_dump(mode='json'))
            converter=DocumentConverter(allowed_formats=[InputFormat.PDF],format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)})
            begin=time.perf_counter();result=converter.convert(source,page_range=(task['page'],task['page']),raises_on_error=True)
            record['conversion_seconds']=time.perf_counter()-begin
            assert len(result.pages)==1 and result.pages[0].page_no==task['page']
            dump(out/'docling.json',result.document.export_to_dict())
            items=[]
            for i,(item,level) in enumerate(result.document.iterate_items(with_groups=False)):
                items.append(dict(order_index=i,self_ref=item.self_ref,label=str(item.label.value),text=getattr(item,'text',None),level=level,
                                  provenance=[p.model_dump(mode='json') for p in getattr(item,'prov',[])]))
            dump(out/'items.json',items);dump(out/'layout.json',result.pages[0].predictions.layout.model_dump(mode='json'))
            record.update(conversion_status=str(result.status.value),formulas=[v for v in items if v['label']=='formula'],errors=[e.model_dump(mode='json') for e in result.errors])
            record['formula_backend_fallback_detected']=any(not c.get('success') for c in record['predictor_calls'])
        record.update(status='SUCCESS',threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads())
    except Exception as exc:
        record.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc());event('worker_failed',error_type=type(exc).__name__);raise
    finally:
        done.set();thread.join(timeout=2);record.update(total_seconds=time.perf_counter()-started,final_cgroup=cgroup());dump(out/'execution.json',record)
        print(json.dumps(record,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
