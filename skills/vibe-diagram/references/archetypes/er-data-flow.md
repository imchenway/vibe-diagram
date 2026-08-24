# Archetype: ER and Data Flow

Use for entities, fields, cardinality, stores, transformations, reads, writes, and data movement.

## Recognizable shape

- ER views show independent entities with relationship cardinality and meaningful key fields.
- Data-flow views distinguish source, process, store, and sink when those roles exist.
- Reads, writes, emits, consumes, and transforms are visible relations.
- Ownership or transaction boundaries appear only when supported by evidence.
- Use separate mapped views when entity structure and runtime movement are both important.

## Avoid

- a state machine used as a database model;
- one generic “data” node containing many unrelated tables;
- cardinality inferred from naming alone;
- listing fields without showing the relationships the user asked about.

## Product-manager reading

Explain which business object is created, owned, transformed, shared, or rejected and why that matters to the process. Keep key fields and exact stores visible only when they affect product rules; put exhaustive schemas in the evidence layer.
