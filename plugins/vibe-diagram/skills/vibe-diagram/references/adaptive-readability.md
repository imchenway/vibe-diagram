# Adaptive Readability and Semantic Relations

Use `adaptive-viewport@1` for presentation and `semantic-relations@1` for authored meaning. The shared runtime may measure, scale, focus, and reset a canvas. It must not infer families, parse visible labels, invent nodes or relations, or rewrite the author's semantic structure.

## Canvas contract

Each generic canvas declares `data-diagram-canvas`, `data-diagram-contract="1"`, a stable `data-diagram-id`, one `data-diagram-profile="graph|matrix|timeline|artboard|ledger"`, `data-diagram-width="contained|auto|wide"`, `data-diagram-height="flow|auto|scroll"`, and `data-diagram-mobile="stack|scroll|summary"`.

Fit width may choose a CSS scale from 75% through 100% only after measuring the unscaled authored stage. A canvas may declare `data-diagram-controls-mode="overflow|persistent"`. Overflow mode hides controls while the stage fits; persistent mode keeps the authored zoom controls available and applies manual percentages even while the stage fits. If 75% cannot fit, keep semantic content unchanged and use scrolling. Re-test fit, selected scale, and control visibility after the canvas or stage resizes. Print, no-JavaScript, reduced-motion, and runtime-error paths must remain readable without enhancement.

Use `data-diagram-title-region` on a title-and-actions wrapper and `data-diagram-title-copy` on its text block when controls should sit inside the diagram title area. The shared CSS owns the responsive alignment; the runtime still owns whether the controls are shown.

## Semantic relation contract

Authors provide stable identifiers. Use `data-diagram-node-id` and `data-semantic-role` for nodes, `data-diagram-group-id` and `data-semantic-role` for groups, and `data-diagram-relation-id`, `data-from`, `data-to`, `data-relation-kind`, and non-empty `data-semantic` for relations.

For graph policies with authored topology, the canvas also declares `data-diagram-topology` and `data-primary-direction="north-to-south|south-to-north|west-to-east|east-to-west"`. Nodes and groups declare integer `data-diagram-rank` plus `data-diagram-region`; group regions cover the policy's required regions and node regions reference one of those authored group regions. Every relation declares `data-primary-relation="true|false"`. Primary relations advance from a lower rank to a higher rank, while branch and merge requirements are checked from primary-relation endpoint degree. A template policy may additionally require authored SVG geometry: each node owns one numeric rectangle, rank centers progress on the declared axis, and each primary relation's absolute path starts and ends on the permitted node boundaries without reversing the declared axis. A layered north-to-south graph specifically exits the source's south edge and enters the target's north edge. A template id, layout name, CSS class, or visible prose never establishes direction by itself.

Matrix canvases additionally identify axes and cells with `data-matrix-row-id`, `data-matrix-col-id`, `data-matrix-row`, and `data-matrix-col`. Overview/detail projections use authored identifiers and `data-detail-for`. Every mobile summary or structural fallback names the covered canvas with `data-fallback-for`. Directional graph fallbacks bind each authored relation through `data-fallback-relation-id` and repeat its structured `data-from`, `data-to`, and `data-relation-kind`; visible route wording is not parsed as direction evidence.

## Evidence ledger contract

A populated generic `evidence-and-notes` slot contains one `data-evidence-ledger="1"` container rather than bare evidence prose. Every evidence entry declares a unique `data-evidence-id`, `data-evidence-status="observed|inferred|proposed|unresolved"`, one or more whitespace-separated semantic targets in `data-evidence-for`, `data-evidence-source-kind="file|line|log|test|command|user|runtime|design|external"`, and a non-empty `data-evidence-source`. Targets resolve against authored canvas, node, group, relation, or detail ids. Unfilled canonical placeholders are not runtime evidence.

The default ledger is a pre-reading evidence boundary after the title region and before the first primary canvas. Keep its visible content to a compact reading guide when the canvas already encodes evidence state by node color: put line styles and node evidence colors in the same guide, using a label, visual sample, and non-color signal for each meaning. When the template exposes mapped node details, add exactly one concise interaction hint to the guide's interaction group and keep it outside the SVG canvas. Do not repeat file paths, implementation inventories, or validation prose in the guide; preserve those facts in structured attributes and mapped node details. A trusted template policy may instead declare `evidence_placement: after-primary-canvas` when the diagram itself should be the first answer. In that mode, place the guide immediately after the canvas and keep the same compact vocabulary.

## Node detail disclosure

Templates that opt into node details give every node one `data-detail-for` target and provide exactly one native `details` block with the matching `data-diagram-detail-id`. The node itself remains a focusable link whose `href` reaches that detail without JavaScript. With enhancement active, the shared runtime opens the mapped detail in a small anchored popover beside the selected node, clamps the popover to the viewport, and avoids scrolling the reader away from the selected node. Escape, the close control, and an outside click close the popover and return focus to its trigger. The mapping, summary, content, no-JavaScript path, and print expansion remain authored in the HTML.

## Complexity and disclosure

`contracts/family-policies.json` is the trusted allowlist for the ten generic families and 53 non-sequence templates. Family budgets are hard upper bounds; a template may only narrow them. When a canvas exceeds its budget, author an overview plus linked details instead of hiding semantics in runtime behavior. Progressive disclosure is optional enhancement: the baseline HTML must preserve native navigation, natural document flow, and printable detail content.

## Scope and evidence boundaries

All 53 canonical generic templates are registered under this contract. The six sequence templates remain governed exclusively by `sequence-contract@1`; do not double-parse or rewrite them as generic canvases.

Canonical completeness is a source and static-contract statement. It does not prove rendering in a browser or any client lifecycle. Keep `browser_runtime` pending and `client_runtime` unverified until their respective runtime evidence has actually been collected.

The linter can prove that authored ranks, regions, SVG rectangle coordinates, supported absolute path vertices, fallback bindings, and evidence references are internally consistent. It also applies visible-language checking to every Chinese HTML artifact, independent of diagram family; stable semantic ids and recognizable technical names may remain untranslated, while ordinary labels and unresolved visible placeholders fail closed. It cannot prove the browser's computed pixel geometry, clipping, collision behavior, hit targets, or focus movement. Browser acceptance for a directional graph records the tested viewport sizes and verifies computed node bounding-box order, arrowhead endpoints, group placement, collision absence, page overflow, and measured control visibility at each width.
