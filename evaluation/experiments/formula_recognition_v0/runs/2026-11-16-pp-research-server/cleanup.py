"""Delete only a revalidated owned tree after verified download and process exit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


def validate(root, expected):
    root = Path(root)
    assert root.is_absolute() and root.resolve(strict=True) == root
    assert root.name == 'understanding-engine-pp-' + expected['run_id']
    assert str(root) == expected['root'] and expected['uid'] == os.getuid()
    st = root.lstat()
    assert stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and stat.S_IMODE(st.st_mode) == 0o700
    assert (st.st_dev, st.st_ino) == (expected['device'], expected['inode'])
    assert not os.path.ismount(root)
    marker = root / '.experiment-owner.json'
    assert stat.S_ISREG(marker.lstat().st_mode) and not marker.is_symlink()
    actual = json.loads(marker.read_text())
    assert all(actual[key] == expected[key] for key in ['root', 'run_id', 'uid', 'device', 'inode'])
    # Reject nested mount points, including same-filesystem bind mounts.
    if Path('/proc/self/mountinfo').exists():
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            mount = line.split()[4].replace('\\040', ' ').replace('\\134', '\\')
            assert mount != str(root) and not mount.startswith(str(root) + '/')
    return st


def inspect_tree(fd, uid, device):
    counts = {'files': 0, 'directories': 1, 'symlinks': 0, 'allocated_bytes': 0, 'logical_bytes': 0}
    for entry in os.scandir(fd):
        status = entry.stat(follow_symlinks=False)
        assert status.st_uid == uid and status.st_dev == device, 'Unexpected owner/filesystem; do not delete'
        if stat.S_ISDIR(status.st_mode):
            child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                assert (os.fstat(child).st_dev, os.fstat(child).st_ino) == (status.st_dev, status.st_ino)
                values = inspect_tree(child, uid, device)
            finally:
                os.close(child)
            for key, value in values.items():
                counts[key] += value
        elif stat.S_ISLNK(status.st_mode):
            counts['symlinks'] += 1
        else:
            assert stat.S_ISREG(status.st_mode), 'Unexpected special file; do not delete'
            counts['files'] += 1
            counts['allocated_bytes'] += status.st_blocks * 512
            counts['logical_bytes'] += status.st_size
    return counts


def remove_contents(fd, uid, device):
    for entry in os.scandir(fd):
        status = entry.stat(follow_symlinks=False)
        assert status.st_uid == uid and status.st_dev == device
        if stat.S_ISDIR(status.st_mode):
            child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                assert (os.fstat(child).st_dev, os.fstat(child).st_ino) == (status.st_dev, status.st_ino)
                remove_contents(child, uid, device)
            finally:
                os.close(child)
            again = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
            assert (again.st_dev, again.st_ino) == (status.st_dev, status.st_ino)
            os.rmdir(entry.name, dir_fd=fd)
        else:
            assert stat.S_ISREG(status.st_mode) or stat.S_ISLNK(status.st_mode)
            # Unlink the owned entry; never follow or modify a symlink target.
            os.unlink(entry.name, dir_fd=fd)


def cleanup(root, expected, archive_sha256):
    root = Path(root)
    status = validate(root, expected)
    ack = json.loads((root / 'download-verified.json').read_text())
    assert ack['local_archive_sha256'] == archive_sha256 and ack['archive_and_members_verified'] is True
    # Known child identities must already have exited; no process is terminated here.
    known = []
    for path in root.glob('*.stage.json'):
        value = json.loads(path.read_text())
        assert value['process_exited'] is True
        known.append(value['pid'])
    for directory in ['outputs', 'outputs-decoder-complete']:
        for path in (root / directory).glob('*.resource.json'):
            value = json.loads(path.read_text())
            assert value['process_cleanup_verified'] is True
            if 'pid' in value:
                known.append(value['pid'])
    # lsof filters our UID and the exact tree; no unrelated argv/file contents read.
    excluded = []
    # Other users' FUSE portals cannot be stat'ed. Explicitly exclude only
    # disjoint FUSE mounts, never the owned ext4 tree or an ancestor of it.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        if right.split()[0].startswith('fuse.'):
            path = Path(left.split()[4])
            assert path.is_absolute() and path != root and not root.is_relative_to(path) and not path.is_relative_to(root)
            excluded += ['-e', str(path)]
    probe = subprocess.run(['lsof', '-nP', *excluded, '-a', '-u', str(os.getuid()), '+D', str(root), '-t'], capture_output=True, text=True, timeout=60)
    assert probe.returncode in [0, 1] and not probe.stderr.strip(), 'Open-handle verification uncertain; leave tree untouched'
    pids = {int(line) for line in probe.stdout.splitlines() if line.strip().isdigit()} - {os.getpid()}
    assert not pids, 'Experiment directory still referenced by processes; leave untouched'
    for pid in known:
        command = Path('/proc', str(pid), 'cmdline')
        if command.exists():
            assert str(root).encode() not in command.read_bytes(), 'Known owned process remains active'
    parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        assert (os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (status.st_dev, status.st_ino)
        counts = inspect_tree(fd, os.getuid(), status.st_dev)
        fs = os.statvfs(root.parent)
        before = fs.f_bavail * fs.f_frsize
        remove_contents(fd, os.getuid(), status.st_dev)
        current = os.stat(root.name, dir_fd=parent_fd, follow_symlinks=False)
        assert (current.st_dev, current.st_ino) == (status.st_dev, status.st_ino)
        os.rmdir(root.name, dir_fd=parent_fd)
    finally:
        os.close(fd)
        os.close(parent_fd)
    assert not root.exists() and not root.is_symlink()
    fs = os.statvfs(root.parent)
    after = fs.f_bavail * fs.f_frsize
    return {'removed': True, 'identity_verified': True, 'owner_verified': True, 'open_process_references': [],
            'before_available_bytes': before, 'after_available_bytes': after, 'observed_recovered_bytes': after - before,
            'pre_cleanup_inventory': counts, 'remaining_owned_files': 0,
            'lsof_excluded_disjoint_fuse_mounts': excluded[1::2],
            'caveat': 'Observed filesystem free-space change includes possible concurrent activity; allocated bytes do not guarantee identical recovery'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--expected-json', required=True)
    parser.add_argument('--archive-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(cleanup(args.root, json.loads(args.expected_json), args.archive_sha256), indent=2), flush=True)
