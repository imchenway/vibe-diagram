# vibe-diagram

Chinese overview: [README.zh-CN.md](README.zh-CN.md).

## What it is

`vibe-diagram` is a portable agent skill for producing self-contained HTML diagrams. The repository holds one host-neutral canonical skill and deterministic package definitions for four client families. The current Unreleased 0.1.0 stable-candidate snapshot is not a published stable release or an aggregate client-runtime compatibility claim.

## Repository model

`skills/vibe-diagram/` is the only editable source for skill behavior. That directory contains `SKILL.md`, 11 references, 58 HTML templates, and one standard-library linter. It has zero third-party runtime dependencies.

Client manifests and overlays live under `adapters/`. Generated outputs are disposable artifacts and must not be edited by hand:

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

No generated package is a second source of truth.

The repository-root `plugins/vibe-diagram/` tree is the builder-only generated projection included for Codex publication. It is not canonical and must not be edited by hand. The deterministic repo marketplace catalog is `.agents/plugins/marketplace.json`, which points to `./plugins/vibe-diagram`.

## Codex installation

The public repository is <https://github.com/imchenway/vibe-diagram>. Its two public Codex source structures are the repo marketplace backed by `.agents/plugins/marketplace.json` and the GitHub skill path backed by `skills/vibe-diagram/`.

GitHub installation instructions are pinned to RC `v0.1.0-rc.2`. Runtime verification for this RC remains `Unverified`: installation, discovery, invocation, HTML delivery, upgrade, and uninstall have not been established for any client surface. These instructions identify source paths and do not claim stable support or aggregate compatibility.

### Codex App plugin

Use the Codex CLI bundled with the macOS Codex App, or another compatible `codex` executable:

```bash
codex plugin marketplace add imchenway/vibe-diagram --ref v0.1.0-rc.2
codex plugin add vibe-diagram@imchenway
```

Start a new Codex task after installation so the new skill catalog is loaded. To uninstall the plugin and repository marketplace:

```bash
codex plugin remove vibe-diagram@imchenway
codex plugin marketplace remove imchenway
```

### GitHub skill path

In a Codex task, ask:

> Use `$skill-installer` to install `https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.2/skills/vibe-diagram`.

Start a new Codex task after the installer completes.

## Artifact contract

Every package contains the canonical skill byte-for-byte, a root `LICENSE`, and exactly one client manifest. The Codex package additionally contains its allowlisted `agents/openai.yaml`. The builder rejects symlinks, path escapes, unlisted files, remote resources, manifest drift, and canonical hash drift.

All four packages are assembled in one staging tree. Publishing replaces the complete `build/` tree as one transaction with rollback to the previous tree when promotion fails.

## Static build

The supported static verification commands are:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.9 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --check
```

To generate the local package tree after those checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --output build
```

The builder uses only the Python standard library and reads the package version from `VERSION`.

The explicit local projection command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --sync-publication
```

`--sync-publication` is the only publication write entry point. `--check` is read-only: it detects publication drift but does not repair publication files.

## Package layouts

| Client family | Manifest in generated package | Canonical skill |
|---|---|---|
| Codex | `.codex-plugin/plugin.json` | `skills/vibe-diagram/` |
| Claude Code | `.claude-plugin/plugin.json` | `skills/vibe-diagram/` |
| Gemini CLI | `gemini-extension.json` | `skills/vibe-diagram/` |
| GitHub Copilot CLI | `plugin.json` | `skills/vibe-diagram/` |

These layouts are static package definitions. They do not constitute installation, discovery, invocation, HTML-delivery, upgrade, or uninstall verification.

## Validation status

A build report value of `static_validation: passed` is package-static-valid and only means the builder production preflight passed for that generated tree. It does not prove the complete unit suite, deterministic process checks, or the second complete suite. Static-valid status requires those commands to pass together; the evidence remains in command or CI output and is not committed as repository documentation.

Runtime verification remains `Unverified` for the local 0.1.0 candidate. No installation, discovery, invocation, HTML-delivery, upgrade, or uninstall result is inherited from an earlier tag. Stable publication remains blocked until current, scoped real-client evidence exists.

## License

Apache-2.0. See [LICENSE](LICENSE).
