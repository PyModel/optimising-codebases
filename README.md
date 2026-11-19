# Optimise

Optimise audits a whole codebase. Scouts map the repository, specialists review the risks they uncover, and the skill verifies findings against the code and current primary sources. It reports defects, risks and justified improvements in priority order and applies fixes only when asked.

## Repository layout

- [SKILL.md](SKILL.md) defines the audit workflow and how to run the scripts.
- [references/](references/) covers orchestration, audit domains, verification, sources and the report contract.
- [scripts/](scripts/) inventories repository files and validates and renders audit reports.
- [assets/](assets/) contains the audit template and skill icon.
- [agents/openai.yaml](agents/openai.yaml) configures the skill’s display and invocation in OpenAI clients.
- [tests/](tests/) contains the Python unit tests for the scripts.

## Install

From the repository root, create the canonical symlink and the three relative links. OpenCode reads `~/.agents/skills` directly.

```sh
mkdir -p ~/.agents/skills ~/.claude/skills ~/.codex/skills ~/.pi/agent/skills
ln -sn "$PWD" ~/.agents/skills/optimise
ln -sn ../../.agents/skills/optimise ~/.claude/skills/optimise
ln -sn ../../.agents/skills/optimise ~/.codex/skills/optimise
ln -sn ../../../.agents/skills/optimise ~/.pi/agent/skills/optimise
```

## Run the tests

```sh
python3 -m unittest discover -s tests -v
```

MIT License, © 2026 PyModel LLC. See LICENSE.
