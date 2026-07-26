# Technical design reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family for module boundaries, API contracts, consistency, release switching, implementation constraints, test evidence, and rollback.

## Templates

- `../assets/templates/technical-design/api-contract-swimlane.html`: caller, interface, service, observation, and contract behavior.
- `../assets/templates/technical-design/data-consistency-boundary.html`: the 0.1.10 Outbox consistency design, separating transaction, delivery, consumption, failure-recovery, and consistency-constraint boundaries.
- `../assets/templates/technical-design/module-contract-data-topology.html`: modules, contracts, data, operations, tests, release, and rollback.
- `../assets/templates/technical-design/release-switch-track.html`: build, gate, rollout, observation, switch, and rollback.

Copy the selected template and retain its layout identity. Replace slots with evidence-backed design content.

## Design rules

- The Outbox primary chain identifies local transaction writes, event delivery, broker acknowledgement, consumer idempotency, and result updates. Failure recovery uses an independent feedback channel.
- Express consistency constraints as a boundary or constraint band rather than scattering constraint prose as cards at the same level as the primary chain.

- Begin with the current entry point and verified implementation chain.
- Define changed, retained, and removed behavior plus compatibility impact.
- Put module ownership, interfaces, schemas, invariants, state transitions, and failure semantics on the main canvas.
- Include permissions, concurrency, consistency, observability, migration, testing, deployment, and rollback when they affect correctness.
- Keep code paths and anchors near the claims they support.
- Distinguish current implementation, proposed design, and unresolved decision.

## Layout and interaction

Use directional topology rather than a card inventory. Keep labels off connector paths, expose critical details without hover, and put dense evidence in accessible details or a bottom ledger. Ensure keyboard access, visible focus, mobile reflow, and print expansion.
