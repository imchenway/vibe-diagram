# Business flow reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family for ordered work, responsibility changes, decisions, exception paths, and stage gates.

## Templates

- `../assets/templates/business-flow/bpmn-light-flow.html`: a compact start, activity, gateway, activity, and outcome path.
- `../assets/templates/business-flow/dual-path-swimlane.html`: two aligned current-state paths with one shared trigger, one shared result, inline directed SVG arrows, and an explicitly broken cross-lane handoff.
- `../assets/templates/business-flow/exception-branch-flow.html`: a dominant path plus an explicit failure or recovery branch.
- `../assets/templates/business-flow/stage-track.html`: four stages with a cross-stage checkpoint strip.
- `../assets/templates/business-flow/swimlane-flow.html`: responsibilities and handoffs across three actors or systems.

Copy the selected template and replace slot content. Preserve its distinct DOM skeleton and directional grammar.

Choose `dual-path-swimlane` when the question is why two current paths that begin from the same trigger do not reach the same business result, especially when one path computes context or permission that the other path never receives. Keep the two paths aligned in the primary SVG, bind every authored relation to a visible SVG path, and encode the absent handoff as a broken relation rather than as a prose note or a separate attachment. Make the visible `h1` name the compared domain and the dual-path swimlane diagram type; put the diagnostic question in the summary instead of using the question as the title. Use `swimlane-flow` for three-role responsibility transfer without this path-comparison gap.

## Modeling rules

- Start with a trigger and end with a business result.
- Label gateways as questions and outgoing paths as mutually understandable outcomes.
- Use lanes only for responsibility; use stages only for time or maturity.
- Keep exceptions connected to the step that can cause them and show rejoin, termination, or compensation.
- Use verb-object activity labels and avoid card-style prose.
