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
| model-authored artifact | 模型依据证据编写最终 HTML/SVG、文案和真实关系；共享程序可根据现有语义标记测量、排版和走线，不补造对象或关系。 |
| product-manager-first artifact | Every delivered artifact treats a business-literate, non-engineering product manager as the primary reader. Its visible primary layer explains the outcome, business impact, rules, decision, and acceptance meaning that matter to the request before exposing implementation terminology. |
| business-first label | The primary visible name of an object, action, state, failure, or relation states its business meaning; an exact code, API, field, table, or infrastructure identifier may follow as secondary evidence. |
| technical evidence layer | Supporting or appendix content that preserves exact source locations, identifiers, logs, calls, fields, and implementation mechanics without making them prerequisites for understanding the primary product story. |
| Diagram Brief | The model's private reasoning summary of product questions, decisions, facts, evidence states, primary relationships, business-first labels, information hierarchy, and suitable views. It is not a rendering input or persisted node specification. |
| visual archetype | 五种基础图法的按需指导：架构关系、流程、时序、状态、数据关系。比较表和页面原型使用原生 HTML；故障、审查、技术设计是内容组织要求，不是独立模板。 |
| global artifact shell | 内嵌于单文件的公共排版、缩放、关联高亮、差异阅读、导出、打印和检查能力；不生成业务含义。 |
| automatic layout | 对显式选择自动排版的 SVG，读取已有节点、边和归属，测量文字后安排位置与避障路线；复杂嵌套边界可直接编排，但必须通过同一几何检查。 |
| accepted artifact | 独立候选文件经过静态检查、对应文件的浏览器检查和产品阅读后，才原子替换的交付文件；失败保留原文件并报告本次失败。 |
| artifact comparison | 按同一 artifactId 下的稳定元素编号比较文字、关系、证据和手工几何；不根据相似标签猜身份，不将改位置解释成业务变化。 |
| view image export | 导出一个完整 SVG 视图及其标题、摘要和说明，清除临时高亮；不能完整表达的 HTML 混排视图使用整页打印或原 HTML。 |
| ArtifactManifest v1 | Embedded questions, critical facts, views, evidence, and visible-target coverage used to audit a finished artifact. It deliberately contains no node list, edge list, rank, lane, topology, or coordinate model. |
| semantic marker | 模型已编写元素上的 data-vd-* 标记，同时供检查、关联阅读、对比与可选自动排版使用；不另建平行节点清单。 |
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
