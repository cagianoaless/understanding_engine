"""One pinned PP-FormulaNet-S crop call; clean interpreter, no references/Torch."""
import argparse
import hashlib
import importlib.util
import importlib.metadata as md
import json
from pathlib import Path
import resource
import site
import sys
import time
import traceback


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def verify(root, crop_root, identifier):
    manifest = json.loads((root / 'inputs.json').read_text())
    assert manifest['reference_inputs_uploaded'] is False
    assert manifest['model']['repo'] == 'PaddlePaddle/PP-FormulaNet-S'
    assert manifest['model']['revision'] == '0572450e501be9eb1b1cdb7e00fccf4b22fab4df'
    crop = next(r for r in manifest['crops'] if r['id'] == identifier)
    path = crop_root / (identifier + '.png')
    assert path.stat().st_size == crop['bytes'] and sha(path) == crop['sha256']
    acquired = json.loads((root / 'model-acquisition.json').read_text())
    assert acquired['revision'] == manifest['model']['revision']
    expected = {r['file']: r for r in manifest['model']['files']}
    for row in acquired['files']:
        assert row['bytes'] == expected[row['file']]['bytes']
        if expected[row['file']]['expected_sha256']:
            assert row['sha256'] == expected[row['file']]['expected_sha256']
        model = root / 'model' / row['file']
        assert model.stat().st_size == row['bytes'] and sha(model) == row['sha256']
    assert {r['file'] for r in acquired['files']} == {'inference.json', 'inference.pdiparams', 'inference.yml'}
    return manifest, crop, path


def run(root, crop_root, identifier, output):
    output.mkdir(exist_ok=False)
    start = time.perf_counter()
    record = {'schema_version': 'pp-formulanet-prediction.1', 'id': identifier, 'status': 'STARTING',
              'reference_inputs': False, 'raw_latex': None, 'source_unicode_replaced': False}

    def event(name, **data):
        with (output / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': name, 'elapsed': time.perf_counter() - start, **data}) + '\n')

    try:
        assert not site.ENABLE_USER_SITE and importlib.util.find_spec('torch') is None
        manifest, crop, path = verify(root, crop_root, identifier)
        record.update(input=crop, input_crop_sha256=sha(path), model_revision=manifest['model']['revision'])
        event('imports_start')
        import paddle
        import yaml
        from PIL import Image
        from paddleocr import FormulaRecognition
        assert 'torch' not in sys.modules and importlib.util.find_spec('torch') is None
        assert paddle.is_compiled_with_cuda()
        paddle.set_device('gpu:0')
        paddle.seed(0)
        paddle.device.cuda.reset_max_memory_allocated()
        paddle.device.cuda.reset_max_memory_reserved()
        model_config = yaml.safe_load((root / 'model/inference.yml').read_text())
        assert model_config['Global']['model_name'] == 'PP-FormulaNet-S'
        with Image.open(path) as image:
            assert list(image.size) == crop['image_dimensions']
        record['versions'] = {name: md.version(name) for name in ['paddlepaddle-gpu', 'paddleocr', 'paddlex', 'numpy', 'opencv-contrib-python', 'Pillow', 'modelscope', 'nvidia-nccl-cu12']}
        record['configuration'] = manifest['recognition_configuration']
        before = time.perf_counter()
        event('model_initialization_start')
        options = {k: v for k, v in manifest['recognition_configuration'].items() if k in ['model_name', 'device', 'enable_hpi', 'use_tensorrt', 'precision', 'enable_mkldnn', 'cpu_threads']}
        model = FormulaRecognition(model_dir=str(root / 'model'), **options)
        assert model._model_name == 'PP-FormulaNet-S'
        paddle.device.cuda.synchronize()
        record['model_initialization_seconds'] = time.perf_counter() - before
        record['predictor_type'] = type(model.paddlex_predictor).__name__
        event('model_initialization_complete', seconds=record['model_initialization_seconds'])
        event('predictor_invoked', batch_size=1, input_sha256=crop['sha256'])
        before = time.perf_counter()
        result = model.predict(input=str(path), batch_size=1)
        paddle.device.cuda.synchronize()
        record['recognition_seconds'] = time.perf_counter() - before
        assert len(result) == 1 and isinstance(result[0]['rec_formula'], str)
        native = result[0].json
        if isinstance(native, str):
            native = json.loads(native)
        write(output / 'native-result.json', native)
        record.update(status='RETURNED', raw_latex=result[0]['rec_formula'], native_result=native,
                      tokens=None, token_count_reason='Official crop API exposes decoded rec_formula, not raw token IDs',
                      extra_cleanup_applied=False, backend_fallback_possible=False)
        assert 'torch' not in sys.modules and importlib.util.find_spec('torch') is None
        event('predictor_returned', seconds=record['recognition_seconds'])
        # Relevant loaded libraries provide read-only isolation evidence, not loader overrides.
        record['loaded_cuda_libraries'] = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                                                if '/' in line and any(name in line for name in ['libnccl', 'libcudnn', 'libcublas', 'libcudart'])})
        record['torch_visible'] = False
        record['torch_imported'] = False
    except Exception as exc:
        record.update(status='FAILED', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        event('failed', error_type=type(exc).__name__)
        raise
    finally:
        record['total_seconds'] = time.perf_counter() - start
        record['peak_process_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        try:
            import paddle
            record['paddle_peak_allocated_bytes'] = paddle.device.cuda.max_memory_allocated()
            record['paddle_peak_reserved_bytes'] = paddle.device.cuda.max_memory_reserved()
            record['allocator_scope'] = 'Paddle tensor allocator; static inference/native-library allocations may not be fully represented; external process VRAM sampled separately'
        except Exception:
            pass
        write(output / 'prediction.json', record)
        print(json.dumps({k: record.get(k) for k in ['id', 'status', 'raw_latex', 'model_initialization_seconds', 'recognition_seconds', 'error']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--crop-root', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.crop_root, args.id, args.output)
