# Archetype: Technical Design and Page Prototype

Use technical design when several relationship views must jointly explain how a change will work. Use a page prototype when screen structure, controls, interaction, or responsive states are the primary subject.

## Technical design

- Begin with a product-readable primary overview that states the change, boundaries, decisions, and expected result.
- Add only the architecture, flow, sequence, state, data, comparison, or recovery views required by the implementation question.
- Map the same concepts consistently across views without forcing one fixed view count.
- Keep detailed contracts, source paths, migration notes, and raw evidence in the relevant view or appendix.

## Page prototype

- Use real HTML inputs, buttons, filters, tables, states, and responsive behavior.
- Make important empty, loading, error, permission, and success states visible or interactively reachable.
- When the user requests exploration, provide three to five genuinely different peer candidates; otherwise provide one best design.

## Avoid

- routing every development design to system architecture;
- a fixed four-view technical package;
- device frames filled with cards but no usable controls;
- mixing peer design candidates with sequential workflow steps.

## Product-manager reading

Technical design first explains what changes for users or operations, which product rules and decisions govern it, and how success is accepted; implementation views then prove feasibility. A prototype must make the user goal, controls, states, permission behavior, errors, and responsive outcome directly operable without requiring knowledge of the frontend stack.
