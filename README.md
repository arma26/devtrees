# Devtrees

Create task environments as ordinary independent Git clones.
Each project has a bare hub, a Git repository without checked-out files.
The hub stores committed branches from task clones.
Use native Git to push, fetch, review and merge those branches in your original checkout.
Devtrees never merges branches. It does not automatically publish work to hosted remotes.

## Topology

```text
normal-checkout/                 # original integration checkout

$devtrees_root/project/
├── .devtrees                    # sourceable configuration pointing at hub.git
├── hub.git/                     # full bare repository for committed branches
├── task-a/                      # independent clone, branch agent/task-a
└── task-b/                      # independent clone, branch agent/task-b
```

The original checkout can be outside `devtrees_root`.
Devtrees operations and their targets must remain inside that root.

## Quick start

Requires Python 3.9+, Git, `/bin/sh`, and `mv` with `-n` support on a POSIX host.
Devtrees needs no package installation. Replace `/path/to/devtrees` below with this checkout's absolute path.
The example adds its `bin` directory to PATH for the current shell.
The command is a symlink to the standalone `devtrees.py` script.

Use a full-history source. `init` refuses shallow sources, regardless of the task clone mode.

```sh
set -eu
export PATH="/path/to/devtrees/bin:$PATH"
export devtrees_root="$HOME/environments"
mkdir -p -- "${devtrees_root:?}"
cd -- "$devtrees_root"
devtrees init project /path/to/normal-checkout
cd project
devtrees add -b agent/task-a ./task-a
devtrees add -b agent/task-b ./task-b
devtrees list
```

`init` creates `project/hub.git` as a full bare clone and writes `.devtrees` pointing there.
It prints the hub path and a remote-registration command. It does not change the original checkout's remotes.

`add` creates each task clone with its own `.git/` directory and the hub as `origin`.
Native Git templates and settings apply.
`list` reports the task clones beneath the project workspace.

Devtrees refuses existing destinations. It retains partial destinations after clone or checkout failures.

### Push a completed task

Commit task-a's work first. From the project workspace, push its branch:

```sh
cd task-a
git status
git push --set-upstream origin agent/task-a
git ls-remote --heads origin refs/heads/agent/task-a
git rev-parse HEAD
```

`git ls-remote` must show the same commit as `git rev-parse HEAD`.
Keep the clone if the push fails.
Only committed history crosses repositories.
A branch push does not preserve uncommitted changes, untracked or ignored files, or stashes.

Alternatively, from the project workspace, `devtrees push ./task-a origin agent/task-a` invokes native `git push`.
It does not merge or synchronize clones.

### Fetch, review and merge

In the original checkout, resolve uncommitted work first. Select the intended integration branch.
Register the additional `devtrees` remote once. Keep the existing hosted `origin` unchanged.
If `devtrees` already exists, inspect its URL. Do not replace it.

```sh
git remote add devtrees /absolute/path/to/project/hub.git
git remote get-url devtrees
```

Check the URL before `git fetch`:

```sh
git fetch devtrees
git log --oneline HEAD..devtrees/agent/task-a
git diff HEAD...devtrees/agent/task-a
```

`fetch` updates remote-tracking references. It does not change checked-out files or merge branches.
Review the commits and changes before `git merge`:

```sh
git merge devtrees/agent/task-a
git status
git merge-base --is-ancestor devtrees/agent/task-a HEAD
```

`merge` can fast-forward or create a merge commit. If conflicts occur, stop and resolve them with native Git.
After a successful merge, the ancestry check exits successfully. Review and merge task-b separately.

## Remove a task

The user or agent harness decides whether a task is delivered and ready for removal.
Devtrees does not verify pushes, delivery, dirty files, stashes, or Git object retention.

Stop writers and inspect the selected path before removal:

```sh
devtrees remove ./task-a
```

This is a dry run. `--dry-run` is an explicit equivalent.
After you preserve the work you need and approve the exact target, delete it with:

```sh
devtrees remove ./task-a --please
```

**`--please`** deletes the entire selected clone, including uncommitted files, ignored files, stashes and local settings.
It is confirmation, not a preservation check. Devtrees does not automatically push or create a backup.

Removal enforces the operating-root boundary. It refuses selected symlinks, mounts, the project, its hub and its configured source repository.
It does not remove sibling clones or authorize project retirement.
If deletion fails partway, inspect the remaining directory. Do not overwrite it or assume rollback.

### Preserve a clone with quarantine

Choose quarantine when you need the complete clone rather than deletion:

```sh
devtrees remove ./task-a --quarantine
```

It prints the source, destination and no-clobber restore command. It requires a terminal and the exact confirmation `quarantine`.
Piped input cannot approve it. The move stays on one filesystem beneath `$devtrees_root/.devtrees-quarantine/`.

Retain the printed restore command. There is no manifest, recovery database or purge command.
Verify the reported `Quarantined:` directory. Restore only to an absent original path with the printed command.
Inspect both paths if verification fails. There is no copy/delete fallback or crash-recovery service.
Stop writers throughout removal or quarantine. Devtrees does not protect against hostile filesystem writers.
`teardown` is an alias for `remove`.

## Similar to and different from linked Git worktrees

Both provide separate working directories and an add/list/remove lifecycle.
Each working directory has its own index.
Linked worktrees share repository storage and use `.git` pointer files.
Task clones have separate refs, objects, indexes, stashes and repository configuration.
Tools can mount each task clone's normal `.git/` directory.
Devtrees does not emulate Git-worktree flags or maintain a membership registry.

## Configuration and discovery

Task clones default to depth one for available branch tips. The hub always starts with full history.
Choose full task history with `init --clone-mode full` or `devtrees_clone_mode=full`.
Existing clones are never silently deepened. Use native Git for older history.

The nearest `.devtrees` is trusted shell code, not passive data. It cannot widen the shell-provided `devtrees_root`.
See [design and configuration](docs/design.md) for root limits, clone options and discovery rules.
See [terminology](GLOSSARY.md) for the terms used here.

## Development

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use real local Git repositories and retain fixtures in Git-private storage.
