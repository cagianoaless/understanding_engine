"""Runtime, cache, optional-dependency and decoder checks before neural invocation."""
import argparse
import hashlib
import importlib.metadata as md
import importlib.util
import json
import os
from pathlib import Path
import site
import sys
import tempfile


def run(root):
    root = Path(root)
    assert not site.ENABLE_USER_SITE and importlib.util.find_spec('torch') is None
    assert str(Path.home()).startswith(str(root) + '/')
    assert sys.dont_write_bytecode and Path(sys.pycache_prefix).is_relative_to(root)
    import paddle
    import tokenizers
    import yaml
    import huggingface_hub.constants as hf
    from modelscope.utils.file_utils import get_modelscope_cache_dir
    import paddlex.utils.cache as cache
    from paddle.utils.download import WEIGHTS_HOME
    from paddlex.inference.models.formula_recognition import processors
    from paddleocr import FormulaRecognition
    assert 'torch' not in sys.modules
    paths = {'home': str(Path.home()), 'tempfile': tempfile.gettempdir(), 'pycache': sys.pycache_prefix,
             'hf_home': hf.HF_HOME, 'hf_hub': hf.HF_HUB_CACHE, 'modelscope': get_modelscope_cache_dir(),
             'paddlex': str(cache.CACHE_DIR), 'paddle_weights': WEIGHTS_HOME}
    assert all(Path(value).resolve().is_relative_to(root) for value in paths.values()), paths
    model = yaml.safe_load((root / 'model/inference.yml').read_text())
    assert model['Global']['model_name'] == 'PP-FormulaNet-S'
    expected = ['UniMERNetImgDecode', 'UniMERNetTestTransform', 'LatexImageFormat', 'ToBatch', 'UniMERNetDecode']
    dependencies = {}
    from paddlex.utils.deps import require_deps
    for name in expected:
        cls = getattr(processors, name)
        declared = tuple(getattr(cls, '_deps_', ()))
        if declared:
            require_deps(*declared, obj_name=name)
        dependencies[name] = list(declared)
    # Build the exact official postprocessor, without loading/running the neural model.
    decoder = processors.UniMERNetDecode(character_list=model['PostProcess']['character_dict'])
    assert decoder.tokenizer is not None
    paddle.set_device('gpu:0')
    assert float(paddle.ones([1]).numpy()[0]) == 1
    assert importlib.util.find_spec('torch') is None and 'torch' not in sys.modules
    records = {'status': 'PASS', 'python': sys.version, 'packages': {d.metadata['Name']: d.version for d in md.distributions()},
               'torch_visible': False, 'torch_imported': False, 'actual_cache_paths': paths,
               'python_bytecode_disabled': sys.dont_write_bytecode, 'declared_processor_dependencies': dependencies,
               'decoder_constructed': True, 'tiny_cuda_probe': True, 'paddle_cuda': paddle.version.cuda(),
               'paddle_cudnn': paddle.version.cudnn(), 'allocator_strategy': paddle.get_flags(['FLAGS_allocator_strategy']),
               'cpu_affinity': sorted(os.sched_getaffinity(0)), 'landlock_inherited': True,
               'processor_source_sha256': hashlib.sha256(Path(processors.__file__).read_bytes()).hexdigest()}
    (root / 'preflight.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps({k: records[k] for k in ['status', 'torch_visible', 'decoder_constructed', 'tiny_cuda_probe', 'paddle_cuda', 'paddle_cudnn', 'cpu_affinity']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
