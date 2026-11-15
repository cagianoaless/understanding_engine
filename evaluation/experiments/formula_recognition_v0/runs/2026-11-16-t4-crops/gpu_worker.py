"""One frozen crop through pinned Docling's neural crop interface; no references."""
import argparse
import functools
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import resource
import time
import traceback

REVISION = 'ecedbe111d15c2dc60bfd4a823cbe80127b58af4'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def verify_inputs(root, identifier):
    manifest = json.loads((root / 'inference-inputs.json').read_text())
    assert manifest['reference_inputs_uploaded'] is False
    assert manifest['model']['revision'] == REVISION
    row = next(r for r in manifest['crops'] if r['id'] == identifier)
    crop = root / 'crops' / (identifier + '.png')
    assert crop.stat().st_size == row['bytes'] and sha(crop) == row['sha256']
    model = root / 'artifacts' / 'docling-project--CodeFormulaV2'
    for file in manifest['model']['files']:
        path = model / file['file']
        assert path.is_file() and path.stat().st_size == file['bytes']
        assert sha(path) == file['sha256']
    return row, crop


def run(root, identifier, output):
    output.mkdir(exist_ok=False)
    started = time.perf_counter()
    record = {'schema_version': 'formula-gpu-prediction.1', 'id': identifier,
              'status': 'STARTING', 'model_revision': REVISION,
              'generated_calls': [], 'source_truth_replaced': False,
              'cpu_memory_enforcement': 'No experiment-specific cgroup limit; remote native process RSS measured',
              'reference_inputs': False}

    def event(name, **data):
        with (output / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': name, 'elapsed': time.perf_counter() - started, **data}) + '\n')

    try:
        row, crop = verify_inputs(root, identifier)
        record.update(input=row, input_crop_sha256=sha(crop))
        assert md.version('docling') == '2.148.0'
        import torch
        from PIL import Image
        from docling.datamodel.pipeline_options import CodeFormulaVlmOptions
        from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
        from docling.models.inference_engines.vlm.transformers_engine import TransformersVlmEngine
        from docling.models.inference_engines.vlm import VlmEngineInput

        assert torch.cuda.is_available() and torch.cuda.get_device_capability(0) == (7, 5)
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.cuda.reset_peak_memory_stats()
        record['versions'] = {n: md.version(n) for n in ['docling', 'docling-slim', 'docling-core', 'torch', 'torchvision', 'transformers', 'accelerate', 'Pillow', 'tokenizers', 'safetensors']}
        engine_options = TransformersVlmEngineOptions(compile_model=False, torch_dtype='float16', trust_remote_code=False)
        options = CodeFormulaVlmOptions.from_preset('codeformulav2', engine_options=engine_options, extract_code=False, extract_formulas=True)
        options.model_spec = options.model_spec.model_copy(deep=True)
        options.model_spec.revision = REVISION
        accelerator = AcceleratorOptions(device=AcceleratorDevice.CUDA, num_threads=4, cuda_use_flash_attention2=False)
        write(output / 'options.json', options.model_dump(mode='json'))
        record['configuration'] = {'dtype': 'float16', 'max_new_tokens': 2048, 'temperature': 0, 'batch_size': 1, 'compile': False, 'seed': 0, 'tf32': False, 'prompt': '<formula>', 'deterministic_algorithms': 'warn_only; generation greedy', 'checkpoint_weights_modified': False}
        initialize = TransformersVlmEngine.initialize

        def measured_initialize(self):
            event('initialize_start')
            before = time.perf_counter()
            result = initialize(self)
            torch.cuda.synchronize()
            record['engine_initialization_seconds'] = time.perf_counter() - before
            dtypes = sorted({str(p.dtype) for p in self.vlm_model.parameters() if p.is_floating_point()})
            assert dtypes == ['torch.float16'], dtypes
            record['parameter_dtypes'] = dtypes
            record['device'] = self.device
            original = self.vlm_model.generate

            @functools.wraps(original)
            def observed_generate(*args, **kwargs):
                cfg = kwargs['generation_config']
                assert cfg.do_sample is False and cfg.max_new_tokens == 2048
                torch.cuda.synchronize()
                tick = time.perf_counter()
                event('generation_start')
                value = original(*args, **kwargs)
                torch.cuda.synchronize()
                seconds = time.perf_counter() - tick
                count = int(kwargs['input_ids'].shape[1])
                ids = value[0, count:].tolist()
                write(output / 'generated-token-ids.json', ids)
                item = {'seconds': seconds, 'input_tokens': count, 'generated_tokens': len(ids), 'last_token_id': ids[-1] if ids else None, 'eos_token_id': cfg.eos_token_id, 'token_cap_reached': len(ids) >= cfg.max_new_tokens}
                record['generated_calls'].append(item)
                event('generation_complete', **item)
                return value

            self.vlm_model.generate = observed_generate
            event('initialize_complete', seconds=record['engine_initialization_seconds'])
            return result

        TransformersVlmEngine.initialize = measured_initialize
        before = time.perf_counter()
        stage = CodeFormulaVlmModel(enabled=True, enable_remote_services=False, artifacts_path=root / 'artifacts', options=options, accelerator_options=accelerator)
        torch.cuda.synchronize()
        record['stage_initialization_seconds'] = time.perf_counter() - before
        extra = dict(skip_special_tokens=False, custom_stopping_criteria=[stage._repetition_stopper])
        with Image.open(crop) as image:
            assert list(image.size) == row['image_dimensions']
            before = time.perf_counter()
            event('predictor_invoked', input_sha256=row['sha256'])
            predictions = stage.engine.predict_batch([VlmEngineInput(image=image.convert('RGB'), prompt='<formula>', temperature=0, max_new_tokens=2048, extra_generation_config=extra)])
            torch.cuda.synchronize()
            record['recognition_seconds'] = time.perf_counter() - before
        assert len(predictions) == 1 and record['generated_calls']
        raw = predictions[0].text
        clean = stage._post_process([raw])[0]
        if stage._repetition_stopper:
            clean = stage._repetition_stopper.strip(clean)
        record.update(status='RETURNED', raw_model_output=raw, cleaned_latex=clean,
                      native_output=predictions[0].model_dump(mode='json'), backend_fallback_possible=False)
        event('predictor_returned')
    except Exception as exc:
        record.update(status='FAILED', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        event('failed', error_type=type(exc).__name__)
        raise
    finally:
        record['total_seconds'] = time.perf_counter() - started
        record['peak_process_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        try:
            import torch
            record.update(peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(), peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(), final_gpu_allocated_bytes=torch.cuda.memory_allocated(), final_gpu_reserved_bytes=torch.cuda.memory_reserved())
        except Exception:
            pass
        write(output / 'prediction.json', record)
        print(json.dumps({k: record.get(k) for k in ['id', 'status', 'raw_model_output', 'cleaned_latex', 'recognition_seconds', 'peak_gpu_allocated_bytes', 'peak_gpu_reserved_bytes', 'error']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.id, args.output)
