# Devtrees

Give each parallel task its own Git repository, then bring finished work back into your original checkout.

Devtrees is a drop-in replacement for the worktree workflow, using isolated clones instead of linked worktrees.
Create a task folder, work inside it, share the branch, then retire the folder.
Use ordinary Git commands inside each task.
When loaded in your agent harness, the included [skill](skills/devtrees/SKILL.md) supersedes worktree invocations and instructions.
Agents use Devtrees instead. Existing linked worktrees are not converted automatically.

## Start parallel tasks

Requires Python 3.9+, Git and `/bin/sh` on a POSIX host. No Python packages need installation.
Quarantine also requires `mv` with `-n` support.

Clone Devtrees and add its command to PATH for the current shell:

```sh
git clone https://github.com/arma26/devtrees.git
export PATH="$PWD/devtrees/bin:$PATH"
```

If you already have a checkout, add that checkout's `bin` directory instead.
Choose where task workspaces live, then create two tasks from your project:

```sh
set -eu
export devtrees_root="$HOME/environments"
mkdir -p -- "${devtrees_root:?}"
cd -- "$devtrees_root"
devtrees init project /absolute/path/to/your-project
cd project
devtrees add -b agent/task-a ./task-a
devtrees add -b agent/task-b ./task-b
devtrees list
```

Replace `/absolute/path/to/your-project` with a checkout that has full Git history.

`init` creates a workspace with a local **hub**, a bare Git repository that receives task branches without checked-out files.
It copies committed history, not uncommitted changes. It does not change your original checkout's remotes or working files.

Each `add` creates an independent task folder on the named branch, with the hub as its `origin`.
`list` prints the task paths. Give each agent its task folder as its working directory.
Task clones start with depth-one history. [Choose full history](docs/design.md#configuration-and-root-boundary) when a task needs older commits.

Existing destinations are refused. If setup fails, inspect the retained partial directory before choosing another destination.

## Share a task's work

Work and commit inside each task folder using ordinary Git. When a branch is ready to share, push it:

```sh
cd -- "$devtrees_root/project/task-a"
git push --set-upstream origin agent/task-a
```

The hub now holds the branch. Pushing does not merge it, update other task clones, or change your original working files.
Only committed work transfers. If the push fails, keep the clone and inspect Git's error before retiring it.

## Bring work into your original checkout

Preserve any local changes first. Select the branch where you want to integrate the task.
Add the hub as a separate remote once, keeping your existing `origin`:

```sh
cd -- /absolute/path/to/your-project
git remote add devtrees "$devtrees_root/project/hub.git"
git fetch devtrees
git diff HEAD...devtrees/agent/task-a
git merge devtrees/agent/task-a
```

If a `devtrees` remote already exists, inspect its URL instead of replacing it.
Fetch makes the task branch available for review without changing working files. Merge applies the chosen branch's changes.
Check `git status` afterward. Resolve conflicts through your usual Git workflow, and review each task branch separately.

The hub is not a live mirror of your original checkout.
[Transfer a newer base explicitly](docs/design.md#branch-handoff-and-integration-checks) before starting tasks that need your latest integration.

## Retire a task

You or your agent harness decides when work is delivered and ready for removal.
Devtrees does not check whether you committed, pushed or merged it.

Stop writers and preview the selected folder:

```sh
cd -- "$devtrees_root/project"
devtrees remove ./task-a
```

Check the printed path. This command does not delete or move the clone.
After preserving everything you need and approving that exact target, delete it explicitly:

```sh
devtrees remove ./task-a --please
```

**`--please`** deletes the whole clone, including uncommitted, untracked and ignored files, stashes and local settings.
It does not create a backup. The hub and other task clones remain.
`Removed:` reports success. `devtrees list` should no longer show that task.
If deletion fails partway, inspect what remains. Do not assume rollback.

Use [quarantine](docs/design.md#quarantine-and-restore) when you want to retain the complete clone instead of deleting it.

## Worktree workflow, isolated repositories

The task lifecycle stays the same. Repository state and branch exchange behave differently:

| Action or behavior | Linked Git worktrees | Devtrees |
| --- | --- | --- |
| Start a task | `git worktree add -b agent/task-a ./task-a` | `devtrees add -b agent/task-a ./task-a` from the workspace |
| Work inside the task | `cd task-a`, then ordinary Git commands | The same |
| Working files and index | Separate for each worktree | Separate for each clone |
| Branches and repository settings | Refs, objects and most settings are shared | Each clone has its own refs and repository settings |
| Available history | Uses the shared repository history | Task clones default to depth one. Full history is optional. The hub has full history |
| See another task's commits | Shared refs make them available in the same repository | Push to the hub, then fetch where needed |
| Integrate a task | Review and merge with ordinary Git | Review and merge with ordinary Git after fetching from the hub |
| List task folders | `git worktree list` | `devtrees list` |
| Preview retirement | Inspect the task before `git worktree remove` | `devtrees remove ./task-a` previews without deleting |
| Remove the task folder | `git worktree remove ./task-a` applies Git's removal checks | `devtrees remove ./task-a --please` deletes the selected clone. The caller decides readiness |
| Mount the task in a container | Its `.git` pointer depends on shared repository metadata | Its `.git/` directory travels with the clone |
| Ask an agent for a worktree | The agent's usual worktree instructions apply | The included skill supersedes those instructions and uses Devtrees |

This replaces the agent workflow, not the `git` executable or every worktree flag.
Existing linked worktrees are not migrated automatically.

## More detail

- [Workflow reference](docs/design.md): commands, configuration, history choices, path boundaries, handoff checks and recovery.
- [Development checks](docs/design.md#development-checks): the repository's test command and fixture behavior.
- [Terminology](GLOSSARY.md): names used throughout the workflow.
