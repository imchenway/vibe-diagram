# Domain Context

The primary artifact produced by this project is a model-authored, self-contained single-file HTML document.

| Term | Stable definition |
|---|---|
| canonical core | The only editable, host-neutral Skill body, shell, contracts, references, and scripts under `skills/vibe-diagram/`. |
| adapter definition | One client's manifest template, output path, additional-file allowlist, and host notes; it contains no copy of the Skill body. |
| generated package | A complete client package under `build/<client>/`, composed from the canonical core and an adapter definition. |
| Codex marketplace projection | The builder-only generated package under `plugins/vibe-diagram/`. It is not canonical and must byte-match the Codex package. |
| package-static-valid | One generated package passed canonical, adapter, manifest, inventory, path, digest, and self-containment preflight. It proves no real client behavior. |
| static-valid | Two clean deterministic builds, generated projection comparison, `git diff --check`, and canonical archive validation passed. |
| browser-layout-verified | A named artifact passed computed geometry and interaction checks at the declared real-browser viewports. It does not prove client installation or invocation. |
| runtime-verified | Installation, discovery, invocation, output, delivery, upgrade, and uninstall passed in one named real client and version. It cannot be inherited by another lane. |
| Vibe Diagram delivery system | The complete boundary spanning canonical authoring, generated client packages, public distribution, and client-scoped runtime evidence. |
| model-authored artifact | Final HTML, CSS, SVG, topology, copy, and coordinates authored directly by the model from current evidence; no renderer supplies its nodes or layout. |
| product-manager-first artifact | Every delivered artifact treats a business-literate, non-engineering product manager as the primary reader. Its visible primary layer explains the outcome, business impact, rules, decision, and acceptance meaning that matter to the request before exposing implementation terminology. |
| business-first label | The primary visible name of an object, action, state, failure, or relation states its business meaning; an exact code, API, field, table, or infrastructure identifier may follow as secondary evidence. |
| technical evidence layer | Supporting or appendix content that preserves exact source locations, identifiers, logs, calls, fields, and implementation mechanics without making them prerequisites for understanding the primary product story. |
| Diagram Brief | The model's private reasoning summary of product questions, decisions, facts, evidence states, primary relationships, business-first labels, information hierarchy, and suitable views. It is not a rendering input or persisted node specification. |
| visual archetype | A concise reference that teaches when a visual grammar is useful, what makes it recognizable, and which anti-patterns to avoid. It never supplies business labels, node inventory, topology, DOM, or coordinates. |
| global artifact shell | The content-neutral title, summary, persistent zoom, light grid, interaction, print, accessibility, and geometry-audit base inlined into every artifact. It does not generate business meaning or family layout. |
| ArtifactManifest v1 | Embedded questions, critical facts, views, evidence, and visible-target coverage used to audit a finished artifact. It deliberately contains no node list, edge list, rank, lane, topology, or coordinate model. |
| semantic marker | A minimal `data-vd-*` annotation attached to a model-authored visual element so endpoints, critical visibility, family grammar, details, and geometry can be checked without prescribing HTML structure. |
| family outcome grammar | A family-specific set of observable characteristics such as lifelines for sequence or labeled branches for flow. It sets no node maximum, DOM skeleton, business wording, coordinates, or fixed view count. |
| outcome linter | Static validation of self-containment, Manifest coverage, semantic bindings, family outcome grammar, titles, language, details, and shared-shell integrity. It never compares a template identity or exact DOM. |
| computed layout audit | Browser-side inspection after fonts load for node overlap, overflow, edge-through-node, endpoint anchoring, label collisions, group clipping, critical visibility, and page overflow. It reports issues but never changes semantics or layout. |
| product-reading-reviewed | A named real-demand artifact passed a review performed without opening technical details: its declared critical questions are answerable from the product-manager-first primary layer and its exact evidence remains available separately. Static lint and browser geometry cannot establish this result. |
| critical coverage | A question or fact mapped to one or more visible `data-vd-critical` elements in a primary view. A closed detail, hidden candidate, or appendix cannot satisfy it. |
| evidence state | One of `observed`, `inferred`, `proposed`, `unresolved`, or `verified`; visual completeness never permits promotion to a stronger state. |
| true diagram | A primary visual whose decision-relevant objects and relationships are encoded as visible shapes, axes, lifelines, states, controls, or anchored routes. A card inventory or prose report is not a true diagram. |
| technical-design orchestration | A product-readable primary design overview plus only the architecture, flow, sequence, state, data, comparison, recovery, or prototype views the current implementation question needs. It has no fixed view count. |
| candidate mode | Multiple peer designs shown only when the user explicitly requests visual exploration. Sequential steps or ordinary follow-up content are not candidates. |
| readable floor | `75%` zoom. If a natural diagram cannot fit at that scale, use view-local horizontal scrolling or split mapped views; never keep shrinking, delete facts, or create nested vertical scrolling. |
| authored output language | The language inferred from the current request and used for every visible label, title, control, detail, fallback, and evidence statement. |
| explicit standard mode | A user-named notation such as UML or BPMN. It may be used only when a strict canonical reference exists; otherwise generation fails closed instead of emitting a native lookalike. |
| invocation-complete | Update gate, evidence inspection, Diagram Brief, relevant archetype loading, direct artifact authoring, ArtifactManifest binding, static linting, browser verification when available, and HTML delivery completed. |
| retired template compiler | Contract v2's fixed HTML/DOM templates and Contract v3's `DiagramDocumentSpec` plus generic renderer. Both are physically absent from production and may appear only in historical documentation or explicit rejection checks. |
| update tree digest | SHA-256 over the canonical Skill files except `update.json`, used by the updater to verify an immutable release candidate before activation. |
| transient activation slot | A same-parent staging location holding the previous installed tree only while a transactional updater activation is in progress; it is deleted after success and is not a retained backup. |
| public source set | Product source, adapters, build/release definitions, public policy documents, and generated Codex projection. Task records and local runtime evidence are not public runtime claims. |
| direct stable release | A separately authorized publication path after local `static-valid`; it never implies browser or real-client verification and is outside ordinary implementation authority. |
