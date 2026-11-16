"""Bounded evidence export: explicit metadata/config/output paths, never weights/runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile


MAX_TOTAL = 64 * 1024**2
MAX_FILE = 20 * 1024**2


def package(root, name='results.zip'):
    assert Path(name).name == name and name.endswith('.zip')
    paths = []
    for path in root.iterdir():
        if path.suffix in {'.json', '.jsonl', '.log', '.trace', '.py', '.txt', '.lock'} and path.is_file() and not path.is_symlink():
            paths.append(path)
    for filename in ['inference.json', 'inference.yml']:
        paths.append(root / 'model' / filename)
    for directory in ['outputs', 'outputs-decoder-complete']:
        if (root / directory).exists():
            paths.extend(p for p in (root / directory).rglob('*') if p.is_file())
    rows = []
    total = 0
    for path in sorted(paths):
        status = path.lstat()
        assert stat.S_ISREG(status.st_mode) and not path.is_symlink()
        assert path.resolve().is_relative_to(root)
        relative = path.relative_to(root).as_posix()
        assert path.suffix != '.pdiparams' and status.st_size <= MAX_FILE
        total += status.st_size
        assert total <= MAX_TOTAL
        rows.append({'file': relative, 'bytes': status.st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    with zipfile.ZipFile(root / name, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            archive.write(root / row['file'], row['file'])
        archive.writestr('archive-members.json', json.dumps(rows, indent=2))
    archive = root / name
    result = {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size, 'members': len(rows), 'uncompressed_member_bytes': total}
    summary = 'archive-summary.json' if name == 'results.zip' else name[:-4] + '.summary.json'
    with (root / summary).open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--name', default='results.zip')
    args = parser.parse_args()
    package(args.root, args.name)
