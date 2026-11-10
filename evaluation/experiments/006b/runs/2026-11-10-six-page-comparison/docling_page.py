"""One of the six authorized pages, unchanged PR15 model options, no network."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import threading
import time
import traceback

REVISION = '8f39ad3c0b4c58e9c2d2c84a38465abf757272d8'
ALLOWED = {
    'bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697': {6, 9},
    '5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e': {6, 10},
    '6b5ce3dba2ef7454ad0868ad733a64b4ac89bcd98307773fad1e0e977caaa013': {15, 19}}
DISABLED = ['do_ocr', 'do_table_structure', 'do_code_enrichment', 'do_formula_enrichment',
            'do_picture_classification', 'do_picture_description', 'do_chart_extraction',
            'enable_remote_services', 'allow_external_plugins']
MODEL = {
    'config.json': 'fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d',
    'preprocessor_config.json': 'cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1',
    'model.safetensors': '00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c'}


def cgroup():
    return {n: (Path('/sys/fs/cgroup')/n).read_text().strip() for n in
            ['memory.max', 'memory.swap.max', 'cpu.max', 'memory.current', 'memory.peak', 'memory.events', 'cpu.stat']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--page', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output; output.mkdir(exist_ok=False)
    started = time.perf_counter(); initial = cgroup()
    assert int(initial['memory.max']) <= 4294967296 and initial['memory.swap.max'] == '0'
    quota, period = initial['cpu.max'].split()
    assert quota != 'max' and int(quota) <= 4*int(period)
    assert len(os.sched_getaffinity(0)) <= 4
    assert not Path('/var/run/docker.sock').exists() and not Path('/Users').exists()
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    assert args.page in ALLOWED[digest]
    for name, expected in MODEL.items():
        assert hashlib.sha256((Path('/ue/artifacts/docling-project--docling-layout-heron')/name).read_bytes()).hexdigest() == expected
    for name, version in [('docling', '2.148.0'), ('torch', '2.15.0+cpu'), ('torchvision', '0.29.2+cpu')]:
        assert importlib.metadata.version(name) == version
    done = threading.Event()

    def monitor():
        with (output/'cgroup-samples.jsonl').open('x') as stream:
            while not done.is_set():
                stream.write(json.dumps({'elapsed_seconds': time.perf_counter()-started, **cgroup()})+'\n')
                stream.flush(); done.wait(.1)
    worker = threading.Thread(target=monitor, daemon=True); worker.start()
    record = {'source_pdf_sha256': digest, 'page_range': [args.page, args.page], 'heron_revision': REVISION,
              'initial_cgroup': initial, 'inference_network': 'none', 'ocr': False}
    seen = []
    try:
        import torch
        torch.set_num_threads(4); torch.set_num_interop_threads(1)
        assert torch.__version__ == '2.15.0+cpu' and torch.version.cuda is None
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        from docling.models.inference_engines.object_detection.transformers_engine import TransformersObjectDetectionEngine
        original = TransformersObjectDetectionEngine.predict_batch

        def guarded(self, batch):
            if batch:
                assert len(batch) == 1 and batch[0].metadata.get('page_no') == args.page
                assert not seen, 'Second nonempty inference batch forbidden'
                info = {'page_no': args.page, 'image_size': list(batch[0].image.size)}
                seen.append(info); begin = time.perf_counter()
                result = original(self, batch)
                info['predict_batch_seconds'] = time.perf_counter()-begin
                return result
            return original(self, batch)
        TransformersObjectDetectionEngine.predict_batch = guarded
        options = PdfPipelineOptions()
        for name in DISABLED:
            assert name in type(options).model_fields
            setattr(options, name, False)
        options.artifacts_path = Path('/ue/artifacts')
        options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=4)
        assert options.layout_options.model_spec.repo_id == 'docling-project/docling-layout-heron'
        options.layout_options.model_spec.revision = REVISION
        options.layout_options.engine_options.compile_model = False
        (output/'pipeline-options.json').write_text(options.model_dump_json(indent=2)+'\n')
        converter = DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        begin = time.perf_counter()
        result = converter.convert(args.source, page_range=(args.page, args.page), raises_on_error=True)
        record['conversion_wall_seconds'] = time.perf_counter()-begin
        assert len(seen) == 1 and len(result.pages) == 1 and result.pages[0].page_no == args.page
        document = result.document
        (output/'docling.json').write_text(json.dumps(document.export_to_dict(), ensure_ascii=False, indent=2)+'\n')
        (output/'page.md').write_text(document.export_to_markdown())
        items = []
        for index, (item, level) in enumerate(document.iterate_items(with_groups=False)):
            items.append({'order_index': index, 'self_ref': item.self_ref, 'label': str(item.label.value),
                'text': getattr(item, 'text', None), 'level': level,
                'provenance': [p.model_dump(mode='json') for p in getattr(item, 'prov', [])]})
        (output/'items.json').write_text(json.dumps(items, ensure_ascii=False, indent=2)+'\n')
        (output/'layout.json').write_text(result.pages[0].predictions.layout.model_dump_json(indent=2)+'\n')
        record.update(status=str(result.status.value), item_count=len(items), model_prediction_batches=seen,
            torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
            errors=[e.model_dump(mode='json') for e in result.errors])
    except Exception as exc:
        record.update(status='FAILED', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        done.set(); worker.join(timeout=2)
        record.update(total_wall_seconds=time.perf_counter()-started, final_cgroup=cgroup())
        (output/'execution.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
