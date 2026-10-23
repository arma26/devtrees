# Design record

Audience: the user designing a worktree-compatible clone manager. Purpose: separate accepted requirements from proposals and expose the remaining compatibility decisions.

## Accepted requirements

- Replace the `git worktree` command prefix in documentation, instructions, and scripts with a new CLI command. Preserve the remaining workflow as far as the replacement contract requires; do not intercept Git's built-in command.
- Use ordinary independent full repositories, not linked worktrees, for development checkouts.
- Organize working clones under a workspace directory that is not itself a repository.
- An optional workspace `.env` example defines `GITREPO='file:///example.git'`. Required fields, lookup, and evaluation rules remain unspecified.
- A local `example.git` may be used as a bare repository, not a mirror. It may serve as both cache and authority for local branches; these roles are not exclusive. Its presence is not required.
- The checked-out branches are arbitrary. A `main` checkout is optional, not an integration prerequisite.
- The CLI model should accommodate acting in the appropriate repository to push or merge, and returning to the prior location. Exact commands and caller-shell navigation behavior remain undecided.
- The likely deliverable is a script and skill intended to supersede worktree skills. Only design tracking is authorized now; implementation and bulk migration have not been authorized.

## Compatibility work remaining

These are design obligations to evaluate, not implemented features or approved implementation mechanisms.

### Command surface

Map the full worktree interface: `add`, `list`, `remove`, `move`, `lock`, `unlock`, `prune`, and `repair`. Inventory options and argument inference rather than supporting only the happy-path add/list/remove sequence. Choose an explicit Git compatibility baseline before defining exhaustive parity.

### Script contract

Preserve explicit destination paths, relative-path interpretation, exit statuses, stdout/stderr separation, quiet behavior, and parseable `list --porcelain` / `-z` output where required. Reconcile caller-specified paths with the workspace layout rather than silently relocating them. Define discovery from the workspace root, from a member clone, and from an external invocation.

### Cross-clone Git behavior

Independent clones do not supply shared branch state merely by replacing the management command. In particular, an unchanged workflow can create a task checkout, commit there, return to another checkout, and run `git merge task-branch`. The required visibility of that task branch and its latest commit is the central unresolved compatibility problem.

Decide which unchanged ordinary Git operations must work, and when/how commits and refs become available to sibling repositories. Do not silently treat a newly introduced manual fetch or integration command as identical behavior. Specify operation with and without the optional local bare repository, including unavailable sources, divergent branches, and concurrent writers.

### Preservation and lifecycle

Clones can contain unique committed history as well as uncommitted and ignored files. Removal must account for recoverability of all local work, not only a clean working directory. Define lock persistence, stale entries, moved repositories, repair, and failure recovery. Do not reinterpret prune as deletion of working repositories. Existing user filesystem-preservation rules remain applicable; destructive flag compatibility cannot silently override them.

### Repository isolation and portability

Validate ordinary Git operations when only a working clone is mounted into a container. Check for external object-store dependencies and define clone behavior that does not require access to another repository's filesystem. Validate the user's actual scripts, linking tools, and package-manager cache workflows before claiming those problems are resolved. Define treatment of submodules, Git LFS, configuration, and hooks rather than assuming ordinary clone defaults reproduce all worktree behavior.

## Open design frontier

1. Compatibility boundary: must unchanged ordinary Git commands observe new commits and branches across working clones, or may integration sites explicitly adopt the new CLI?
2. Explicit paths versus managed layout: preserve caller-provided paths, provide workspace-based defaults, or constrain all destinations?
3. Configuration authority: identify the source when the local bare repository is absent; define missing/conflicting configuration and deliberate removal of configuration without losing or modifying existing clones.
4. Select the executable name and Git compatibility baseline.

Later branches depend on these answers: synchronization mechanism, conflict handling, shell integration, registry format, and migration of existing worktree instructions. No mechanism has been selected.

## Sources and limitations

Accepted requirements come from the design conversation. The command inventory was checked against the official Git worktree documentation and local Git 2.50.1 help. The Git compatibility baseline remains undecided.

A local probe created two independent clones of the same source, created and committed `task-b` in one, and checked the other with `git rev-parse --verify refs/heads/task-b`. The other clone returned exit status 128: no such local branch was available without synchronization. This verifies the basic branch-visibility gap, not a proposed synchronization solution.

No replacement CLI behavior has been implemented or validated. No ADR is recorded yet: concrete implementation trade-offs remain open.
