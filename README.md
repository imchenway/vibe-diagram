# vibe-diagram

Chinese overview: [README.zh-CN.md](README.zh-CN.md).

## What it is

`vibe-diagram` is a portable agent skill for producing self-contained HTML diagrams. The repository holds one host-neutral canonical skill and deterministic package definitions for four client families. The current repository version is declared by `VERSION`; `v0.1.1` established the released update-capable standalone Skill lane, while `v0.1.3` made current and offline checks read-only and removed generated-plugin ambiguity from release archives. The GitHub Skill evidence does not claim aggregate compatibility across every generated client package.

## Repository model

`skills/vibe-diagram/` is the only editable source for skill behavior. That directory contains the bootstrap `SKILL.md`, 12 references, 58 HTML templates, a standard-library updater, and a standard-library linter. It has zero third-party runtime dependencies.

Client manifests and overlays live under `adapters/`. Generated outputs are disposable artifacts and must not be edited by hand:

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

No generated package is a second source of truth.

The repository-root `plugins/vibe-diagram/` tree is the builder-only generated projection included for Codex publication. It is not canonical and must not be edited by hand. The deterministic repo marketplace catalog is `.agents/plugins/marketplace.json`, which points to `./plugins/vibe-diagram`.

## Codex Skill installation

The public repository is <https://github.com/imchenway/vibe-diagram>. The moving `stable` ref is live, and the permanent standalone Skill source is:

<https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram>

The permanent URL is a moving install channel for new direct installations. Every direct-installed `0.1.1+` invocation fetches the small stable manifest, compares strict versions, and upgrades from an immutable version tag before loading the runtime workflow. Network failure or an invalid release keeps the installed version available. Package-managed generated copies skip self-update.

Public GitHub-path evidence covers installation from `stable`, fresh-process discovery and invocation, HTML delivery with bundled-linter repair, an offline fail-open check, and an online current-version check at `v0.1.1`. The first real `v0.1.1` to `v0.1.2` attempt safely kept the installed tree because the full repository ZIP exposed both canonical and generated-plugin version markers. Repository version `0.1.3` adds an archive export rule and exact canonical-root selection; a successful public replacement remains outside the evidence until that release is promoted and exercised.

### Install from a Codex task

Ask Codex:

> Use `$skill-installer` to install `https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram`.

Start a new Codex task after installation so the new Skill catalog is loaded. A simple first invocation is:

> Use `$vibe-diagram` to create a self-contained HTML architecture diagram for this repository and run the bundled linter.

### Install with the bundled helper

The system Skill installer can also be called directly:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref stable
```

The helper stops when `$CODEX_ROOT/skills/vibe-diagram` already exists. Use the recoverable replacement flow below instead of overwriting an installed copy.

### One-time bridge from `v0.1.0`

`v0.1.0` does not contain the updater. After `v0.1.1` is published, move the installed Skill outside the discovery directory once, then install the pinned bridge release:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
BACKUP_ROOT="$CODEX_ROOT/backups/skills"
BACKUP_PATH="$BACKUP_ROOT/vibe-diagram-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_ROOT"
mv "$CODEX_ROOT/skills/vibe-diagram" "$BACKUP_PATH"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref v0.1.1
```

Keep the backup until the replacement has passed a new-task invocation and its bundled linter. Do not move or rewrite the immutable `v0.1.0` tag.

### Automatic and manual updates

For a direct-installed `v0.1.1+` copy, the bootstrap runs the update gate on every invocation. It silently continues when current, installs a verified newer stable tag before loading the runtime workflow, and continues with the local version when the stable source is unavailable. Starting with `v0.1.2`, current and offline checks do not create a lock file; write permission is needed only after a newer version is detected. Starting with `v0.1.3`, release archives export only the canonical version marker, while the updater also requires the exact repository-root canonical path. The host may still require network or filesystem approval for activation.

Ask the installed Skill to update explicitly:

> Use `$vibe-diagram` to update itself to the latest stable version.

Or run the public manual command:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/vibe-diagram/scripts/update_skill.py" \
  --force-check \
  --json
```

The updater downloads to a sibling staging directory, validates the release manifest and tree digest, retains a recoverable backup, and activates the new tree only after validation. Roll back to the newest retained backup with:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/vibe-diagram/scripts/update_skill.py" --rollback --json
```

### Recoverable uninstall

