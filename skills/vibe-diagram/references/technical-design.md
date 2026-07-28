# Technical Design Reference

## Purpose

A technical design is not a magnified implementation path or a canvas filled with module cards. The default deliverable is one continuously visible design package that answers:

1. What are the system boundaries, module responsibilities, and dependencies?
2. How do the critical runtime interactions execute?
3. What states, guards, and consistency constraints apply?
4. How are failures detected, retried, compensated, escalated, and terminated?

Use a focused template only when the user explicitly asks about one local concern. A focused view must not be presented as a complete technical design.

## Templates

- `../assets/templates/technical-design/technical-design-package.html`: default. It continuously presents four core diagrams and reuses the architecture, sequence, state-machine, and logic-flow kernels.
- `../assets/templates/technical-design/data-consistency-boundary.html`: deprecated migration asset. It must not be scaffolded or delivered as a standalone diagram type. Put Outbox transaction, delivery, consumption, recovery, and consistency concerns into the corresponding views of `technical-design-package`.
- `../assets/templates/technical-design/api-contract-swimlane.html`: migration-candidate view for callers, APIs, services, observability, and contract behavior.
- `../assets/templates/technical-design/module-contract-data-topology.html`: migration-candidate view for module, contract, data, and operational relationships.

`release-switch-track` is deprecated for one release cycle and is no longer a public template. If the user requests only a release process, route it to the shared business-flow logic core. When release or rollback affects a technical design, preserve it in the relevant node details instead of creating a fifth top-level graph.

## Composition and reuse

The default package has one title, one reading guide, and one detail interaction system. It must not nest complete HTML shells.

| Technical view | Reused source | Required meaning |
|---|---|---|
| Design overview | `system-architecture/component-breakdown` | boundaries, responsibilities, modules, dependencies, external systems |
| Runtime sequence | `code-sequence/participant-timeline` | participants, lifelines, calls, returns, exception fragments |
| State consistency | `state-data-model/state-machine` | states, events, guards, terminal states, consistency feedback |
| Failure recovery | `business-flow/logic-flowchart` | detection, decision, retry, compensation, human intervention, termination |

Reuse diagram-family grammar, layout contracts, nodes, relations, interactions, and validation kernels. Do not copy complete templates or fork a second implementation from an older template.

## Content and evidence boundary

- Canonical templates define topology, relative placement, complexity limits, connection anchors, responsive transformation, and interaction capability.
- Titles, nodes, relations, table cells, evidence states, and details must come from current task facts.
- Distinguish current implementation, proposed design, and open questions. Static validity is not browser layout verification or client lifecycle evidence.
- Include API and data contracts, security, concurrency, consistency, observability, migration, tests, release, and rollback whenever they affect correctness, but place them in the relevant core graph or its details rather than inventing another graph type.
- Put code paths and evidence anchors in details; do not cover the primary canvas with prose.

## Layout and interaction

- Keep all four views continuously visible; do not hide design content behind tabs.
- Give each core graph one title in the exact `diagram type｜title` form, localized to the artifact language. The page title and detail headings remain outside this rule.
- Keep the shared percentage control group persistently visible for the package's primary overview canvas; embedded graphs reuse the package interaction shell without duplicating control groups.
- Prefer direct relations. Branches and merges may use at most one necessary bend. Feedback loops require an explicit semantic reason and an independent channel.
- Size nodes for their real copy. Never conceal overflow by shrinking the font.
- Node details support a nearby collision-aware popover, Escape, outside-click close, focus return, and deep links. Native `details` elements remain only as no-JavaScript and print fallbacks.
- Semantic tables may scroll horizontally inside their own viewport on narrow screens; the page itself must not overflow horizontally.
