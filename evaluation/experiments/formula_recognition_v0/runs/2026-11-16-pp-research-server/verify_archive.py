"""Verify bounded returned evidence locally before authorizing exact-tree cleanup."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def verify(path, summary, destination):
    assert path.stat().st_size == summary['bytes']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == summary['sha256']
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [i.filename for i in entries]
        assert len(names) == len(set(names)) and len(names) <= 300
        assert sum(i.file_size for i in entries) <= 65 * 1024**2
        for item in entries:
            name = PurePosixPath(item.filename)
            assert not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename
            assert not stat.S_ISLNK(item.external_attr >> 16) and not item.is_dir()
            assert item.file_size <= 20 * 1024**2
        rows = json.loads(archive.read('archive-members.json'))
        assert len(rows) == summary['members']
        assert {row['file'] for row in rows} == set(names) - {'archive-members.json'}
        for row in rows:
            data = archive.read(row['file'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        assert archive.testzip() is None
        destination.mkdir(exist_ok=False)
        for item in entries:
            target = destination / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(archive.read(item.filename))
    return {'local_archive_sha256': summary['sha256'], 'archive_and_members_verified': True, 'members': len(rows)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, json.loads(args.summary.read_text()), args.destination)), flush=True)
