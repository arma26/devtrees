# Clone workspaces

Design notes for a CLI that replaces `git worktree` command invocations in documentation, instructions, and scripts while using ordinary independent clones instead of linked worktrees.

**Status:** design only. No CLI or skill is implemented. The working project name is not a selected executable name.

## Goal

Preserve familiar arguments, command behavior, and script-facing output wherever compatible with independent repositories. Change repository storage and workspace organization, not the user's development workflow.

The intended reader is the user designing the future script and skill. Start with [the design](docs/design.md) for accepted requirements and unresolved compatibility issues. [The glossary](GLOSSARY.md) defines the domain terms.

## Motivation

The user reports worktree-related failures in relative scripts, linking, container Git access, and package-manager cache behavior. These are target validation scenarios, not yet reproduced findings or claims about every tool.

## Example layout

```text
workspace/                 # not a repository
├── .env                   # example declaration: GITREPO='file:///example.git'
├── example.git/            # optional local bare repository
├── branch-a/               # ordinary independent clone
├── branch-b/               # ordinary independent clone
└── branch-c/               # ordinary independent clone
```

The example URI is preserved from the design discussion; path resolution is not yet specified. No particular checkout, including `main`, is required.
