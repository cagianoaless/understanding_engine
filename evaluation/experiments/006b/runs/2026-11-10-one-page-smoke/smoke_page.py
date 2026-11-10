"""Exactly one page; all neural imports stay inside main(), in the container."""

import hashlib
import json
import os
from pathlib import Path
import threading
import time
import traceback


PAGE=6
PDF_SHA="bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"
REVISION="8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
DISABLED=["do_ocr","do_table_structure","do_code_enrichment","do_formula_enrichment",
          "do_picture_classification","do_picture_description","do_chart_extraction",
          "enable_remote_services","allow_external_plugins"]


def assert_cgroup(values):
    assert int(values['memory.max'])<=4294967296
    assert int(values['memory.swap.max'])==0
    quota,period=values['cpu.max'].split()
    assert quota!='max' and int(quota)<=4*int(period)


def single_batch(batch, seen):
    assert len(batch)==1 and batch[0].metadata.get('page_no')==PAGE,'Unexpected page/batch'
    assert not seen,'Second model prediction forbidden'
    seen.append({'page_no':PAGE,'image_size':list(batch[0].image.size)})


def cgroup():
    names=['memory.max','memory.swap.max','cpu.max','memory.current','memory.peak','memory.events','cpu.stat']
    return {n:(Path('/sys/fs/cgroup')/n).read_text().strip() for n in names}


def main():
    output=Path('/ue/output');started=time.perf_counter();initial=cgroup();assert_cgroup(initial)
    assert len(os.sched_getaffinity(0))<=4
    assert not Path('/var/run/docker.sock').exists() and not Path('/Users').exists()
    source=Path('/ue/input/original.pdf');assert hashlib.sha256(source.read_bytes()).hexdigest()==PDF_SHA
    done=threading.Event()
    def monitor():
        with (output/'cgroup-samples.jsonl').open('x') as stream:
            while not done.is_set():
                stream.write(json.dumps({'elapsed_seconds':time.perf_counter()-started,**cgroup()})+'\n');stream.flush()
                done.wait(0.1)
    worker=threading.Thread(target=monitor,daemon=True);worker.start()
    record={'source_pdf_sha256':PDF_SHA,'page_range':[PAGE,PAGE],'heron_revision':REVISION,
            'initial_cgroup':initial,'inference_network':'none','ocr':False,'source_character_crosswalk':None,
            'annotation_status':'agent_visual_checked','independent_human_verifications':0}
    seen=[]
    try:
        import torch
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        assert torch.__version__=='2.15.0+cpu' and torch.version.cuda is None
        from docling.document_converter import DocumentConverter,PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
        from docling.models.inference_engines.object_detection.transformers_engine import TransformersObjectDetectionEngine
        original=TransformersObjectDetectionEngine.predict_batch
        def guarded(self,batch):
            if batch:single_batch(batch,seen)
            return original(self,batch)
        TransformersObjectDetectionEngine.predict_batch=guarded
        options=PdfPipelineOptions()
        for name in DISABLED:
            assert name in type(options).model_fields,name
            setattr(options,name,False)
        options.artifacts_path=Path('/ue/artifacts')
        options.accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4)
        assert options.layout_options.model_spec.repo_id=='docling-project/docling-layout-heron'
        options.layout_options.model_spec.revision=REVISION
        options.layout_options.engine_options.compile_model=False
        (output/'pipeline-options.json').write_text(options.model_dump_json(indent=2)+'\n')
        converter=DocumentConverter(allowed_formats=[InputFormat.PDF],format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
        convert_started=time.perf_counter()
        result=converter.convert(source,page_range=(PAGE,PAGE),raises_on_error=True)
        record['conversion_wall_seconds']=time.perf_counter()-convert_started
        assert len(seen)==1 and len(result.pages)==1 and result.pages[0].page_no==PAGE
        document=result.document
        (output/'docling.json').write_text(json.dumps(document.export_to_dict(),ensure_ascii=False,indent=2)+'\n')
        (output/'page.md').write_text(document.export_to_markdown())
        items=[]
        for index,(item,level) in enumerate(document.iterate_items(with_groups=False)):
            items.append({'order_index':index,'self_ref':item.self_ref,'label':str(item.label.value),
                          'text':getattr(item,'text',None),'level':level,
                          'provenance':[p.model_dump(mode='json') for p in getattr(item,'prov',[])]})
        (output/'items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
        page=result.pages[0]
        (output/'layout.json').write_text(page.predictions.layout.model_dump_json(indent=2)+'\n')
        record.update(status=str(result.status.value),page_numbers=[p.page_no for p in result.pages],
                      item_count=len(items),model_prediction_batches=seen,
                      torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),
                      errors=[e.model_dump(mode='json') for e in result.errors],
                      coordinate_caveat='Native Docling provenance and layout coordinates preserved with their own origin metadata; no mapping to Structure0.2 character IDs, crop or rotation transforms is asserted.')
    except Exception as exc:
        record.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),model_prediction_batches=seen)
        raise
    finally:
        done.set();worker.join(timeout=2)
        record.update(total_wall_seconds=time.perf_counter()-started,final_cgroup=cgroup())
        (output/'smoke-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(record,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
