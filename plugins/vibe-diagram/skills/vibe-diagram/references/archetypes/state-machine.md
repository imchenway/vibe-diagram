# Archetype: State Machine

Use for durable lifecycle, retries, leases, approvals, terminal conditions, and guarded transitions.

## Recognizable shape

- Show an initial state and named states as distinct semantic objects.
- Directed transitions carry event and guard meaning where applicable.
- Terminal states are explicit, or the diagram clearly declares a cyclic lifecycle.
- Retry, timeout, cancellation, and recovery paths retain their real conditions.
- Persisted state and transient activity are not conflated.

## Avoid

- a horizontal milestone timeline without transitions;
- states named after operations instead of durable conditions;
- unlabeled loops;
- inventing terminal success when the lifecycle has none.

## Product-manager reading

Use product-recognizable state names and state which event or rule permits, blocks, retries, expires, or finishes the transition. Persistence and lease mechanics remain supporting detail unless they change the visible lifecycle.
