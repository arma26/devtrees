---
name: devtrees
description: Use whenever worktree/worktrees are requested or proposed.
version: 0.2.1
platforms: [macos, linux]
metadata:
  hermes:
    tags: [devtrees, worktree, worktrees, git-worktree, isolation, clones]
---

# Devtrees instead of linked worktrees

Use Devtrees for any worktree invocation in an agent workflow.
This includes requests from users, plans, commands, agents, or other skills.
Translate instructions written as `git worktree` commands into the corresponding Devtrees workflow instead of invoking linked-worktree creation.
This replaces generic worktree setup and removal instructions, not testing, review, or preservation requirements.
An explanatory question does not authorize setup. Preserve existing linked worktrees unless the user explicitly requests a change.

Each clone has its own refs, index, stash, configuration, and objects.
Linked worktrees also have separate indexes, but share most repository storage.
A project-local bare hub receives task branches. The original checkout fetches and merges selected branches through native Git.
Devtrees has no registry, clone IDs, active environment, or merge coordinator.

## Before setup

For each new project workspace, ask:

> Where should I initialize the devtrees project workspace?

The workspace contains `.devtrees`, `hub.git`, and task clones. It is not the original checkout.
Use a location that the user supplied. Reuse an initialized workspace instead of creating one for each task.
Ask for the source repository too if it is unclear. Uncommitted work does not transfer through a clone.

1. Locate the executable with `command -v devtrees`, or use an executable path that the user supplied.
2. Ask for its location if unavailable. Do not install it or change PATH without authorization.
3. Require Python 3.9+, Git, `/bin/sh`, and `mv` with `-n` on a supported POSIX host.
4. Read `devtrees_root` from the shell. If unset, ask the user to approve an existing operating-root directory.
5. Set the root only for authorized calls. Do not edit shell startup files or choose a fallback root.
6. Verify that the project and clone paths resolve inside the root. Refuse the filesystem root and outward symlinks.
7. Run devtrees inside that root. The nearest sourceable `.devtrees` wins and cannot widen the shell-owned root.

Treat `.devtrees` as trusted executable shell configuration. Preserve existing configuration and destinations.
Read `--help` when command syntax is uncertain.

## Create a workspace and task clone

Populate these variables from verified, approved values. They are shell variables, not additional devtrees settings.

```sh
set -eu
# devtrees_bin: executable; project_dir: approved new workspace
# source_repo: committed source; branch_name and clone_path: selected task
cd -- "${devtrees_root:?Set the approved operating root first}"
"$devtrees_bin" init "$project_dir" "$source_repo"
cd -- "$project_dir"
"$devtrees_bin" add -b "$branch_name" "$clone_path"
cd -- "$clone_path"
git status
```

Skip `init` for an initialized workspace. Use an absolute clone path inside the root.
`init` creates a full-history bare hub and points `.devtrees` at it. It rejects a shallow source.
Task clones default to depth one. Use `init --clone-mode full` when task clones need full history.
Do not silently change an existing clone policy or deepen existing clones.
`add PATH START` selects a start point. `add -b BRANCH PATH [START]` creates a branch.
Native Git templates and settings apply.
Keep failed setup attempts for inspection.

Verify a real `.git/` directory and the intended branch with `git branch --show-current`.
Use ordinary `cd`, `git switch`, `git commit`, `git fetch`, `git pull`, and `git push` inside the clone.
Pass that clone as the subagent cwd. Repository-local Git needs no devtrees context.
Use the CodeGraph skill for its independent index. Linked-worktree index seeding does not apply to an independent clone.

## Exchange branches and integrate

Inspect `git remote -v`. Task `origin` should identify the project hub, not necessarily a hosted upstream.
Push only an authorized branch to an explicit remote. `devtrees push PATH REMOTE [REFSPEC...]` is an optional native Git handoff.
A successful push does not merge branches or preserve uncommitted files, ignored files, stashes, or local configuration.

The original checkout can add the hub as a separate remote, then fetch, review, and merge selected branches.
Keep its existing hosted `origin` and upstream settings unchanged. Do not register remotes or merge without authorization.
The hub is a snapshot and exchange point, not automatic synchronization or a separate-device backup.

## Discover and retire task clones

Use `devtrees list [DIRECTORY]` for discovery. It reads the filesystem and stops at clone roots.
Do not assume worktree porcelain flags or remembered membership. A rename needs no registry repair.

For requested task removal:

1. Inspect the clone and preserve all needed work using ordinary Git or other appropriate tools.
2. Verify delivery and obtain approval for the exact target. These are harness responsibilities, not CLI checks.
3. Stop writers and run `devtrees remove PATH` for the default dry run.
4. Use `devtrees remove PATH --please` only within the approved removal scope.
5. Verify `Removed:` and the continued presence of the hub, project configuration, and other clones.

`--please` deletes the entire clone even when work is dirty or unpublished. It does not prove preservation or delivery.
The CLI enforces path boundaries and protects the project, hub and configured source. It does not inspect Git storage.
Never remove a clone automatically merely because a task finished. Do not treat a dry run as proof of readiness.

Use explicit quarantine when the complete clone must remain:

- Obtain approval for `devtrees remove PATH --quarantine` and the exact selected clone.
- Require a real terminal and the user's exact `quarantine` confirmation.
- Do not pipe approval, simulate a terminal for the user, or add `--yes`.
- In a noninteractive session, stop with the plan and interactive command.
- Retain the printed restore command. Verify the reported `Quarantined:` directory.
- Restore only to an absent original path with the printed no-clobber command, under the applicable approval rules.
- Inspect both paths if verification fails. There is no automatic purge or cross-filesystem copy/delete fallback.

Do not invent merge, repair, prune, lock, unlock, move, or context-switch commands or recreate them through state files.
Explain any requirement for shared Git refs or exact worktree flags. Ask for a scoped decision instead of claiming compatibility.
You may inspect existing linked worktrees without changing them. Requirements for existing linked-worktree operations need a scoped decision, not automatic migration.

## Finish

Report the workspace, clone, branch, native Git status, and authorized push or removal result.
Leave integration and optional retirement to the user. Do not rewrite unrelated skills, scripts, project rules, or configuration.
