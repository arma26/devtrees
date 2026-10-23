# Design record

Audience: the user designing a worktree-compatible clone manager. Purpose: separate accepted requirements from proposals and expose the remaining compatibility decisions.

## Accepted requirements

- The selected project and CLI name is `devtrees`.
- Replace the `git worktree` command prefix in documentation, instructions, and scripts with `devtrees`. Worktree parity and drop-in command replacement are the design goal, not open product questions. Do not intercept Git's built-in command. Any incompatibility must remain an explicit unresolved obligation rather than silently narrowing the goal.
- Use ordinary independent full repositories, not linked worktrees, for development checkouts.
- Organize working clones under a workspace directory that is not itself a repository.
- A `.devtrees` configuration file supersedes the earlier `.env` proposal. It uses shell-sourceable environment syntax so subagents and containers can source it directly. It defines environment variables and identifies the target repository to replicate. Generated configuration should use exported assignments so child processes receive the values. The earlier repository declaration example was `GITREPO='file:///example.git'`; the complete fields and relative-path interpretation remain unspecified.
- Discover `.devtrees` by walking upward through parent directories from the invocation directory until a configuration file is found. Discovery must work at arbitrary depth within a clone; a Git repository boundary must not by itself stop the search.
- The nearest `.devtrees` wins. Stop at that file rather than combining ancestor configurations.
- A local `example.git` may be used as a bare repository, not a mirror. It may serve as both cache and authority for local branches; these roles are not exclusive. Its presence is not required.
- The checked-out branches are arbitrary. A `main` checkout is optional, not an integration prerequisite.
- The CLI model should accommodate acting in the appropriate repository to push or merge, and returning to the prior location. Exact commands and caller-shell navigation behavior remain undecided.
- Reuse native Git commands internally wherever possible. Devtrees supplies workspace structure, configuration/environment variables, repository selection, and automated directory context; it orchestrates Git rather than reimplementing Git behavior.
- Add `devtrees init` to create a new workspace directory, seed a default `.devtrees` configuration, and prepare the workspace for immediate branch checkout through subsequent devtrees commands without manual configuration repair.
- The likely deliverable is a script and skill intended to supersede worktree skills. Only design tracking is authorized now; implementation and bulk migration have not been authorized.

## Shell-sourceable configuration

Format example, not a real repository location or a complete default configuration:

```sh
export GITREPO='file:///example.git'
```

Subagents or container shells can source the selected file using ordinary shell syntax. Exported assignments make the values available to child commands. Prefer portable shell syntax in generated configuration so consumers do not require a particular interactive shell.

This supersedes the earlier assistant recommendation that the format be restricted to a data-only parser. It does not by itself settle automatic execution of arbitrary discovered files by the CLI. Sourcing shell code requires a trusted file; discovery is not a sandbox or a trust check. The CLI loading mechanism and trust handling remain to be specified without inventing custom variable-precedence semantics.

## Workspace initialization

`devtrees init` is an additional setup command, not a replacement for native `git init`: the workspace itself must remain a non-repository directory.

Required outcome:

- Create the requested new workspace directory without overwriting an existing destination.
- Seed `.devtrees` with the default configuration and the actual repository source supplied or resolved during initialization. A placeholder source is not sufficient for successful ready-to-work initialization.
- Prepare whatever minimal workspace state subsequent devtrees commands require, reusing native Git operations wherever needed.
- Leave the workspace ready to create independent branch checkouts immediately, with no required `main` checkout or other mandatory working clone.
- Keep the local bare repository optional; the exact opt-in syntax remains unspecified.
- Report initialization failures without claiming readiness, overwriting pre-existing data, or automatically deleting retained partial work.

Proposed invocation shape, not a finalized parser contract or an implemented command:

```sh
devtrees init <directory> <repository>
cd <directory>
devtrees add -b task-a ./task-a
```

Acceptance: after successful initialization, a subsequent `devtrees add` can resolve the repository through the generated `.devtrees` and create a usable independent clone without editing the configuration first. Exact default fields depend on the still-open configuration contract.

## Compatibility work remaining

These are design obligations to evaluate, not implemented features or approved implementation mechanisms.

### Command surface

Map the full worktree interface: `add`, `list`, `remove`, `move`, `lock`, `unlock`, `prune`, and `repair`. Inventory options and argument inference rather than supporting only the happy-path add/list/remove sequence. Choose an explicit Git compatibility baseline before defining exhaustive parity.

