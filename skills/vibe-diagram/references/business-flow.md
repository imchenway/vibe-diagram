# Business flow reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family for ordered work, responsibility changes, decisions, exception paths, and stage gates.

## Templates

- `../assets/templates/business-flow/logic-flowchart.html`: the default basic logic flowchart for start, processing, a question-shaped decision, explicit yes/no branches, merge, optional feedback loop, and end. Its primary relations are anchored SVG paths inside the canvas; every node has a matching native detail disclosure, and the narrow-screen fallback preserves every authored relation.
- `../assets/templates/business-flow/bpmn-light-flow.html`: a compact legacy/native start, activity, gateway, activity, and outcome path. Use it only when the task explicitly needs this compact native topology; it is not a standards-compliant BPMN substitute.
- `../assets/templates/business-flow/dual-path-swimlane.html`: two aligned current-state paths with one shared trigger, one shared result, inline directed SVG arrows, and an explicitly broken cross-lane handoff.
- `../assets/templates/business-flow/exception-branch-flow.html`: shares the basic-flow node, branch, merge, and routing kernel while emphasizing failure origin, compensation, retry, and rejoin.
- `../assets/templates/business-flow/stage-track.html`: four stages with a cross-stage checkpoint strip.
- `../assets/templates/business-flow/swimlane-flow.html`: responsibilities and handoffs across three actors or systems.

Copy the selected template and replace slot content. Preserve its distinct DOM skeleton and directional grammar.

Choose `logic-flowchart` by default when the user asks to explain ordinary logic, conditions, if/else behavior, a decision, branching and merging, or a bounded loop without naming an external notation standard. The main canvas must remain a flowchart: terminators, process nodes, question-shaped decisions, outcome-labeled branches, merge points, and anchored arrows carry the explanation. Do not replace that topology with cards, a step list, or a relation ledger.

Choose `exception-branch-flow` only when the exception path itself is the question: where failure originates, what recovery or compensation occurs, whether the operation retries, and where it rejoins or terminates. Keep both the dominant path and recovery path in the same SVG coordinate system. A prose ledger may supplement the diagram for accessibility or evidence, but it can never be the primary relationship carrier.

Choose `dual-path-swimlane` when the question is why two current paths that begin from the same trigger do not reach the same business result, especially when one path computes context or permission that the other path never receives. Keep the two paths aligned in the primary SVG, bind every authored relation to a visible SVG path, and encode the absent handoff as a broken relation rather than as a prose note or a separate attachment. Make the visible `h1` name the compared domain and the dual-path swimlane diagram type; put the diagnostic question in the summary instead of using the question as the title. Use `swimlane-flow` for three-role responsibility transfer without this path-comparison gap.

## Modeling rules

- In 0.1.10, ordinary, decision, exception, compensation, and rollback flows share the strong `logic-flowchart` kernel and default north-to-south. A horizontal layout is allowed only when copy length and branch density clearly support it.
- Connect adjacent nodes directly. Branches leave from explicit decision exits, merges enter an explicit merge point, and two arrowheads must never crowd the same node edge.
- Direct relationships have zero bends. Branch and merge routes have at most one necessary bend. Compensation and rollback feedback declare their semantic reason and use an independent loop channel.

- Start with a trigger and end with a business result.
- Label gateways as questions and outgoing paths as mutually understandable outcomes.
- Use lanes only for responsibility; use stages only for time or maturity.
- Keep exceptions connected to the step that can cause them and show rejoin, termination, or compensation.
- For graph-like flow templates, render every semantic relationship as an in-canvas SVG `path` anchored to its source and target. HTML relationship records exist for semantics and fallback binding, not as a substitute for the main diagram.
- Give every interactive node exactly one native detail disclosure and preserve the same complete relationship set in the narrow-screen fallback.
- Use verb-object activity labels and avoid card-style prose.
