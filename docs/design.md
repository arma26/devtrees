# Workflow reference

For the guided user journey, see [start parallel tasks](../README.md#start-parallel-tasks).
This page covers command behavior, configuration, verification and recovery details.

## Contents

- [Workspace layout](#workspace-layout)
- [Responsibilities and lifetime](#responsibilities-and-lifetime)
- [Branch handoff and integration checks](#branch-handoff-and-integration-checks)
- [State and discovery](#state-and-discovery)
- [Configuration and root boundary](#configuration-and-root-boundary)
- [Preservation and removal](#preservation-and-removal)
- [Quarantine and restore](#quarantine-and-restore)
- [Agent workflow routing](#agent-workflow-routing)
- [Development checks](#development-checks)

## Workspace layout

```text
normal-checkout/                 # original integration checkout

$devtrees_root/project/
├── .devtrees                    # sourceable configuration pointing at hub.git
├── hub.git/                     # full bare repository for committed branches
├── task-a/                      # independent clone, branch agent/task-a
└── task-b/                      # independent clone, branch agent/task-b
```

The original checkout can be outside `devtrees_root`. Devtrees calls and mutation targets stay inside that root.

## Responsibilities and lifetime

- `init DIRECTORY SOURCE` creates a full bare clone at `DIRECTORY/hub.git` and points `.devtrees` at it.
  It rejects shallow sources. It prints a remote-registration command but does not change the original checkout's remotes.
- `add -b BRANCH PATH [START]` creates an independent task clone and a branch.
  `add PATH START` selects a start point without creating a named branch.
  Each clone has its own `.git/` directory. Its `origin` points to the configured source, normally the hub.
  Native Git templates and settings apply.
- `push PATH REMOTE [REFSPEC...]` invokes native Git push. It does not merge branches or synchronize clones.
- `remove PATH` and `remove PATH --dry-run` preview the selected clone.
  `remove PATH --please` deletes it. `remove PATH --quarantine` preserves the complete clone through an approved move.
  `teardown` is an alias for `remove`.

The hub starts as a snapshot, not a live synchronization service.
Only committed history crosses repositories. Branch pushes do not preserve uncommitted changes, untracked or ignored files, or stashes.
Task removal keeps the project configuration, hub and sibling clones.

Hub retirement is a separate decision because it can hold branches absent from the original checkout or hosted upstream.
A local hub is not a separate-device backup.
There is no automatic merge, branch deletion, force-push, hosted publication or cleanup after a task.

## Branch handoff and integration checks

After pushing task-a, compare the hub's branch tip with your local commit:

```sh
cd -- "$devtrees_root/project/task-a"
git ls-remote --heads origin refs/heads/agent/task-a
git rev-parse HEAD
```

The commit IDs should match. These checks concern that committed branch, not other local-only work.
If the push fails, keep the clone and inspect Git's error.

In the original checkout, inspect an existing `devtrees` remote before fetching:

```sh
git remote get-url devtrees
git fetch devtrees
git log --oneline HEAD..devtrees/agent/task-a
git diff HEAD...devtrees/agent/task-a
```

The remote URL should identify the intended project hub. Keep any existing hosted `origin` unchanged.
Fetch updates remote-tracking refs without changing working files. Review each branch before merging it into the intended integration branch.
After a successful merge, this ancestry check should exit successfully:

```sh
git merge-base --is-ancestor devtrees/agent/task-a HEAD
```

Merges can fast-forward or create merge commits. Resolve conflicts through native Git before treating integration as complete.

To give new tasks your latest integration, explicitly update the hub's base branch.
For a hub whose intended default base is `main`, push the selected integration commit to that branch:

```sh
git push devtrees HEAD:refs/heads/main
```

Choose the destination branch deliberately. A rejected push needs inspection, not an automatic force-push.
Devtrees does not update the base on your behalf.

## State and discovery

Git owns repository state. Filesystem paths determine which task environments exist.
There is no clone registry, generated clone identity, membership cache, state database or active-environment selector.
There is no shared-ref emulation, persistent lock database or merge orchestration.

`list` inspects the nearest workspace. `list DIRECTORY` inspects an explicit directory within the operating root.
Discovery stops at each ordinary clone. It skips Git internals and bare repositories and does not follow directory symlinks.
Renaming a clone directory needs no registry repair.
A root-wide listing can also find quarantined clones. There is no hidden active/inactive state.

## Configuration and root boundary

The invoking shell must supply `devtrees_root` as an existing directory other than the filesystem root.
Devtrees calls and target paths must stay inside it, including after symlink resolution.
Native Git remote registration, fetch and merge in the original checkout are explicit operations outside Devtrees.
The original checkout can be outside the operating root.

The nearest `.devtrees` wins. Relative source paths resolve against its directory.
The default project configuration points `devtrees_repo` at `hub.git` and selects shallow task clones:

```sh
export devtrees_repo='/path/to/project/hub.git'
export devtrees_clone_mode='shallow'  # or full
```

`.devtrees` is trusted shell code, loaded with `/bin/sh -eu`. It must not print to stdout.
Only the source and clone-mode settings cross that interface, as NUL-delimited fields, not JSON.
Configuration cannot widen the shell-provided root.
Git hooks, shell configuration and remote endpoints remain trusted inputs. Devtrees is not an operating-system sandbox.

Shallow task clones use depth one for available branch tips. The hub itself starts with full history.
Use `init --clone-mode full DIRECTORY SOURCE` to select full history for that workspace's task clones.
Alternatively, set `devtrees_clone_mode=full` in its configuration. Full mode rejects shallow sources.
Existing clones are never silently deepened. Use native Git for older history.

## Preservation and removal

New destinations are exclusive. Native Git cloning uses no local object sharing or hardlinks.
Partial destinations remain after clone or checkout failures.
Push and removal require an ordinary clone, not a linked-worktree pointer or selected symlink.

The user or agent harness owns delivery, preservation and removal readiness.
The CLI does not inspect Git metadata, refs, reflogs or objects to establish readiness.
It does not require a clean clone or verify that branches were pushed.

`remove PATH` previews the target. Only `remove PATH --please` deletes it.
The flag confirms deletion of the entire clone, including any local-only work.
Devtrees enforces its root boundary and protects the project, hub and configured source repository.
It also refuses a selected symlink or mount. It does not maintain inventories, manifests or a registry.

Stop writers before removal or quarantine. Recursive deletion can fail partway and has no rollback guarantee.
If deletion fails, inspect the remaining directory. Do not overwrite it or assume the operation made no changes.
See [retire a task](../README.md#retire-a-task) for the normal user workflow.

## Quarantine and restore

Choose quarantine to retain the complete clone, including local-only work:

```sh
devtrees remove ./task-a --quarantine
```

It prints the source, destination and no-clobber restore command.
It requires a real terminal and the exact confirmation `quarantine`. Piped input cannot approve it.
Cancellation leaves the source in place.

The move stays on one filesystem beneath `$devtrees_root/.devtrees-quarantine/`.
Devtrees verifies the moved directory identity. There is no cross-filesystem copy/delete fallback.
Retain the printed restore command and inspect the reported `Quarantined:` directory.

Restore only to an absent original path with the printed command. Inspect the restored clone with `git status`.
If verification fails, inspect both reported paths. There is no automatic purge, recovery database or crash-recovery service.
Keep paths quiet throughout the operation. Devtrees does not protect against hostile filesystem writers.

## Agent workflow routing

Make the included [Devtrees skill](../skills/devtrees/SKILL.md) available through your agent harness's skill-loading mechanism.
When loaded, it supersedes worktree invocations from requests, plans, commands and other skills.
The agent uses Devtrees for the corresponding task lifecycle. This does not replace the `git` executable or install a shell alias.

Existing linked worktrees are not converted or removed automatically.
The skill preserves testing, review and approval obligations while changing how agents create and retire task folders.

## Development checks

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use real local Git repositories and retain fixtures in Git-private storage.
Deletion-denying wrappers prevent the CLI tests from deleting clones. Reaching that guard verifies dispatch, not completed deletion.