Move the Skill outside `$CODEX_ROOT/skills/` so a new Codex task no longer discovers it:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
BACKUP_ROOT="$CODEX_ROOT/backups/skills"
BACKUP_PATH="$BACKUP_ROOT/vibe-diagram-uninstalled-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_ROOT"
mv "$CODEX_ROOT/skills/vibe-diagram" "$BACKUP_PATH"
```

Start a new Codex task after removal. Restore the selected backup to `$CODEX_ROOT/skills/vibe-diagram` if you need to roll back.

### Searchability boundary

GitHub-path installation is a direct-install lane. It does not add `vibe-diagram` to the curated `$skill-installer` index or the public Plugins Directory. The repository also contains the separate builder-generated Codex marketplace projection under `plugins/vibe-diagram/` and `.agents/plugins/marketplace.json`; that plugin publication path has its own review lifecycle.

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

## GitHub Skill release orchestration

The standard-library release entry point currently implements R00-R07 plus the local contributor and read-only CI slice of R08. Contributors can prepare a candidate, run the complete local gate, refresh read-only remote evidence, and exercise the isolated updater lifecycle. A maintainer or fork owner with repository write permission can invoke the guarded `publish` phase and then separately authorize stable promotion and installed-client verification. See [CONTRIBUTING.md](CONTRIBUTING.md) for the role-specific fork flow and maintainer checklist:

```bash
python3 scripts/release_github_skill.py prepare --version 0.1.4 --dry-run --json
python3 scripts/release_github_skill.py prepare --version 0.1.4 --json
python3 scripts/release_github_skill.py verify --version 0.1.4 --json
python3 scripts/release_github_skill.py status --version 0.1.4 --refresh --json
python3 scripts/release_github_skill.py publish --version 0.1.4 \
  --commit <main-merge-sha> \
  --notes-file /absolute/path/to/release-notes.md \
  --confirm-remote-actions \
  --json
python3 scripts/release_github_skill.py promote-stable --version 0.1.4 \
  --confirm-stable-promotion \
  --json
python3 scripts/release_github_skill.py verify-runtime --version 0.1.4 \
  --mode isolated \
  --json
python3 scripts/release_github_skill.py verify-runtime --version 0.1.4 \
  --mode installed-client \
  --artifact /absolute/path/to/runtime-smoke.html \
  --confirm-installed-skill-mutation \
  --json
```

`prepare` updates release metadata and delegates the tracked publication projection to the repository builder. `verify` runs Python 3.9 and the current Python in parallel within each of two complete rounds, keeps the builder and projection gates between those rounds, performs the read-only builder check, generates the ignored local `build` tree with `python3 scripts/build_packages.py --output build`, compares its Codex package with the tracked plugin projection, and reports runtime validation as unverified. `status --refresh` reads GitHub main, stable, tag, Release, workflow, manifest, and tag-archive evidence; it performs no remote writes.

`publish` requires persisted `LOCAL_VERIFIED` evidence, a clean worktree and index, matching local HEAD and remote main commits, a successful main workflow, a matching `origin`, GitHub push permission, a regular UTF-8 notes file without credential-like values, and the explicit `--confirm-remote-actions` flag. It creates an annotated tag, performs a non-force tag-only push, creates or reuses the matching GitHub Release, waits for the tag workflow with a bounded timeout, and validates the remote tag ZIP through the real updater archive path. A same-commit tag or Release is idempotent; a conflicting tag fails closed; recoverable partial success is stored as `PARTIAL_REMOTE`.

`promote-stable` requires persisted `TAG_VERIFIED` evidence and its own `--confirm-stable-promotion` authorization. It re-reads main, tag, Release, workflow, immutable tag ZIP, stable ancestry, and the stable manifest before writing. It accepts only a normal non-force fast-forward of the verified release commit. After the push it requires the stable commit, raw manifest, and immutable archive to agree, retrying temporary raw/CDN lag with bounded exponential backoff. A successful or already-applied promotion records `STABLE_PROMOTED`; if final consistency times out after the push, that promoted state is retained as pending rather than rolled back or reported as verified.

`verify-runtime --mode isolated` installs the previous immutable tag under a temporary directory, upgrades through the published stable manifest, verifies current and offline fail-open behavior, rolls back, upgrades again, performs a fresh archive installation, and removes both isolated installations. It does not touch the installed Skill and does not prove Codex client discovery. A passing isolated run is retained as prerequisite evidence while the release remains `STABLE_PROMOTED`.

`verify-runtime --mode installed-client` requires matching isolated evidence, an installed previous stable version, a new absolute artifact path, and the separate `--confirm-installed-skill-mutation` flag. It performs upgrade, rollback, and re-upgrade through the real installed updater; invokes `$vibe-diagram` in a fresh ephemeral `codex exec` process; validates the delivered HTML with the upgraded bundled linter; then temporarily isolates and restores the Skill while a second fresh process confirms non-discovery. Both modes must pass before the state becomes CLI-lane-scoped `RUNTIME_VERIFIED`. A post-mutation failure restores the exact previous-version backup and records `PROMOTED_RUNTIME_FAILED`; it never rewrites the released tag or moves `stable` backwards.

The script never commits, merges, changes a remote URL, force-pushes, deletes a tag, rewrites history, or moves `stable` backwards. `publish`, stable promotion, and installed-client mutation have distinct confirmations. No real runtime lifecycle has been executed by these repository changes, so the implemented R07 capability is not itself runtime evidence. Contributors can use `--repo owner/name` for fork-scoped evidence and, only with their own write permission and the matching explicit confirmation, fork-scoped publication or stable promotion.

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

The GitHub-path Codex CLI evidence is limited to the standalone Skill lane. It covers the public `stable` installation, fresh-process discovery and invocation, HTML delivery and linting, offline fail-open behavior, an online current-version check at `v0.1.1`, and safe preservation after the rejected `v0.1.2` archive. It does not yet cover a successful public newer-version replacement, and no result here claims aggregate compatibility for Codex plugins, Claude Code, Gemini CLI, or GitHub Copilot CLI.

## License

Apache-2.0. See [LICENSE](LICENSE).
