# Devtrees

Set up and retire development environments as ordinary independent Git clones.
Devtrees is a small Python storage wrapper, not Git worktree emulation. There is
no membership registry, clone ID, state database, active environment, or merge
orchestration. Filesystem paths are the source of truth.

## Start an environment

Requires Python 3.9+, Git, `/bin/sh`, and `mv` with `-n` support on a POSIX host.
Put this checkout's `bin` directory on your PATH; no package installation is
needed. The command is a symlink to the standalone `devtrees.py` script.

```sh
export devtrees_root="$HOME/environments"
mkdir -p -- "${devtrees_root:?}"
cd -- "$devtrees_root"
devtrees init project /path/to/source.git
cd project
devtrees add -b task-a ./task-a
cd task-a
git status
```

`init` creates a new directory with a sourceable `.devtrees`. `add` creates a
self-contained `.git/` directory, with no hardlinked/shared object-store
requirement. Existing destinations are refused. Failed clone/checkout attempts
are retained, not automatically cleaned up.

Work inside the clone using ordinary Git and `cd`. Devtrees is not needed for
branching, pulling, committing, pushing, or merging:

```sh
git push --set-upstream origin task-a
```

Alternatively, `devtrees push ./task-a origin task-a` from the workspace invokes
native `git push`. It does not merge or synchronize clones. The user chooses
where and how integration happens.

## Discover and retire

```sh
cd -- "$devtrees_root/project"
devtrees list
devtrees remove ./task-a                 # dry-run only
devtrees remove ./task-a --quarantine    # interactive confirmation
```

`list` discovers ordinary clones beneath the nearest workspace, or an explicit
`list DIRECTORY`, without registration. Discovery stops at each clone, skips
Git internals, and does not follow directory symlinks. Renaming directories
needs no devtrees repair. A root-wide listing can also find quarantined clones;
there is no hidden active/inactive membership state.

Teardown prints Git changes, every resource, the proposed destination and a
restore command. Stop writers before confirming. Quarantine requires a terminal
and the exact confirmation `quarantine`; piped input cannot approve it. It checks
the inventory again, moves into a new private directory beneath
`$devtrees_root/.devtrees-quarantine/`, and verifies the moved contents. It never
falls back to cross-filesystem copy/delete and has no purge or `--yes` option.
`teardown` is an alias for `remove`.

Keep the printed resource manifest and restore mapping; devtrees does not write
a recovery database. Confirm that `Quarantined:` reports success and inspect the
reported directory with ordinary Git. Restore only to an absent original path
using the printed no-clobber command, then verify with `git status`. Cancellation
leaves the clone in place. On an unverified move, inspect both reported paths;
nothing is automatically deleted. This is not crash recovery or protection
against racing filesystem writers.

## Configuration and boundary

```sh
export devtrees_repo='/path/to/source.git'
export devtrees_clone_mode='shallow'  # or full
```

The nearest `.devtrees` wins, with paths relative to its directory. It is trusted
shell code, loaded with `/bin/sh -eu`; it must not print to stdout. Only the source
and clone-mode settings are transported, as NUL-delimited fields, not JSON.
`devtrees_root` is mandatory in the invoking shell and cannot be widened by the
configuration. Calls and target paths must remain inside that root, including
symlink resolution. Git hooks, shell configuration and remote endpoints remain
trusted inputs, not an OS sandbox.

New clones default to depth one for available branch tips. Choose full history
with `init --clone-mode full`, or set `devtrees_clone_mode=full`; a shallow source
is rejected in full mode. Existing clones are never silently deepened. Use
native Git if older history is needed. `add PATH START` checks out a start point;
`add -b BRANCH PATH [START]` creates a branch with native Git.

## Development

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use real local Git repositories and retain fixtures in Git-private storage.
See [design](docs/design.md) and [terminology](GLOSSARY.md).
