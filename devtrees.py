#!/usr/bin/env python3
"""Create and retire independent Git task clones."""

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from typing import Literal, overload


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
def git(*args, cwd, capture: Literal[True]) -> str: ...


@overload
def git(*args, cwd, capture: Literal[False] = False) -> None: ...


def git(*args, cwd, capture=False):
    env = os.environ.copy()
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
                 'GIT_COMMON_DIR', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'):
        env.pop(name, None)
    result = subprocess.run(['git', *map(str, args)], cwd=cwd, env=env,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, text=True)
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
    git('clone', '--no-local', '--no-hardlinks', *history, '--', source, destination, cwd=directory)
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


def teardown(args, root):
    source = repository(args.path, root)
    project, configured, _ = configuration(root, source)
    if source == project or source == project / 'hub.git':
        raise Refusal('removal cannot select the project or hub')
    if Path(configured).is_absolute() and source == Path(configured).resolve():
        raise Refusal('removal cannot select the configured source repository')
    if source.is_mount():
        raise Refusal('removal cannot select a filesystem mount')
    if not args.please and not args.quarantine:
        print('Would remove:', repr(str(source)))
        print('Dry run: nothing changed. Use --please to delete this entire clone.')
        return
    if args.please:
        if not shutil.rmtree.avoids_symlink_attacks:
            raise Refusal('this platform lacks symlink-resistant directory removal')
        shutil.rmtree(source)
        if source.exists() or source.is_symlink():
            raise Refusal('removal was not verified. Inspect the selected path')
        print('Removed:', repr(str(source)))
        return
    store = inside(root / '.devtrees-quarantine', root)
    if store == source or source in store.parents or store.is_symlink():
        raise Refusal('quarantine storage must be separate from the selected clone')
    if store.exists() and (not store.is_dir() or (store / '.git').exists()):
        raise Refusal('quarantine storage is occupied by another resource')
    identity = (source.stat().st_dev, source.stat().st_ino)
    if identity[0] != root.stat().st_dev or (store.exists() and store.stat().st_dev != identity[0]):
        raise Refusal('quarantine requires the same filesystem. No copy/delete fallback is available')
    container = store / uuid.uuid4().hex
    destination = container / source.name
    print('Source:', repr(str(source)))
    print('Quarantine:', repr(str(destination)))
    print('Restore: mv -n -- ' + shlex.quote(str(destination)) + ' ' + shlex.quote(str(source)))
    if not sys.stdin.isatty():
        raise Refusal('quarantine requires a real terminal. Noninteractive input cannot approve it')
    if input('Stop writers. Type quarantine to move this clone: ') != 'quarantine':
        print('Cancelled: source retained.')
        return
    if repository(args.path, root) != source or (source.stat().st_dev, source.stat().st_ino) != identity:
        raise Refusal('the selected clone changed. Inspect the source')
    store.mkdir(exist_ok=True)
    if store.is_symlink() or inside(store, root) != store or store.stat().st_dev != identity[0]:
        raise Refusal('quarantine storage changed. The source remains in place')
    container.mkdir(mode=0o700)
    result = subprocess.run(['mv', '-n', str(source), str(destination)], cwd=root)
    if (result.returncode or source.exists() or not destination.is_dir()
            or (destination.stat().st_dev, destination.stat().st_ino) != identity):
        raise Refusal('quarantine could not be verified. Inspect both reported paths')
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
    remove = commands.add_parser('remove', aliases=['teardown'], help='preview, delete, or quarantine a selected clone')
    remove.add_argument('path')
    mode = remove.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='preview removal (default)')
    mode.add_argument('--please', action='store_true', help='delete the entire selected clone (caller confirms readiness)')
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
