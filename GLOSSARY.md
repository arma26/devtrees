# Devtrees

A workspace groups independent development checkouts while preserving familiar worktree-management workflows.

## Language

**Operating root**:
The user-selected directory that bounds where Devtrees may discover and manage workspaces and development repositories.

**Workspace**:
A non-repository directory containing related working clones and their workspace configuration.

**Devtree**:
An independent repository used for development within a workspace. A workspace does not require a designated main checkout.
_Avoid_: Linked worktree

**Local bare repository**:
An optional repository within a workspace that can serve as both a local cache and an authoritative destination for local branches.
_Avoid_: Mirror, mandatory hub
