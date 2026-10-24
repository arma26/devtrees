# Design of the bare hub workflow

Devtrees creates project workspaces and ordinary independent task clones.
A project workspace contains a sourceable `.devtrees` configuration and a bare Git repository named `hub.git`.
The hub stores committed branches without a checked-out working tree.
The original checkout remains the place where the user reviews and integrates task branches.
See the [quick start](../README.md#quick-start) for the complete command sequence.

## Responsibilities and lifetime

- `init` creates a full bare clone at `project/hub.git` and points `.devtrees` at it.
  It rejects shallow sources. It prints a remote-registration command but does not change the original checkout's remotes.
- `add` creates an independent clone from the configured source. In the default project layout, that source is the hub.
  Each task has its own `.git/` directory. Use a distinct branch for each task. Its `origin` points to the hub.
  Native Git templates and settings apply.
- `push` invokes native Git push to the selected remote. It neither merges branches nor synchronizes clones.
- Native Git `fetch` in the original checkout updates remote-tracking references through the additional `devtrees` remote.
  The user reviews each branch before an explicit native Git `merge`. The existing hosted `origin` remains unchanged.
- `remove PATH --dry-run` inspects the proposed operation without removing the clone.
  `remove PATH --please` deletes the selected clone. Explicit `--quarantine` preserves the complete clone instead.

The hub starts as a snapshot, not a live synchronization service.
Transfer a newer committed base explicitly before tasks that need it.

Only committed history crosses repositories. Branch pushes do not preserve uncommitted changes, untracked or ignored files, or stashes.

Task removal keeps the configuration, hub and sibling clones.
Hub retirement is a separate decision because it can hold branches absent from the original checkout or hosted upstream.
A local hub is not a separate-device backup.

There is no automatic merge, branch deletion, force-push, hosted publication or cleanup after a task.

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
The default project configuration points `devtrees_repo` at `hub.git` and selects shallow task clones.
The supported settings have this form:

```sh
export devtrees_repo='/path/to/project/hub.git'
export devtrees_clone_mode='shallow'  # or full
```

`.devtrees` is trusted shell code, loaded with `/bin/sh -eu`. It must not print to stdout.
Only the source and clone-mode settings cross that interface, as NUL-delimited fields, not JSON.
Configuration cannot widen the shell-provided root.
Git hooks, shell configuration and remote endpoints remain trusted inputs. Devtrees is not an operating-system sandbox.

Shallow task clones use depth one for available branch tips.
`init --clone-mode full` or `devtrees_clone_mode=full` selects full task history. Full mode rejects shallow sources.
This task policy does not change the full-history hub created by `init`.

Existing clones are never silently deepened. Use native Git for older history.

`add PATH START` checks out a start point. `add -b BRANCH PATH [START]` creates a branch with native Git.

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
The root boundary is path containment, not an operating-system sandbox.
See [task removal](../README.md#remove-a-task) for the commands and their effects.

Quarantine preserves the complete clone through an explicit same-filesystem no-clobber move.
It prints source, destination and restore command, then requires terminal approval with the exact word `quarantine`.
The destination is a new private directory beneath `$devtrees_root/.devtrees-quarantine/`.
It verifies the moved directory identity. There is no copy/delete fallback, purge or crash-recovery service.
See [quarantine](../README.md#preserve-a-clone-with-quarantine) for verification and restoration.

## Scope

Python and its standard library implement Devtrees.
Task clones do not share objects, refs, indexes, stashes or repository configuration.
They are not linked Git worktrees. See the [comparison](../README.md#similar-to-and-different-from-linked-git-worktrees).
Exact Git-worktree flag parity, cache sharing, daemons and global instruction/script migration are outside this design.
So are Perl, missing-registration recovery and prospective filesystem-collation emulation.
Old experiments remain outside the product.
