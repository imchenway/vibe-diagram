# Vibe Diagram

`vibe-diagram` is a portable Agent Skill that turns code, documentation, and requirements into self-contained, single-file HTML visuals for architecture, workflows, sequences, state models, and technical designs.

## Install

### Codex

Send this in Codex:

```text
Use $skill-installer to install https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram
```

After installation, start a new Codex task and describe the diagram you need.

### TRAE

Install the Skill once at user level to make it available in every project. Node.js 18+ and a Python 3 executable named `python3` are required.

TRAE international:

```bash
npx --yes skills@latest add https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram --skill vibe-diagram --agent trae --global --copy --yes
```

TRAE China:

```bash
npx --yes skills@latest add https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram --skill vibe-diagram --agent trae-cn --global --copy --yes
```

The command copies the complete Skill, including its scripts, references, contracts, and templates. After installation, start a new TRAE conversation and ask it to use `vibe-diagram`.
