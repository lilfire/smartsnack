# CLAUDE.md

## Branch Policy

- **`main` is protected.** No agent may push, commit, or create pull requests targeting `main`. Only the board (repo owner) may create PRs into `main`.
- **All agent work targets `development`.** Feature branches must be created from `development` and PRs must target `development`.
- **Direct commits to `main` are blocked** by GitHub branch protection (requires PR + review + admin enforcement).
