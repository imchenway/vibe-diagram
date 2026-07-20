# Changelog

## [Unreleased]

- Prepared the `0.1.1` candidate with a stable bootstrap that checks for an automatic update before every direct-installed invocation.
- Added a standard-library updater with strict version comparison, immutable-tag downloads, tree-integrity validation, locking, recoverable backups, rollback, and offline fail-open behavior.
- Added the future moving `stable` installation channel and public manual update command while retaining `v0.1.0` as the latest runtime-verified public lane.
- Kept generated package copies under package-manager ownership so they do not self-update outside their distribution lifecycle.

## [0.1.0] - 2026-07-18

- Published the stable GitHub tag for the host-neutral canonical Skill, deterministic four-client package definitions, static validators, and transaction-safe local build pipeline.
- Verified the GitHub-path Codex CLI lane through installation, discovery, invocation, HTML delivery, replacement upgrade, and uninstall isolation.
- Documented the pinned `v0.1.0` `$skill-installer` and bundled-helper flows, including recoverable replacement and removal.
- Kept the curated `$skill-installer` index and public Plugins Directory outside the direct-install claim; those discovery surfaces require separate publication lifecycles.