### Script contract

Preserve explicit destination paths, relative-path interpretation, exit statuses, stdout/stderr separation, quiet behavior, and parseable `list --porcelain` / `-z` output. Reconcile caller-specified paths with workspace-based defaults rather than silently relocating them. Upward `.devtrees` discovery is selected; its stopping and failure rules remain to be defined.

### Native Git delegation

Use native `git clone`, branch/checkout operations, `git fetch`, `git push`, `git merge`, and Git inspection commands as the implementation primitives. The wrapper selects the relevant repositories, supplies configuration, and runs commands in their directory context. Git remains responsible for object transfer, ref-update checks, merge behavior, and conflict reporting.

Cross-clone branch visibility is an orchestration and compatibility-test obligation, not justification for a bespoke replication engine or a separate synchronization product. Native transfer commands must make the required commits available at the appropriate operation boundary, with and without the optional bare repository. The exact sequence remains implementation work.

Keep the verified limitation visible: independent clones do not automatically share refs, so matching the management command alone does not establish that an unchanged ordinary `git merge task-branch` sees a newly committed sibling branch. Do not claim that parity until the native command sequence has been exercised against the relevant workflow.

### Preservation and lifecycle

Clones can contain unique committed history as well as uncommitted and ignored files. Removal must account for recoverability of all local work, not only a clean working directory. Define lock persistence, stale entries, moved repositories, repair, and failure recovery. Do not reinterpret prune as deletion of working repositories. Existing user filesystem-preservation rules remain applicable; destructive flag compatibility cannot silently override them.

### Repository isolation and portability

Validate ordinary Git operations when only a working clone is mounted into a container. Check for external object-store dependencies and define clone behavior that does not require access to another repository's filesystem. Validate the user's actual scripts, linking tools, and package-manager cache workflows before claiming those problems are resolved. Define treatment of submodules, Git LFS, configuration, and hooks rather than assuming ordinary clone defaults reproduce all worktree behavior.

## Proposed discovery boundary

The user proposed an optional globally defined shell environment variable named `devtrees_root` to prevent discovery from walking outside the workspaces directory. Preserve that spelling. It is a search-boundary proposal, not authorization to restrict every operation to that directory.

Illustrative layout, not a fixed path requirement:

```text
workspaces/
└── project/
    ├── .devtrees
    ├── branch-a/
    └── branch-b/
```

Discovery stops at the first `.devtrees` file encountered; it does not combine ancestor files. The proposed boundary variable's adoption, inclusive boundary behavior, unset/invalid/outside-root cases, and symbolic-link treatment remain unresolved. Missing or malformed configuration must not be silently equated with an approved default; removal of configuration must not imply permission to delete or modify retained clones.

## Remaining design decisions

The parity goal is settled. The remaining decisions concern mechanisms and genuinely new configuration behavior:

1. Configuration contract: the shell-sourceable environment format and nearest-file selection are settled. Complete the target-repository fields, relative-path bases, CLI loading/trust handling, and missing/malformed/removed-config behavior. Do not reopen the file-format decision or imply that the earlier assistant defaults were all approved.
2. Discovery boundary: decide the proposed `devtrees_root` semantics and how upward traversal handles symlinks and invocation outside the boundary.
3. Membership authority: select how commands identify and retain workspace membership, including moved or missing clones and explicit destinations. Hidden registry versus filesystem discovery is an implementation choice, not a reason to reopen worktree command parity.
4. Compatibility and preservation: choose a Git baseline and resolve any conflict between destructive worktree flags and existing user preservation requirements. A clean clone may still contain unique committed history.

Exact flag support, exit statuses, and output formats should be derived from the chosen Git baseline, not repeatedly redesigned. Native Git orchestration, shell navigation, integration, and recovery mechanisms remain implementation work subject to the accepted parity goal, not a new synchronization-system design interview. Implementation and bulk migration remain unauthorized.

## Sources and limitations

Accepted requirements come from the design conversation. The command inventory was checked against the official Git worktree documentation and local Git 2.50.1 help. The Git compatibility baseline remains undecided.

A local probe created two independent clones of the same source, created and committed `task-b` in one, and checked the other with `git rev-parse --verify refs/heads/task-b`. The other clone returned exit status 128: no such local branch was available without synchronization. This verifies the basic branch-visibility gap, not a proposed synchronization solution.

No replacement CLI behavior has been implemented or validated. No ADR is recorded yet: concrete implementation trade-offs remain open.
