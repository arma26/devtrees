#!/usr/bin/env python3
"""Small, stateless setup and teardown for ordinary Git clones."""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


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
    return result.stdout.strip() if capture else None


def source_value(value, base):
    if not value or value.startswith('-'):
        raise Refusal('repository source must be nonempty and not start with a dash')
    if re.match(r'^(?:[A-Za-z][A-Za-z0-9+.-]*://|[^/]+:)', value):
        return value
    return str((base / Path(value).expanduser()).resolve())


def configuration(root):
    directory = Path.cwd().resolve()
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
        raise Refusal('destination must be new; existing data is not overwritten')
    return destination


def setup(args, root):
    destination = new_destination(args.directory, root)
    source = source_value(args.repository, Path.cwd())
    git('ls-remote', '--', source, cwd=Path.cwd(), capture=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    with (destination / '.devtrees').open('x') as stream:
        stream.write('export devtrees_repo=' + shlex.quote(source) + '\n')
        stream.write('export devtrees_clone_mode=' + shlex.quote(args.clone_mode) + '\n')
    print(destination)


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


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create sourceable workspace configuration')
    init.add_argument('directory')
    init.add_argument('repository')
    init.add_argument('--clone-mode', choices=('shallow', 'full'), default='shallow')
    init.set_defaults(handler=setup)
    clone = commands.add_parser('add', help='create an ordinary independent Git clone')
    clone.add_argument('-b', '--branch')
    clone.add_argument('path')
    clone.add_argument('start', nargs='?')
    clone.set_defaults(handler=add)
    listing = commands.add_parser('list', help='discover ordinary clones from the filesystem')
    listing.add_argument('directory', nargs='?')
    listing.set_defaults(handler=discover)
    handoff = commands.add_parser('push', help='invoke native git push; never merge')
    handoff.add_argument('path')
    handoff.add_argument('remote')
    handoff.add_argument('refspec', nargs='*')
    handoff.set_defaults(handler=push)
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
