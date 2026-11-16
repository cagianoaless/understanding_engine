"""Unprivileged Linux write confinement; reads allowed, persistent writes owned-root only."""
import argparse
import ctypes
import glob
import json
import os
from pathlib import Path
import stat

WRITE_FILE = 1 << 1
WRITE_RIGHTS = WRITE_FILE | sum(1 << n for n in range(4, 15))


def validate_root(root):
    root = Path(root)
    assert root.is_absolute() and root.resolve(strict=True) == root
    status = root.lstat()
    assert stat.S_ISDIR(status.st_mode) and status.st_uid == os.getuid()
    assert stat.S_IMODE(status.st_mode) == 0o700 and not os.path.ismount(root)
    marker = root / '.experiment-owner.json'
    assert not marker.is_symlink()
    data = json.loads(marker.read_text())
    assert data['root'] == str(root) and data['uid'] == os.getuid()
    assert (data['device'], data['inode']) == (status.st_dev, status.st_ino)
    return data


def environment(root):
    root = Path(root)
    values = dict(os.environ)
    for key in ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']:
        values.pop(key, None)
    paths = {
        'HOME': 'home', 'XDG_CACHE_HOME': 'cache', 'XDG_CONFIG_HOME': 'config', 'XDG_DATA_HOME': 'data',
        'XDG_STATE_HOME': 'state', 'XDG_RUNTIME_DIR': 'run', 'HF_HOME': 'cache/hf', 'HF_HUB_CACHE': 'cache/hf/hub',
        'HUGGINGFACE_HUB_CACHE': 'cache/hf/hub', 'HF_ASSETS_CACHE': 'cache/hf/assets', 'HF_XET_CACHE': 'cache/hf/xet',
        'MODELSCOPE_CACHE': 'cache/modelscope', 'MODELSCOPE_MODULES_CACHE': 'cache/modelscope-modules',
        'PADDLE_HOME': 'cache/paddle', 'PADDLE_PDX_CACHE_HOME': 'cache/paddlex', 'PADDLEOCR_HOME': 'cache/paddleocr',
        'PIP_CACHE_DIR': 'cache/pip', 'UV_CACHE_DIR': 'cache/uv', 'UV_PYTHON_INSTALL_DIR': 'managed-python',
        'UV_TOOL_DIR': 'tools', 'UV_TOOL_BIN_DIR': 'bin', 'TMPDIR': 'tmp', 'TMP': 'tmp', 'TEMP': 'tmp',
        'PYTHONPYCACHEPREFIX': 'pycache', 'PYTHONUSERBASE': 'userbase', 'CUDA_CACHE_PATH': 'cache/cuda',
        'MPLCONFIGDIR': 'cache/matplotlib', 'NUMBA_CACHE_DIR': 'cache/numba', 'TORCH_HOME': 'cache/torch',
        'TRITON_CACHE_DIR': 'cache/triton',
    }
    for key, relative in paths.items():
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        values[key] = str(path)
    for key in ['PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST', 'UV_EXTRA_INDEX_URL']:
        values.pop(key, None)
    values.update({'PIP_INDEX_URL': 'https://pypi.org/simple', 'UV_INDEX_URL': 'https://pypi.org/simple',
                   'SSL_CERT_FILE': '/etc/ssl/certs/ca-certificates.crt', 'REQUESTS_CA_BUNDLE': '/etc/ssl/certs/ca-certificates.crt',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1', 'UV_PYTHON_DOWNLOADS': 'never',
                   'UV_LINK_MODE': 'copy', 'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PIP_CONFIG_FILE': '/dev/null',
                   'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '4',
                   'NUMEXPR_NUM_THREADS': '4', 'RAYON_NUM_THREADS': '4', 'TOKENIZERS_PARALLELISM': 'false',
                   'CUDA_VISIBLE_DEVICES': '0', 'FLAGS_allocator_strategy': 'auto_growth',
                   'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
                   'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True'})
    return values


def restrict(root, write_scope=None, allow_self_task_metadata=False):
    root = Path(root)
    validate_root(root)
    scope = Path(write_scope) if write_scope else root
    assert scope.resolve(strict=True).is_relative_to(root)
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError('Landlock ABI >=3 required; do not run unconfined')

    class Ruleset(ctypes.Structure):
        _fields_ = [('handled_access_fs', ctypes.c_uint64)]

    class Beneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]

    attr = Ruleset(WRITE_RIGHTS)
    fd = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'landlock_create_ruleset')
    try:
        def allow(path, rights):
            parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Beneath(rights, parent)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0) < 0:
                    raise OSError(ctypes.get_errno(), 'landlock_add_rule')
            finally:
                os.close(parent)
        allow(scope, WRITE_RIGHTS)
        if allow_self_task_metadata:
            # Explicitly authorized process-local kernel metadata only. The
            # directory FD identifies this PID's task subtree, not all /proc.
            # Install in the eventual CUDA process immediately before exec.
            allow('/proc/self/task', WRITE_FILE | (1 << 14))  # open(O_TRUNC) on thread comm
        # Device I/O is required, but no external regular file gets write rights.
        devices = ['/dev/null'] + glob.glob('/dev/nvidia*') + glob.glob('/dev/nvidia-caps/*')
        for path in devices:
            if stat.S_ISCHR(os.stat(path).st_mode):
                allow(path, WRITE_FILE)
        if libc.prctl(38, 1, 0, 0, 0):
            raise OSError(ctypes.get_errno(), 'no_new_privs')
        if libc.syscall(446, fd, 0):
            raise OSError(ctypes.get_errno(), 'landlock_restrict_self')
    finally:
        os.close(fd)
    return abi


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--write-scope', type=Path)
    parser.add_argument('--allow-self-task-metadata', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    assert command
    env = environment(args.root)
    os.chdir(args.root)
    os.nice(19)
    allowed_cpus = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, allowed_cpus[-4:])
    restrict(args.root, args.write_scope, args.allow_self_task_metadata)
    os.execvpe(command[0], command, env)
