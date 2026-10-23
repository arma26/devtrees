# Devtrees

Design notes for a CLI that replaces `git worktree` command invocations in documentation, instructions, and scripts while using ordinary independent clones instead of linked worktrees.

**Status:** design only. The selected project and CLI name is `devtrees`. No CLI or skill is implemented.

## Goal

Provide worktree command parity so documentation, instructions, and scripts can replace the `git worktree` command prefix with `devtrees`. Change repository storage and workspace organization, not the user's development workflow. Any compatibility gap is an unresolved design obligation, not permission to change the goal.

Devtrees is a thin orchestration layer over native Git commands: it supplies directory structure, configuration/environment variables, and execution context rather than reimplementing cloning, transfers, branching, or merging.

The intended reader is the user designing the future script and skill. Start with [the design](docs/design.md) for accepted requirements and unresolved compatibility issues. [The glossary](GLOSSARY.md) defines the domain terms.

## Motivation

The user reports worktree-related failures in relative scripts, linking, container Git access, and package-manager cache behavior. These are target validation scenarios, not yet reproduced findings or claims about every tool.

## Example layout

```text
workspace/                 # not a repository
├── .devtrees              # config: environment definitions and target repository
├── example.git/            # optional local bare repository
├── branch-a/               # ordinary independent clone
├── branch-b/               # ordinary independent clone
└── branch-c/               # ordinary independent clone
```

Commands discover `.devtrees` by walking upward from the current directory, including from deeply nested directories inside a clone. No particular checkout, including `main`, is required. An optional shell variable named `devtrees_root` has been proposed to bound discovery; its semantics are not settled.
