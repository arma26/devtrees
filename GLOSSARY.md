# Terminology

- **Task environment / devtree:** an ordinary independent Git clone directory with its own `.git/` directory.
- **Project workspace:** a directory with sourceable `.devtrees` configuration and, after `init`, a bare hub.
- **Bare hub:** the project's `hub.git` repository, without checked-out files, used to retain committed branches from task clones.
- **Original checkout:** the checkout where the user fetches, reviews and merges task branches through native Git.
- **Task branch:** a distinct branch for one task, pushed to the hub rather than merged automatically.
- **Operating root:** the shell-provided `devtrees_root` that bounds Devtrees calls and target paths.
- **Discovery:** inspection of current directories and Git, without a membership registry.
- **Handoff:** a native Git push to a selected remote. It transfers committed history, not uncommitted files or stashes.
- **Normal removal:** explicit deletion of the selected clone with `--please`. The caller decides readiness.
- **Dry-run:** inspection of the proposed removal or preservation operation without removing or moving the clone.
- **Quarantine:** a terminal-approved, verified same-filesystem move that preserves the complete clone and its local-only work.
- **Linked worktree:** a Git-managed checkout that shares repository storage instead of having an independent clone's `.git/` directory.

See the [quick start](README.md#quick-start) and [design](docs/design.md) for commands and limits.
