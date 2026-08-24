# Archetype: System Architecture

Use for systems, components, interfaces, stores, middleware, deployment or trust boundaries, and their dependencies.

## Recognizable shape

- Boundaries encode real ownership, trust, runtime, or deployment distinctions.
- Components and stores sit inside the boundary that actually owns them.
- Calls, reads, writes, publishes, subscribes, routes, and dependencies are visibly different where the distinction matters.
- The dominant direction is normally north to south or upper-left to lower-right.
- Supporting operational paths remain secondary to the main architecture story.

## Avoid

- fixed presentation/business/data layers when the evidence has another shape;
- inventing databases, queues, caches, or gateways for visual completeness;
- representing a development plan as only a component map;
- dense internal capability cards with no visible interfaces.

## Product-manager reading

Lead with what each boundary is responsible for, which business information crosses it, and what dependency failure affects. Exact component, middleware, database, and protocol names are secondary unless they determine a product constraint or decision.
