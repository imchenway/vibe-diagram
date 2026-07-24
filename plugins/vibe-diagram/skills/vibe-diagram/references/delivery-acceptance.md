# Delivery acceptance reference

## Content-neutral template boundary

This template family defines only topology, relative placement, layering or lanes, complexity ceilings, connection anchors, responsive transformations, and interaction capabilities. Every visible title, icon, node, relation, note, evidence item, and detail must be filled from facts established for the current task. `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` are positional placeholders without domain semantics. Never treat a template filename, structural identifier, prior example, or visual position as a system fact.

Use this family to connect original requirements to delivered changes, verification evidence, decisions, risk actions, and sign-off.

## Templates

- `../assets/templates/delivery-acceptance/acceptance-ledger.html`: requirement-to-change-to-evidence acceptance rows.
- `../assets/templates/delivery-acceptance/delivery-timeline.html`: delivery milestones and checkpoints in time order.
- `../assets/templates/delivery-acceptance/evidence-swimlane.html`: evidence ownership and collection across sources.
- `../assets/templates/delivery-acceptance/risk-action-board.html`: risk, impact, owner, action, and status.

Copy the selected template and preserve the evidence ledger structure.

## Modeling rules

- Every user requirement or acceptance criterion must have an independent R# lane from original wording through change, evidence, decision, and remaining action.
- No evidence means warn or blocked; never merge an unproven item into an overall pass.
- A whole-suite gate must not replace per-requirement evidence. Put commands, results, screenshots, and package checks on the R# lane they prove.
- Every acceptance claim must link to a requirement and reproducible evidence.
- Distinguish implemented, verified, unverified, blocked, and out-of-scope states.
- Show remaining risk and rollback conditions beside the acceptance result.
- Use exact commands, paths, screenshots, logs, or test identifiers where available.
- Do not treat static validation as proof of an unverified runtime or client behavior.
- Expose what changed, affected entry points, required scripts or restarts, verification steps, and uncovered areas next to the ledger. State explicitly when no script or restart is needed.
- Use text plus shape or icon for pass, warn, fail, and blocked; never rely on color alone.
