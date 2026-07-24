# System architecture reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family for system boundaries, containers, components, deployment, data, integrations, security, reliability, observability, and delivery topology.

## Templates

- `../assets/templates/system-architecture/api-integration.html`: contracts and integration edges.
- `../assets/templates/system-architecture/component-breakdown.html`: internal component responsibilities.
- `../assets/templates/system-architecture/data-architecture.html`: data domains, stores, governance, and consumers.
- `../assets/templates/system-architecture/data-flow.html`: sources, transformations, trust boundaries, and sinks.
- `../assets/templates/system-architecture/delivery-pipeline.html`: source-to-build-to-release delivery stages when staged delivery is the primary question.
- `../assets/templates/system-architecture/deployment-topology.html`: environments, runtime units, and infrastructure.
- `../assets/templates/system-architecture/event-driven.html`: producers, channels, consumers, and delivery semantics.
- `../assets/templates/system-architecture/identity-access.html`: identity, authentication, authorization, and protected resources.
- `../assets/templates/system-architecture/logical-layering.html`: a true north-to-south layered DAG with peers placed in parallel inside a rank and explicit branch or merge relations between ranks.
- `../assets/templates/system-architecture/network-topology.html`: zones, boundaries, ingress, egress, and internal networks.
- `../assets/templates/system-architecture/observability-view.html`: telemetry sources, pipelines, storage, rules, and response.
- `../assets/templates/system-architecture/resilience-view.html`: failure domains, isolation, degradation, and recovery.
- `../assets/templates/system-architecture/router-v6.html`: route the question to the most useful architectural view.
- `../assets/templates/system-architecture/security-view.html`: assets, threats, trust boundaries, and controls.
- `../assets/templates/system-architecture/system-context.html`: people and external systems around one system boundary; use it for context, not as a substitute for internal layering or workload topology.
- `../assets/templates/system-architecture/workload-overview.html`: a narrow west rail, wide north-to-south center spine, narrow east rail, lower-center band, and full-width southern band; the positions carry no predefined domain roles.

Copy one primary template and replace its slots. Do not combine all views into one canvas or reduce them to the same generic grid.

An unfilled canonical preview hides every unresolved canvas text token so long macro names cannot overlap the authored geometry. This is preview behavior only: do not delete node title, summary, icon, relation, chip, detail, or fallback slots that generated artifacts still need.

## Topology contract

- Use a real SVG architecture canvas for the primary topology. HTML may provide controls, annotations, evidence, and fallback reading, but it must not substitute a card list for the architecture map.
- Treat geometry as part of the contract. A claimed north-to-south view must place successive primary ranks lower on the canvas and connect them with visible directed relations whose endpoints follow the same progression; `workload-overview` and `logical-layering` enforce this from numeric SVG node bounds, boundary-attached path endpoints, and path vertices that never route northward. The layered view exits each source on its south edge and enters each target on its north edge. Names such as `north-south` are not evidence.
- Declare the primary topology and direction on the canvas, assign stable ranks and regions to semantic groups and nodes, and classify primary versus supporting relations. Keep parallel peers in the same rank and give every required region a visible boundary.
- Bind every authored relation to exactly one visible SVG path or line with `data-diagram-visible-relation-id`. The visible carrier must preserve the declared endpoints and relation kind; metadata-only relations are invalid.
- Draw each system boundary explicitly and give every major region or actor a named landmark. Use boundaries for ownership, trust, runtime, network, and data scope rather than decorative grouping.
- Provide a legend whenever line style, marker, color, or shape carries more than one meaning. Keep color supplementary and preserve direction through arrowheads or equivalent marks.
- Route connectors around nodes, anchor them at object edges, and add a label mask or deliberate gap when a relation label overlays a path.
- Provide a semantic mobile fallback that preserves landmarks, boundaries, endpoints, direction, and reading order. It may reflow into an ordered relation ledger, but it must not become an unrelated summary or micro-scaled desktop canvas.
- In `workload-overview` and `logical-layering`, give every primary node one compact pictogram or emoji, a language-matched title, and a short summary. The icon supports scanning but never replaces the title. Keep the outer semantic node as a non-link container so it can safely own both a native primary detail link and independently focusable auxiliary links without nesting anchors.
- Give every visible internal module, chip, or supporting card its own native auxiliary detail link and one matching printable `details` block. The shared popover runtime only presents authored detail content; it never derives content from a position or template name.
- Treat the quality values in `contracts/family-policies.json` as executable layout constraints for these two templates: primary nodes must not overlap, configured peer widths and vertical gaps must be uniform, required bands must meet their full-width ratio, outer boundaries must meet canvas-utilization thresholds, every path must remain long enough to read, every endpoint must stay on its owning node boundary, routes must avoid unrelated nodes, arrowheads must remain within the declared size range, and the compound overview must retain four visibly distinct relation colors.
- Encode observed implementation, completed checks, and not-yet-verified claims with distinct node treatments. Combine their color meanings, every authored line kind, and one concise node-detail interaction hint into one compact reading guide above the canvas. The hint must not float inside the SVG canvas. Do not turn the guide into another evidence report.
- For `workload-overview`, follow the compound landscape skeleton rather than a loose card scatter: a narrow west rail, a dense central boundary whose internal primary cards form one north-to-south spine, a lower-center band, a stacked east rail, and a full-width southern band. Assign business meaning to those positions only after reading current evidence. Express verified substructure as compact chips inside the owning primary node so the canvas communicates composition without multiplying unrelated top-level boxes.
- Keep persistent Fit, 75%, 90%, and 100% controls on these two overview templates at measurable desktop widths. Their visibility is a template capability, not an overflow accident.
- Keep topology template-specific without turning topology into content: a centered boundary, side rails, a layered DAG, zones, or a timeline may constrain placement and relation geometry, but none of those positions predefines the system's actors, modules, responsibilities, or evidence state.

## Routing rules

- Start from the question: context, runtime, data, integration, deployment, security, resilience, observability, or delivery.
- Do not route to `delivery-pipeline` merely because source, build, release, publication, or deployment terms appear. Select it only when the staged source-to-build-to-release progression is the dominant relationship being explained.
- Use `workload-overview` when the evidence needs two side rails around a dense central north-to-south spine plus lower-center and southern bands. Use `logical-layering` for a predominantly top-to-bottom dependency stack with parallel responsibilities and branch or merge points. Choose by geometry; do not infer content roles from either layout.
- Use one dominant view and add a second only when it resolves a distinct conflict.
- Keep the primary request or information flow visually continuous.
- Label ownership, trust, network, runtime, and data boundaries explicitly.
- Include external dependencies and operational control paths only when supported by evidence.
- Route detailed call timing to the sequence family and detailed business responsibility to the business families.

## Screenshot-free computed audit

The shared artifact shell audits the computed browser layout after DOM readiness, font readiness, and every observed resize. It checks visible node collisions, content overflow, auxiliary-node surface contrast, relation paths crossing nodes or labels, source and target boundary anchoring, arrowhead presence, canvas utilization, guide/control order, and page-level horizontal overflow. The result is exposed on each canvas and the document through `data-computed-layout-audit` plus an issue count and bounded issue list.

This audit is intentionally geometry-based rather than screenshot-based. Do not create or compare screenshots or pixel baselines as a normal acceptance gate. A passing computed audit is viewport-scoped browser evidence; it does not establish a real client's install, discovery, invocation, upgrade, or uninstall lifecycle.

## Evidence and scale

Prefer verified component and interface names. If the source only supports a logical role, use that role and mark the missing implementation mapping. Use overview plus drill-down when a single view would require tiny labels, excessive crossings, or unrelated planes.
