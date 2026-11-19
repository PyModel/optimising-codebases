The repository folder is `optimise`. Agents see its single skill as `optimising-codebases`, the installed link name and frontmatter `name`.

- Installed as a symlink to this working tree: `~/.agents/skills/optimising-codebases` → here, with relative links from
  `~/.claude/skills`, `~/.codex/skills` and `~/.pi/agent/skills` (opencode reads `~/.agents/skills`).
  Every saved edit is live in all four agents at once; keep `main` working.
- Scripts are Python 3.10+ standard library only, no shell, and standalone: each must run under
  `python3 -I` (no sibling imports). They never edit the audited repo's files; `git status` with the
  user's own global git-lfs filter may add objects under its `.git/lfs`.
  Every behavior change gets a test in `tests/` that fails on the old code.
- Before committing: `python3 -m unittest discover -s tests -v`.
