# Devtrees

Set up and retire development environments as ordinary independent Git clones.
Devtrees is a small Python storage wrapper, not Git worktree emulation. There is
no membership registry, clone ID, state database, active environment, or merge
orchestration. Filesystem paths are the source of truth.

## Design decision: a bare hub for parallel agents

**Accepted design; not yet implemented as the default.** Today, `init` records
its supplied source directly. It does not create a hub or register a remote in
an existing checkout. The commands under [Start an environment](#start-an-environment)
describe that current implementation.

For parallel agent work, the intended default is one project-local **bare hub**:
a Git repository without a working tree, used to exchange committed branches.
Each agent still works in an ordinary independent clone.

```text
normal-checkout/                 # existing checkout; outside or inside the root

$devtrees_root/project/
├── .devtrees                    # points task clones at hub.git
├── hub.git/                     # bare exchange repository
├── task-a/                      # independent clone, branch agent/task-a
└── task-b/                      # independent clone, branch agent/task-b
```

### Why use a hub?

Agents get a common place to push without updating a branch checked out in the
normal repository. Git normally refuses that kind of push into a non-bare
repository. The hub also keeps pushed branches available after individual task
clones are retired. It is Git storage, not a devtrees membership registry.

The hub **collects branches; it does not merge them**. Integration remains an
explicit operation in the normal checkout, using ordinary Git. Existing hosted
remotes and their upstream configuration stay unchanged.

### How the workflow works

1. **Seed the hub.** Create a bare clone of the normal repository inside the
   project workspace. Use a normal bare clone, not a mirror. Keep the hub
   full-history by default; agent clone depth is a separate choice. Only committed
   history is transferred: uncommitted and untracked work stays in the original.
2. **Start tasks.** Point `.devtrees` at the hub and create independent clones
   from it. Each clone has the hub as `origin` and uses a distinct task branch.
3. **Return completed work.** Each agent pushes its branch to the hub when ready.
   Agents need not wait for every other task to finish.
4. **Integrate deliberately.** Add the hub as an additional remote in the normal
   checkout, fetch its branches, review them, and merge the selected results.
   Fetching alone does not change checked-out files or combine agent branches.

The following native Git examples assume the proposed layout already exists;
they are not commands that the current `init` runs automatically. Replace the
example paths with the chosen locations. From the task-a clone, after committing:

```sh
git push --set-upstream origin agent/task-a
git ls-remote --heads origin refs/heads/agent/task-a
```

The remote branch should name the commit returned by `git rev-parse HEAD` in
that clone. A failed push is not a completed handoff; retain the clone and inspect
the error before retrying.

In the normal checkout, first resolve uncommitted work and select the intended
integration branch. Register the additional remote once; if `devtrees` already
exists, inspect it rather than replacing it:

```sh
git remote add devtrees /absolute/path/to/project/hub.git
git remote get-url devtrees
git fetch devtrees
git log --oneline HEAD..devtrees/agent/task-a
git diff HEAD...devtrees/agent/task-a
git merge devtrees/agent/task-a
git status
```

Confirm the remote URL before fetching. Review each branch separately; a single
pull does not combine all agent branches. A merge may fast-forward or create a
merge commit. If it conflicts, stop and resolve it using normal Git; do not retire
the task clone merely because its push succeeded. After a successful merge,
`git merge-base --is-ancestor devtrees/agent/task-a HEAD` should exit successfully.
Repeat the review and merge for task-b when appropriate.

### Normal task removal

The intended `devtrees remove PATH` is a normal task-clone removal operation,
not removal of the project workspace or its hub. Once work is safely retained
in the hub, the task checkout is reconstructible and need not be quarantined
merely because its directory is being retired.

Normal removal must verify that:

- The project's hub still exists and is a valid bare Git repository.
- The clone belongs to that project, and its selected path is neither the hub
  nor the project directory, an ancestor of either, or an unrelated repository.
- The clone's local branch tips are reachable from retained references in the
  hub. A directory named `hub.git` or an earlier successful push is not proof
  that the hub still retains the work.
- No uncommitted changes, untracked or ignored files, stashes, or other local-only
  work would be lost. Pushing a branch does not preserve these resources.

If these checks pass, an explicitly requested normal removal retires only the
selected task clone. The project configuration, hub, and other clones remain.
If a check fails, refuse removal and report what must be committed, pushed,
preserved, or inspected. Do not force-remove, auto-stash, or auto-push to make
removal succeed. Dry-run inspection and explicitly chosen quarantine remain
available for cases where normal removal is inappropriate.

This is the familiar worktree-removal workflow applied to independent clones,
not a call to `git worktree remove`. It requires no membership registry: inspect
the project configuration, paths, and current Git references at removal time.
Project or hub retirement is a separate operation and is not authorized by
removing a task clone.

**Implementation status:** normal removal under these checks is part of the
accepted design, not implemented behavior. The current CLI still defaults to
the dry-run/quarantine workflow documented below.

### Boundaries and lifetime

- The hub starts as a snapshot, not a live synchronization service. Transfer a
  newer committed base explicitly before starting tasks that need it.
- Devtrees setup remains inside `devtrees_root`. Remote registration, fetching,
  and merging in the original checkout are explicit native Git operations,
  including when that checkout is outside the root.
- Retiring a task clone must leave the hub and other clones intact. Hub retirement
  is a separate decision because it may hold branches absent from the original
  checkout or hosted upstream. A local hub is not a separate-device backup.
- There is no automatic merge, branch deletion, force-push, publication to a
  hosted service, or cleanup when tasks finish.

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
