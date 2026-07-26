# Decision communication reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family when the reader must understand options, criteria, tradeoffs, a recommendation, and the conditions that would change it.

## Templates

- `../assets/templates/decision-communication/decision-tree.html`: conditions, branches, outcomes, and the recommended leaf.
- `../assets/templates/decision-communication/option-matrix-path.html`: the 0.1.10 default decision matrix, using criteria rows, candidate columns, factual cells, a conclusion, and review conditions.
- `../assets/templates/decision-communication/recommended-path.html`: show the recommended sequence with a visible risk branch.
- `../assets/templates/decision-communication/tradeoff-quadrant.html`: position alternatives on two named decision axes.

Copy the selected template and replace slots; do not reuse one generic matrix skeleton for all four choices.

## Modeling rules

- A decision matrix contains complete criterion rows, candidate columns, and factual values. Every candidate uses the same criteria; flow cards cannot stand in for a matrix.
- Weights are optional input. When the user provides no weights, do not invent scores, totals, or precise rankings. A recommendation must state the evidence and preference basis directly.
- The conclusion region includes the recommendation, decisive constraints, and review conditions. Do not add perimeter arrows merely to make a matrix feel like a process.

- State the decision question and decision owner.
- Use comparable criteria and evidence for every option.
- Separate facts from weights and preferences.
- Make the recommendation visually dominant and show its risks, assumptions, and reversal trigger.
- A quadrant requires meaningful axes; a tree requires mutually understandable branch labels.
