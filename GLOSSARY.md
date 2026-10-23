# Terminology

- **Environment / devtree:** an ordinary independent Git clone directory.
- **Workspace:** a normal directory with sourceable `.devtrees` configuration.
- **Operating root:** shell-provided `devtrees_root`, bounding devtrees operations.
- **Discovery:** inspecting current directories and Git, not consulting a registry.
- **Handoff:** native Git push to an explicitly selected remote; not merging.
- **Dry-run:** resource/restore plan without a move.
- **Quarantine:** an approved same-filesystem move, retaining the complete clone.
- **Manifest:** the printed resource inventory and restore mapping; not a database.
