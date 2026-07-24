# Business architecture reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family to show who creates value, which capabilities fulfill needs, how domain objects relate, and where rules constrain the business.

## Templates

- `../assets/templates/business-architecture/capability-domain-map.html`: connect actors and needs to capabilities, services, objects, rules, and feedback.
- `../assets/templates/business-architecture/participant-boundary.html`: distinguish initiators, owners, operators, external parties, commitments, and outcomes.
- `../assets/templates/business-architecture/rule-constraint-heatmap.html`: map rules to constrained objects and make risk concentration visible.
- `../assets/templates/business-architecture/value-chain-map.html`: show the value trigger, capability handoff, object flow, outcome, and feedback loop.

Copy the selected template and replace slot content. Preserve its topology, template identity, macros, responsive rules, and evidence section.

## Modeling rules

- Use business language in the main view; place implementation details in evidence annotations.
- Separate participants, capabilities, services, domain objects, rules, and outcomes.
- Draw a relationship only when its verb can be stated precisely.
- Mark ownership and external boundaries explicitly.
- Show the value result and feedback path, not only an organizational inventory.
- Do not turn the canvas into a grid of unrelated capability cards.

