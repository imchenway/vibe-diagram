# Domain Context

The primary artifact produced by this project is a self-contained single-file HTML document.

| Term | Stable definition |
|---|---|
| canonical core | The only editable, host-neutral skill body and shared assets under `skills/vibe-diagram/`. |
| adapter definition | One client's manifest template, output path, additional-file allowlist, and host notes; it contains no copy of the skill body. |
| generated package | A complete client package under `build/<client>/`, composed from the canonical core and an adapter definition. |
| package-static-valid | The builder's production static preflight of the canonical core, adapter, manifest, package contents, paths, and hashes passed. `build-report.json` with `static_validation: passed` expresses only this layer and does not prove that unit tests ran. |
| static-valid | The complete unit-test suite, a package-static-valid build, and the second complete unit-test run all passed. Evidence stays in command or CI output rather than tracked documentation. It does not mean that a client was installed or invoked. |
| local-release-ready | The repository-side publication structure, documentation, version metadata, CI definitions, and generated projections satisfy static gates locally, while no public GitHub state or real-client lifecycle evidence is claimed. |
| publication repository | The single repository that owns the canonical core, package definitions, tracked Codex marketplace projection, CI definitions, and release history. |
| public source set | The tracked publication content comprising product source, tests, package and CI definitions, three public policy documents, and generated Codex marketplace artifacts. Task records, design decisions, and validation evidence are not part of it. |
| public publisher identity | The stable name exposed consistently by repository ownership, package manifests, and marketplace metadata; it does not require publishing a personal email address. |
| runtime-verified | Installation, discovery, invocation, output, delivery, upgrade, and uninstall were verified in a real client. Every client remains `Unverified` in the current scope. |
| Codex marketplace projection | The tracked, builder-only generated package under `plugins/vibe-diagram/` used by the repo marketplace. It is not canonical and must match the Codex package and release version at the same stable tag. |
| stable promotion gate | The fail-closed boundary that permits a Codex stable release only after every declared CI, installation-entry, client-surface, and runtime-lifecycle requirement has passed; any failure keeps the version at release-candidate status. |
| sequence interaction kernel | The same-version CSS/JavaScript enhancement embedded in six sequence templates. It handles only width, zoom, scrolling, sticky headers, and degradation; it does not generate or rewrite business semantics. |
| semantic participant | An independent sequence participant with a stable `data-participant-id`; semantically different participants must not be merged merely to reduce columns. |
| primary sequence message | A message node declaring structured `data-from`, `data-to`, and `data-message-kind`. Calls, returns, async messages, self-calls, and exceptions count; notes, evidence annotations, and phase headings do not. |
| major sequence phase | A main business phase explicitly declaring `data-sequence-phase-id`. Loops, branches, and notes count only when they also declare this attribute. |
| overview sequence | The main-path overview for an over-complex diagram. It keeps phase boundaries and critical transitions and does not pretend to be the complete call chain. |
| detail sequence | A diagram mapped to one overview phase that preserves every real participant, message, and exception branch for that phase. |
| adaptive viewport contract | A host-neutral presentation contract that declares a diagram canvas's width, height, scrolling, zoom, sticky-navigation, mobile, print, no-JavaScript, and reduced-motion behavior without defining its business grammar. |
| semantic relation contract | A static structural contract that gives canvases, semantic objects, groups, and directed relations stable identifiers so readability, endpoint integrity, complexity, overview/detail mapping, and semantic fallbacks can be validated without parsing visible labels or CSS classes. |
| diagram family policy | A trusted canonical policy for one diagram family. It declares allowed semantic profiles, relation kinds, complexity budgets, required reading aids, and fallback strategies; a template cannot override its own policy or raise its own budget. |
| semantic profile | A per-canvas structural vocabulary such as graph, matrix, timeline, artboard, or ledger. A template may contain more than one profile while retaining its own family-specific visual grammar. |
| semantic reading guide | An author-provided, structurally linked navigation aid such as a sticky lane label, stage header, axis header, boundary index, or landmark index. The shared runtime may position it but must not infer or generate its meaning. |
| semantic mobile fallback | A baseline HTML representation that preserves identities, relation endpoints, direction, ownership, ordering, axes, boundaries, and evidence when a desktop visual topology cannot remain readable on a narrow viewport. It is not an unrelated summary or a flattened card list. |
| family complexity budget | A fail-closed limit defined by the diagram family policy over semantic objects, relations, groups, depth, rows, columns, views, stages, or other profile-specific dimensions. Exceeding it requires an explicitly linked overview/detail split. |
| progressive disclosure capability | An optional runtime enhancement bound to the semantic relation contract. It opens author-provided detail panels and preserves focus, anchors, print visibility, and no-JavaScript readability; it never creates semantic content. |
| Vibego downstream projection | A controlled copy mapped into Vibego after canonical verification. Host delivery wording, language, and template-relative paths may differ, while the sequence-contract version, kernel digest, template identity, semantic endpoint rules, and structural signatures must match. |
