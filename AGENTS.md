# Repository guidance

This repo is one agent skill, `audit-codebase` (folder name `optimise`; the installed link name is what agents see).

- Installed as a symlink to this working tree: `~/.agents/skills/audit-codebase` → here, with relative links from
  `~/.claude/skills`, `~/.codex/skills` and `~/.pi/agent/skills` (opencode reads `~/.agents/skills`).
  Every saved edit is live in all four agents at once; keep `main` working.
- Scripts are Python 3.10+ standard library only, no shell, read-only against the audited repo.
  Every behavior change gets a test in `tests/` that fails on the old code.
- Before committing: `python3 -m unittest discover -s tests -v`.
