# Design: stateless clone storage

Devtrees supplies directory setup, filesystem discovery, an optional native Git
push handoff, and dry-run or quarantine teardown. Each environment is an ordinary
independent clone. All repository-local work and all merging belong to Git and
the user.

## State and authority

There is no clone registry, generated clone identity, membership cache, internal
merge, shared-ref emulation, persistent lock database, or environment selector.
Git owns repository state. Directories determine which environments exist.
`.devtrees` is sourceable configuration, not a database. The shell supplies the
mandatory `devtrees_root`; the nearest configuration supplies the source and
shallow/full policy.

## Preservation

New destinations are exclusive. Cloning uses native Git without local object
sharing. Clone failures remain available for inspection. Selection for push or
teardown requires an actual ordinary repository, not a linked-worktree pointer or
selected symlink. Paths must stay within the operating root.

Teardown defaults to a non-mutating plan. An interactive quarantine prints the
exact resources and restore mapping, obtains approval, rechecks the source and
destination, performs a same-filesystem no-clobber move, and verifies the result.
Its inventory is transient; its manifest is stdout for the caller to retain.
There is no purge, automatic cleanup, cross-filesystem copy/delete fallback,
crash-recovery service or hostile-writer sandbox. Keep the clone quiet during
confirmation and application.

## Scope

Python and its standard library are the implementation. Perl and exact Git
worktree parity are out of scope, as are missing-registration recovery,
prospective filesystem-collation emulation, merge orchestration, cache sharing,
daemons and global instruction/script migration. Old experiments are preserved
outside the product rather than incorporated into this design.
