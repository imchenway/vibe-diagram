---
name: vibe-diagram
description: Create and deliver a product-manager-first, self-contained HTML visual artifact when the user asks to draw or when architecture, workflow, sequence, state, data, debugging, code-review, technical-design, comparison, or page-prototype relationships materially need a diagram; ordinary explanations stay textual unless a diagram is requested, and Mermaid alone never completes the request.
---

# Vibe Diagram

Create a real diagram for a business-literate product manager, not a prose report, card inventory, or fixed template with substituted labels. The model owns fact selection, product reading order, visual hierarchy, topology, HTML, CSS, and SVG. Shared code supplies only the content-neutral shell, interaction, and outcome checks.

## Invocation

1. Resolve this skill directory and run `python3 <skill-root>/scripts/update_skill.py --check-and-update --json`.
2. Read [the runtime workflow](references/runtime-workflow.md) completely from the resolved current skill directory.
3. Read [artifact authoring](references/artifact-authoring.md), then at most two archetypes relevant to the request.
4. Inspect the user's actual evidence before drawing. Form product questions and business-first labels while preserving `observed`, `inferred`, `proposed`, `unresolved`, and `verified` boundaries.
5. Initialize a blank self-contained artifact, author the product-manager-first primary layer and mapped technical evidence directly, lint it, verify computed browser geometry and product reading, then deliver the HTML.

For update status `offline` or `failed`, continue with the installed version and mention the status briefly. For an explicit manual update, use `--force-check --json`. Never bypass updater integrity or transactional activation.

## Global invariants

- Templates and archetypes teach visual grammar only. They never supply business labels, node inventories, topology, DOM, or coordinates.
- Every artifact treats `product-manager` as the primary audience. Additional readers may add supporting depth but cannot remove the product-readable primary layer.
- State the business meaning first. Exact class, method, API, field, table, infrastructure, error, and log identifiers are secondary labels or mapped technical evidence when they add value.
- The visible summary and primary view must answer the current product questions without requiring source-code knowledge or opening details. Technical precision must remain available separately.
- Keep every decision-critical fact visible in a primary view. Raw source excerpts and long technical evidence may live in mapped details or appendices.
- Use real diagram grammar: visible shapes and anchored relations must carry the reasoning. Cards may be nodes or boundaries, never the dominant substitute for relationships.
- Default to one best artifact. Use peer candidate views only when the user explicitly requests design exploration.
- Write each standalone graph title as `diagram type｜business subject`; multi-view packages may use a package title, but every graph keeps that format and does not lead with a repository, class, or method name.
- Follow the user's language for every visible label and control. Never invent actors, components, calls, stores, timings, causes, or verification.
- Prefer north-to-south or upper-left-to-lower-right reading. Let the page grow vertically; do not delete meaning or create internal vertical scrolling to fit one screen.
- If the user explicitly names UML, BPMN, C4, ArchiMate, or another standard, use it only when a strict canonical reference exists. Otherwise fail closed instead of drawing a native lookalike.
- Distinguish static validity, product-reading review, browser-layout verification, and real-client runtime verification. One never proves another.

## Archetype routing

- Capabilities, domains, ownership, value, constraints: [business architecture](references/archetypes/business-architecture.md)
- Order, decisions, branches, handoffs, exceptions: [basic flow](references/archetypes/basic-flow.md) or [swimlane and exception flow](references/archetypes/swimlane-exception-flow.md)
- Calls and time: [code sequence](references/archetypes/code-sequence.md) or [async, retry, and timeout](references/archetypes/async-retry-sequence.md)
- Components, interfaces, stores, trust boundaries: [system architecture](references/archetypes/system-architecture.md)
- Symptom, evidence, cause, impact, repair: [fault causal chain](references/archetypes/fault-causal-chain.md)
- State changes: [state machine](references/archetypes/state-machine.md)
- Entities, cardinality, reads, writes, movement: [ER and data flow](references/archetypes/er-data-flow.md)
- Conditions and visible differences: [comparison matrix](references/archetypes/comparison-matrix.md)
- Findings, real scenario, current behavior, repair: [code review](references/archetypes/code-review.md)
- Coordinated implementation views or interactive screens: [technical design and page prototype](references/archetypes/technical-design-page-prototype.md)

Do not load unrelated archetypes. Technical design is an orchestration capability, not an alias for system architecture and not a fixed four-view package.
