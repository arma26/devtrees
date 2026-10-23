#!/usr/bin/env python3
"""Create and retire independent Git task clones."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import uuid
from typing import Literal, Optional, overload


class Refusal(Exception):
    pass


def root_path():
    value = os.environ.get('devtrees_root')
    if not value:
        raise Refusal('export a nonempty devtrees_root first')
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise Refusal('devtrees_root must be an existing non-root directory')
    inside(Path.cwd(), root)
    return root


def inside(value, root):
    path = Path(value).expanduser().resolve()
    if path != root and root not in path.parents:
        raise Refusal('path is outside devtrees_root: ' + str(path))
    return path


@overload
def git(*args, cwd, capture: Literal[True], data: Optional[str] = None) -> str: ...


@overload
def git(*args, cwd, capture: Literal[False] = False, data: Optional[str] = None) -> None: ...


def git(*args, cwd, capture=False, data=None):
    env = os.environ.copy()
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
                 'GIT_COMMON_DIR', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'):
        env.pop(name, None)
    result = subprocess.run(['git', *map(str, args)], cwd=cwd, env=env,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, text=True, input=data)
    if result.returncode:
        raise Refusal((result.stderr or '').strip() or 'git command failed')
    return result.stdout.removesuffix('\n') if capture else None


def source_value(value, base):
    if not value or value.startswith('-'):
        raise Refusal('repository source must be nonempty and not start with a dash')
    if re.match(r'^(?:[A-Za-z][A-Za-z0-9+.-]*://|[^/]+:)', value):
        return value
    return str((base / Path(value).expanduser()).resolve())


def configuration(root, start=None):
    directory = Path(start).resolve() if start is not None else Path.cwd().resolve()
    while True:
        config = directory / '.devtrees'
        if config.exists() or config.is_symlink():
            inside(config, root)
            # Source trusted shell, transporting only the two supported settings.
            script = ('unset devtrees_repo devtrees_clone_mode; . "$1"; '
                      'printf "%s\\000%s\\000" "${devtrees_repo:?missing devtrees_repo}" '
                      '"${devtrees_clone_mode:-shallow}"')
            result = subprocess.run(['/bin/sh', '-eu', '-c', script, 'devtrees', str(config)],
                                    cwd=directory, capture_output=True)
            if result.returncode:
                raise Refusal('cannot load nearest .devtrees: ' + os.fsdecode(result.stderr).strip())
            fields = result.stdout.split(b'\0')
            if len(fields) != 3 or fields[-1]:
                raise Refusal('.devtrees must not write to stdout')
            source, mode = map(os.fsdecode, fields[:2])
            if mode not in ('shallow', 'full'):
                raise Refusal('devtrees_clone_mode must be shallow or full')
            return directory, source_value(source, directory), mode
        if directory == root:
            raise Refusal('no .devtrees configuration found within devtrees_root')
        directory = directory.parent


def new_destination(value, root):
    original = Path(value).expanduser()
    if original.is_symlink():
        raise Refusal('destination is a symlink')
    destination = inside(original, root)
    if destination == root or destination.exists():
        raise Refusal('destination must be new. Existing data stays unchanged')
    return destination


def setup(args, root):
    destination = new_destination(args.directory, root)
    source = source_value(args.repository, Path.cwd())
    git('ls-remote', '--', source, cwd=Path.cwd(), capture=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    hub = destination / 'hub.git'
    git('clone', '--bare', '--no-local', '--no-hardlinks', '--reject-shallow',
        '--', source, hub, cwd=destination)
    with (destination / '.devtrees').open('x') as stream:
        stream.write('export devtrees_repo=' + shlex.quote(str(hub)) + '\n')
        stream.write('export devtrees_clone_mode=' + shlex.quote(args.clone_mode) + '\n')
    print(destination)
    print('Hub:', hub)
    print('In the original checkout, register this additional remote:')
    print('git remote add devtrees ' + shlex.quote(str(hub)))


def add(args, root):
    directory, source, mode = configuration(root)
    destination = new_destination(args.path, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    history = ['--depth=1', '--no-single-branch'] if mode == 'shallow' else ['--reject-shallow']
    git('clone', '--template=', '--no-local', '--no-hardlinks', *history, '--', source, destination, cwd=directory)
    if args.branch:
        git('switch', '-c', args.branch, *([args.start] if args.start else []), cwd=destination)
    elif args.start:
        git('checkout', args.start, cwd=destination)
    print(destination)


def repository(value, root):
    original = Path(value).expanduser()
    if original.is_symlink():
        raise Refusal('select the repository directory, not a symlink')
    path = inside(original, root)
    if path == root or not (path / '.git').is_dir() or (path / '.git').is_symlink():
        raise Refusal('expected an ordinary independent Git clone')
    actual = git('rev-parse', '--show-toplevel', cwd=path, capture=True)
    if not actual or Path(actual).resolve() != path:
        raise Refusal('repository redirects its working directory')
    return path


def discover(args, root):
    directory = inside(args.directory, root) if args.directory else configuration(root)[0]
    def failed(error):
        raise error
    for base, directories, _ in os.walk(directory, followlinks=False, onerror=failed):
        path = Path(base)
        directories[:] = sorted(name for name in directories
                                if name != '.git' and not (path / name).is_symlink())
        if (path / '.git').exists():
            directories[:] = []
            print(repository(path, root))
        elif (path / 'HEAD').is_file() and (path / 'objects').is_dir():
            directories[:] = []  # A bare source is not a working environment.


def push(args, root):
    path = repository(args.path, root)
    git('push', '--', args.remote, *args.refspec, cwd=path)


def inventory(source):
    paths = [source]
    def failed(error):
        raise error
    for base, directories, files in os.walk(source, followlinks=False, onerror=failed):
        directories.sort()
        paths.extend(Path(base) / name for name in sorted(directories + files))
    rows = []
    for path in paths:
        info = path.lstat()
        extra = ''
        if stat.S_ISLNK(info.st_mode):
            extra = os.readlink(path)
        elif stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            extra = digest.hexdigest()
        elif not stat.S_ISDIR(info.st_mode):
            raise Refusal('stop active processes. Unsupported special file: ' + str(path))
        rows.append((str(path.relative_to(source)), info.st_mode, info.st_dev,
                     info.st_ino, info.st_size, info.st_mtime_ns, extra))
    return rows


def removal_check(source, root):
    project, configured, _ = configuration(root, source.parent)
    hub_path = project / 'hub.git'
    if hub_path.is_symlink() or not hub_path.is_dir():
        raise Refusal('the project hub is missing or is a symlink')
    hub = inside(hub_path, root)
    if not Path(configured).is_absolute() or Path(configured).resolve() != hub:
        raise Refusal('configuration does not select this project hub')
    if source not in project.parents and project not in source.parents:
        raise Refusal('the selected clone is outside its project')
    if source == project or source == hub or source in hub.parents:
        raise Refusal('normal removal cannot select the project or hub')
    for parent in source.parents:
        if parent == project:
            break
        if (parent / '.git').exists():
            raise Refusal('normal removal cannot select a nested repository')
    if git('rev-parse', '--is-bare-repository', cwd=hub, capture=True) != 'true':
        raise Refusal('the project hub is not a bare repository')
    if git('rev-parse', '--is-shallow-repository', cwd=hub, capture=True) != 'false':
        raise Refusal('normal removal requires a full-history hub')
    actual_hub = git('rev-parse', '--absolute-git-dir', cwd=hub, capture=True)
    if Path(actual_hub).resolve() != hub:
        raise Refusal('the hub redirects its Git storage')
    if (hub / 'objects').is_symlink() or (hub / 'objects/info/alternates').exists():
        raise Refusal('the hub uses shared or redirected object storage')
    for directory, dirs, files in os.walk(hub / 'objects', followlinks=False):
        if any((Path(directory) / name).is_symlink() for name in dirs + files):
            raise Refusal('the hub redirects object storage through a symlink')
        if any(name.endswith('.promisor') for name in files):
            raise Refusal('the hub depends on promised objects')
    try:
        git('fsck', '--full', '--strict', '--no-reflogs', '--no-progress',
            cwd=hub, capture=True)
    except Refusal as error:
        raise Refusal('hub object verification failed. Keep the clone') from error
    origin = git('remote', 'get-url', 'origin', cwd=source, capture=True)
    if not Path(origin).is_absolute() or Path(origin).resolve() != hub:
        raise Refusal('the clone origin does not match the project hub')
    index = git('ls-files', '-v', '-z', cwd=source, capture=True).split('\0')
    if any(entry and entry[0] != 'H' for entry in index):
        raise Refusal('index flags can hide local changes. Keep the clone')
    if git('--no-optional-locks', '-c', 'core.fsmonitor=false', 'status',
           '--porcelain=v1', '-uall', '--ignored=matching', cwd=source, capture=True):
        raise Refusal('local changes or untracked or ignored files remain. Keep the clone')
    admin = source / '.git'
    allowed = {'HEAD', 'config', 'description', 'hooks', 'info', 'objects',
               'refs', 'logs', 'index', 'packed-refs', 'shallow', 'branches',
               'FETCH_HEAD', 'ORIG_HEAD', 'COMMIT_EDITMSG'}
    if any(path.name not in allowed or path.name.endswith('.lock') for path in admin.iterdir()):
        raise Refusal('private Git data or an active operation remains. Keep the clone')
    for directory in ('objects', 'refs', 'logs', 'hooks', 'info'):
        if (admin / directory).is_symlink():
            raise Refusal('Git storage must not redirect through a symlink')
    if (admin / 'objects/info/alternates').exists():
        raise Refusal('normal removal cannot verify shared object storage')
    if (admin / 'branches').exists() and any((admin / 'branches').iterdir()):
        raise Refusal('private legacy branch data remains. Keep or quarantine the clone')
    if (admin / 'hooks').exists() and any((admin / 'hooks').iterdir()):
        raise Refusal('local Git hooks remain. Keep or quarantine the clone')
    if (admin / 'info').exists() and any(p.name not in {'exclude', 'refs', 'packs', 'commit-graph'} for p in (admin / 'info').iterdir()):
        raise Refusal('private Git information remains. Keep or quarantine the clone')
    local_refs = git('for-each-ref', '--format=%(refname) %(objectname)',
                     cwd=source, capture=True).splitlines()
    objects = {git('rev-parse', '--verify', 'HEAD', cwd=source, capture=True)}
    for row in local_refs:
        name, oid = row.split(' ', 1)
        if name == 'refs/stash':
            raise Refusal('a local stash remains. Keep or quarantine the clone')
        if not name.startswith('refs/remotes/'):
            retained = git('show-ref', '--verify', '--hash', name, cwd=hub, capture=True)
            if not name.startswith('refs/heads/') and retained != oid:
                raise Refusal('a local Git reference differs from the hub')
        objects.add(oid)
    unreachable = git('fsck', '--full', '--strict', '--no-reflogs',
                      '--unreachable', '--no-progress',
                      cwd=source, capture=True).splitlines()
    for row in unreachable:
        fields = row.split()
        if len(fields) != 3 or fields[0] != 'unreachable':
            raise Refusal('Git object verification returned an unsupported result')
        objects.add(fields[2])
    retained_refs = git('for-each-ref', '--format=%(objectname)', cwd=hub, capture=True).splitlines()
    if not retained_refs:
        raise Refusal('the hub has no retained references')
    revisions = sorted(objects) + ['^' + oid for oid in retained_refs]
    if git('rev-list', '--objects', '--no-object-names', '--stdin', cwd=hub,
           capture=True, data='\n'.join(revisions) + '\n'):
        raise Refusal('the hub does not retain all local work. Push or preserve it first')
    if not shutil.rmtree.avoids_symlink_attacks:
        raise Refusal('this platform lacks safe directory removal support')
    selected = source.lstat()
    hub_info = hub.lstat()
    return (project, hub, selected.st_dev, selected.st_ino,
            hub_info.st_dev, hub_info.st_ino, tuple(retained_refs),
            (project / '.devtrees').read_bytes())


def remove_preserved(source, root):
    checked = removal_check(source, root)
    resources = inventory(source)
    if any(row[2] != checked[2] for row in resources):
        raise Refusal('normal removal cannot cross a filesystem boundary')
    if removal_check(repository(source, root), root) != checked or inventory(source) != resources:
        raise Refusal('the clone or hub changed after inspection. Keep the clone')
    shutil.rmtree(source)
    if source.exists() or source.is_symlink():
        raise Refusal('removal was not verified. Inspect the clone and hub')
    print('Removed:', repr(str(source)))
    print('Hub retained:', repr(str(checked[1])))


def teardown(args, root):
    source = repository(args.path, root)
    if not args.dry_run and not args.quarantine:
        remove_preserved(source, root)
        return
    store = inside(root / '.devtrees-quarantine', root)
    if store == source or source in store.parents:
        raise Refusal('quarantine storage cannot be inside the selected clone')
    if (root / '.devtrees-quarantine').is_symlink():
        raise Refusal('quarantine storage must not be a symlink')
    if store.exists() and (not store.is_dir() or (store / '.git').exists()):
        raise Refusal('quarantine storage is occupied by another resource')
    if source.is_mount() or source.stat().st_dev != root.stat().st_dev:
        raise Refusal('quarantine requires the same filesystem. No copy/delete fallback is available')
    if store.exists() and store.stat().st_dev != source.stat().st_dev:
        raise Refusal('quarantine storage is on a different filesystem')
    container = store / uuid.uuid4().hex
    destination = container / source.name
    changes = git('--no-optional-locks', 'status', '--porcelain=v1', '-uall',
                  cwd=source, capture=True)
    resources = inventory(source)
    print('Source:', repr(str(source)))
    print('Quarantine:', repr(str(destination)))
    print('Restore: mv -n -- ' + shlex.quote(str(destination)) + ' ' + shlex.quote(str(source)))
    print('Git changes:', repr(changes))
    print('Resources:', len(resources), 'entries. Regular-file bytes:',
          sum(row[4] for row in resources if stat.S_ISREG(row[1])))
    for row in resources:
        print(repr(row[0]), oct(row[1]), row[4], repr(row[6]))
    if not args.quarantine:
        print('Dry run: nothing moved. Normal removal requires preserved work. Quarantine requires terminal approval.')
        return
    if not sys.stdin.isatty():
        raise Refusal('quarantine requires a real terminal. Noninteractive input cannot approve it')
    reply = input('Stop writers to this clone. Type quarantine to move exactly these resources: ')
    if reply != 'quarantine':
        print('Cancelled: source retained.')
        return
    if repository(args.path, root) != source or inventory(source) != resources:
        raise Refusal('source changed after the plan. The source remains in place')
    if container.exists() or container.is_symlink():
        raise Refusal('the destination is occupied. The source remains in place')
    store.mkdir(exist_ok=True)
    if store.is_symlink() or inside(store, root) != store or store.stat().st_dev != source.stat().st_dev:
        raise Refusal('quarantine storage changed. The source remains in place')
    container.mkdir(mode=0o700)
    result = subprocess.run(['mv', '-n', str(source), str(destination)], cwd=root)
    if (result.returncode or source.exists() or not destination.is_dir()
            or inventory(destination) != resources):
        raise Refusal('quarantine could not be verified. Inspect both reported paths. No files were deleted')
    print('Quarantined:', repr(str(destination)))


def parser():
    result = argparse.ArgumentParser(description='Create independent task clones around a bare Git hub.')
    commands = result.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create a workspace and a full-history bare hub')
    init.add_argument('directory')
    init.add_argument('repository')
    init.add_argument('--clone-mode', choices=('shallow', 'full'), default='shallow')
    init.set_defaults(handler=setup)
    clone = commands.add_parser('add', help='create an independent task clone')
    clone.add_argument('-b', '--branch')
    clone.add_argument('path')
    clone.add_argument('start', nargs='?')
    clone.set_defaults(handler=add)
    listing = commands.add_parser('list', help='discover ordinary clones from the filesystem')
    listing.add_argument('directory', nargs='?')
    listing.set_defaults(handler=discover)
    handoff = commands.add_parser('push', help='push to an explicit remote without merging')
    handoff.add_argument('path')
    handoff.add_argument('remote')
    handoff.add_argument('refspec', nargs='*')
    handoff.set_defaults(handler=push)
    remove = commands.add_parser('remove', aliases=['teardown'], help='remove a preserved clone, inspect it, or quarantine it')
    remove.add_argument('path')
    mode = remove.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--quarantine', action='store_true')
    remove.set_defaults(handler=teardown)
    return result


def main():
    args = parser().parse_args()
    try:
        args.handler(args, root_path())
        return 0
    except (Refusal, OSError, ValueError) as error:
        print('devtrees: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
