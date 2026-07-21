# System architecture reference

Use this family for system boundaries, containers, components, deployment, data, integrations, security, reliability, observability, and delivery topology.

## Templates

- `../assets/templates/system-architecture/api-integration.html`: contracts and integration edges.
- `../assets/templates/system-architecture/component-breakdown.html`: internal component responsibilities.
- `../assets/templates/system-architecture/data-architecture.html`: data domains, stores, governance, and consumers.
- `../assets/templates/system-architecture/data-flow.html`: sources, transformations, trust boundaries, and sinks.
- `../assets/templates/system-architecture/delivery-pipeline.html`: source-to-build-to-release delivery stages.
- `../assets/templates/system-architecture/deployment-topology.html`: environments, runtime units, and infrastructure.
- `../assets/templates/system-architecture/event-driven.html`: producers, channels, consumers, and delivery semantics.
- `../assets/templates/system-architecture/identity-access.html`: identity, authentication, authorization, and protected resources.
- `../assets/templates/system-architecture/logical-layering.html`: responsibilities and allowed dependencies across layers.
- `../assets/templates/system-architecture/network-topology.html`: zones, boundaries, ingress, egress, and internal networks.
- `../assets/templates/system-architecture/observability-view.html`: telemetry sources, pipelines, storage, rules, and response.
- `../assets/templates/system-architecture/resilience-view.html`: failure domains, isolation, degradation, and recovery.
- `../assets/templates/system-architecture/router-v6.html`: route the question to the most useful architectural view.
- `../assets/templates/system-architecture/security-view.html`: assets, threats, trust boundaries, and controls.
- `../assets/templates/system-architecture/system-context.html`: people and external systems around the system boundary.
- `../assets/templates/system-architecture/workload-overview.html`: entry points, core services, data, operations, and foundation.

Copy one primary template and replace its slots. Do not combine all views into one canvas or reduce them to the same generic grid.

## Topology contract

- Use a real SVG architecture canvas for the primary topology. HTML may provide controls, annotations, evidence, and fallback reading, but it must not substitute a card list for the architecture map.
- Bind every authored relation to exactly one visible SVG path or line with `data-diagram-visible-relation-id`. The visible carrier must preserve the declared endpoints and relation kind; metadata-only relations are invalid.
- Draw each system boundary explicitly and give every major region or actor a named landmark. Use boundaries for ownership, trust, runtime, network, and data scope rather than decorative grouping.
- Provide a legend whenever line style, marker, color, or shape carries more than one meaning. Keep color supplementary and preserve direction through arrowheads or equivalent marks.
- Route connectors around nodes, anchor them at object edges, and add a label mask or deliberate gap when a relation label overlays a path.
- Provide a semantic mobile fallback that preserves landmarks, boundaries, endpoints, direction, and reading order. It may reflow into an ordered relation ledger, but it must not become an unrelated summary or micro-scaled desktop canvas.
- Keep topology template-specific: context diagrams center a system boundary among people and external systems; workload overviews distinguish entry, core runtime, operations, data, and foundation. Other architecture templates retain their own deployment, network, integration, data, security, resilience, observability, or delivery grammar.

## Routing rules

- Start from the question: context, runtime, data, integration, deployment, security, resilience, observability, or delivery.
- Use one dominant view and add a second only when it resolves a distinct conflict.
- Keep the primary request or information flow visually continuous.
- Label ownership, trust, network, runtime, and data boundaries explicitly.
- Include external dependencies and operational control paths only when supported by evidence.
- Route detailed call timing to the sequence family and detailed business responsibility to the business families.

## Evidence and scale

Prefer verified component and interface names. If the source only supports a logical role, use that role and mark the missing implementation mapping. Use overview plus drill-down when a single view would require tiny labels, excessive crossings, or unrelated planes.
