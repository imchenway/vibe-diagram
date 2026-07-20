# Changelog

## [Unreleased]

## [0.1.3] - 2026-07-20

- Exported the generated-plugin `VERSION` marker out of GitHub release archives so legacy standalone updaters see one canonical Skill root.
- Required the updater to select the exact repository-root canonical Skill path even when a custom archive contains generated package projections.
- Recorded the safely rejected `v0.1.2` replacement attempt without treating it as a successful runtime upgrade.

## [0.1.2] - 2026-07-20

- Kept current-version and offline update checks read-only so normal Skill invocation does not need to create a lock file.
- Deferred locking and write permission until the stable manifest actually declares a newer release.
- Verified the public stable install, fresh Codex CLI discovery and invocation, HTML delivery, bundled-linter repair, offline fail-open, and online current-version paths.

## [0.1.1] - 2026-07-20

- Published the stable bootstrap that checks for an automatic update before every direct-installed invocation.
- Added a standard-library updater with strict version comparison, immutable-tag downloads, tree-integrity validation, locking, recoverable backups, rollback, and offline fail-open behavior.
- Added the moving `stable` installation channel and public manual update command.
- Kept generated package copies under package-manager ownership so they do not self-update outside their distribution lifecycle.

## [0.1.0] - 2026-07-18

- Published the stable GitHub tag for the host-neutral canonical Skill, deterministic four-client package definitions, static validators, and transaction-safe local build pipeline.
- Verified the GitHub-path Codex CLI lane through installation, discovery, invocation, HTML delivery, replacement upgrade, and uninstall isolation.
- Documented the pinned `v0.1.0` `$skill-installer` and bundled-helper flows, including recoverable replacement and removal.
- Kept the curated `$skill-installer` index and public Plugins Directory outside the direct-install claim; those discovery surfaces require separate publication lifecycles.
