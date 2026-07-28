# Changelog

## [Unreleased]

## [0.1.13] - 2026-07-28

- 将中英文 README 精简为项目简介和 Codex 对话式一键安装入口，移除仓库模型、升级、卸载、构建、发布及证据边界等维护者细节。

## [0.1.12] - 2026-07-28

- 将默认技术设计包从六视图收敛为设计总览、运行时序、状态一致性和失败恢复四个核心图；数据契约、发布与验收信息按需进入相关节点或详情，不再独立作为图类型。
- 将百分比缩放组件保留为全局能力，仅在技术设计包主画布常驻显示，其余模板恢复为溢出时显示。
- 为代码时序图族及技术设计内嵌时序统一加入非白色语义底色，覆盖参与者、消息标题和移动端消息节点。
- 新增全局图级标题契约，统一使用“图类型｜标题”，并明确页面主标题、表格标题和详情标题不受该格式约束。

## [0.1.8] - 2026-07-24

- Changed direct updater activation to use an in-process transient previous tree, delete it before reporting success, and retain no updater backup.
- Removed the updater `--rollback` action; pinned immutable-tag reinstallation is now the explicit downgrade path.
- Added a compatibility cleanup that removes only legacy updater backups with a matching legacy name, version, manifest, and complete tree digest while preserving manual or modified backups.
- Kept the legacy `backup_path` JSON field as a compatibility field that is `null` for updates performed by the new updater.

## [0.1.7] - 2026-07-23

- Reworked the workload overview into a west-entry, central north-to-south core-spine, east-operations, south-foundation topology and rebuilt logical layering as a true north-to-south DAG with parallel ranks, branches, and merges.
- Made topology direction, ranks, regions, primary relations, exact fallback relations, and structured evidence ledgers fail-closed in both the artifact linter and deterministic builder.
- Moved zoom controls into the responsive title region, added an explicit persistent mode for the two system-architecture views while retaining overflow-only defaults elsewhere, and migrated the shared presentation contract across all 53 generic templates.
- Made the authored conversation language govern visible node labels, kept pre-canvas evidence as the default while allowing trusted templates to place visible key evidence after the primary canvas, and added one-to-one native clickable detail disclosure for every node in the two system-architecture views.
- Required the node-detail interaction hint to appear exactly once inside the shared reading guide and never as a floating SVG-canvas annotation.
- Added a true dual-path swimlane template with inline SVG arrows, an explicit missing-handoff relation, aligned success and blocked outcomes, a visible diagram-type title, visible key evidence after the canvas, and folded long provenance.
- Kept browser rendering evidence separate from static contract validity and kept real client lifecycle verification explicitly unverified.

## [0.1.6] - 2026-07-23

- Removed the repository-wide network-access prohibition so agent tasks may use network access while remote Git, GitHub, marketplace, and client mutations still require explicit authorization.
- Made post-publication GitHub workflow and raw/CDN consistency reads asynchronous evidence so publishing and stable promotion do not wait for propagation.

## [0.1.5] - 2026-07-22

- Removed the automated test suite, runtime evaluation cases, mandatory TDD rule, and unit-test execution gates by explicit project-owner decision; deterministic build, projection, archive, linter, and real-client validation capabilities remain.
- Changed the maintainer release path to publish the immutable tag, GitHub Release, and `stable` immediately after local static validation instead of waiting for GitHub Actions; CI remains asynchronous evidence.
- Added a deterministic canonical-template scaffold and strict artifact-to-template conformance checks for styles, scripts, slots, DOM grammar, and the shared gradient-grid visual shell.
- Restored the reference sequence caption, arrow, return, and risk-node grammar across all six sequence templates while retaining structured participants, endpoints, evidence, and adaptive behavior.
- Added primary-canvas presentation budgets, explicit natural-language visual triggers, implicit Codex invocation metadata, and an invocation-complete HTML delivery gate that forbids Mermaid-only completion.
- Kept real Codex App and CLI execution explicitly unverified.

## [0.1.4] - 2026-07-21

- Added a standard-library GitHub Skill release orchestrator for deterministic candidate preparation, resumable local state, and read-only remote evidence collection.
- Added the guarded R05 publisher for an already-merged main commit: explicit confirmation, immutable annotated tags, non-force tag-only pushes, idempotent GitHub Releases, bounded workflow waits, real-updater ZIP validation, and resumable partial-remote state.
- Added the guarded R06 stable promoter: separate confirmation, complete remote revalidation, fast-forward-only stable pushes, bounded exponential raw/CDN consistency checks, idempotent resume, and durable `STABLE_PROMOTED` state after an accepted push.
- Added the guarded R07 runtime verifier: isolated public-updater lifecycle coverage plus separately confirmed installed Codex CLI invocation, bundled-linter artifact validation, uninstall isolation, exact-backup recovery, and lane-scoped `RUNTIME_VERIFIED` evidence.
- Added the R08 contributor release guide and read-only CI integration around the standard `verify` entry point, including fork boundaries and an official-maintainer checklist.
- Made release verification generate the ignored local package tree before comparing Codex output with the tracked plugin projection, so clean checkouts cannot inherit stale build state.
- Kept runtime evidence fail-closed: R07 code does not claim that a real network, installed Skill, or Codex client lifecycle was executed by these local changes.

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
