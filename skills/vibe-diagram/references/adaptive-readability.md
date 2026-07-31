# Adaptive Readability and Semantic Relations

Use `artifact-shell@1` for the document frame, `adaptive-viewport@1` for generic-canvas presentation, and `semantic-relations@1` for authored meaning. The shared runtime may measure, scale, focus, and reset a canvas. It must not infer families, parse visible labels, invent nodes or relations, or rewrite the author's semantic structure.

## Global artifact shell

All 61 current templates declare exactly one `data-artifact-shell-title="1"` header. The title copy stays on the left and exactly one `data-artifact-shell-controls` region stays on the right; narrow viewports wrap the control region below the title copy. The current inventory also places a local `data-diagram-reading-guide="1"` section before each primary canvas stage, with `data-reading-guide-for` resolving to that canvas. This is a current template policy, not permission for the global shell to invent one fixed semantic legend for every future family. Generic and sequence controls remain in the title control region and expose 75%, 90%, 100%, then Auto.

The canonical shell CSS and shared runtime come from `assets/contracts/artifact-shell/v1.css` and `assets/contracts/artifact-shell/v1.js`; both are embedded byte-for-byte in every template. The runtime removes only unresolved `canvas-text-NNN` text nodes from an unfilled preview and no-ops once real task content is present. It also runs the screenshot-free computed layout audit described below. The builder verifies both kernels, title/control ownership, guide/canvas ownership, guide groups, evidence states, control modes, runtime-audit tokens, and all-template coverage. Templates do not get a page-level or after-canvas evidence exception.

Every graph-level title uses one `data-diagram-view-title="1"` heading with exactly one `data-diagram-view-type`, one `data-diagram-view-separator` that renders the full-width `｜`, and exactly one `data-diagram-view-subject`, in that order. This global rule does not apply to the page title, table captions, or detail headings.

### Local reading guide and title controls

- A local reading guide is optional at the global-shell level and required only when the selected family or template declares it. When present, it has one owning canvas, unique semantic groups, no separate `Reading guide` heading or card, and no page-level how-to-read prose. Group titles use a stronger label treatment than their items, and swatches reuse the owning diagram's actual visual tokens. A family-specific contract may require exact groups and labels; for example, code review requires relationship types plus observed, checked, and not-yet-verified evidence states.
- Controls always appear in the title control region in the order `75%`, `90%`, `100%`, then Auto.
- A local guide and its primary canvas share the same content boundary and ownership identifier. Wide diagrams may scroll horizontally only inside their canvas and must not create page-level horizontal overflow.
- In normal browsing, node details open in an anchored popover that flips and clamps to the viewport. It supports a close control, Escape, outside click, focus return, URL deep links, and browser back or forward navigation.
- Native `details` elements are no-JavaScript and print fallbacks. Once enhancement is active, they must not consume a bottom section in the normal document flow.

Canonical content surfaces outside the title and guide use only neutral `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` placeholders. Semantic roles, relation kinds, and local reading hints are also content attributes and therefore use `canvas-attribute-NNN`. Object, group, detail, relation, participant, sequence, matrix, and architecture references use their matching neutral `layout-*-NNN` identifiers. These identifiers describe fill positions and reference integrity, not business roles. Hard-coded canvas copy, semantic metadata, or domain-named identifiers fail the canonical build.

## Canvas contract

Each generic canvas declares `data-diagram-canvas`, `data-diagram-contract="1"`, a stable `data-diagram-id`, one `data-diagram-profile="graph|matrix|timeline|artboard|ledger"`, `data-diagram-width="contained|auto|wide"`, `data-diagram-height="flow|auto|scroll"`, and `data-diagram-mobile="stack|scroll|summary"`.

Fit width may choose a CSS scale from 75% through 100% only after measuring the unscaled authored stage. A canvas may declare `data-diagram-controls-mode="overflow|persistent"`. Overflow mode hides controls while the stage fits; persistent mode keeps the authored zoom controls available and applies manual percentages even while the stage fits. The percentage component and interaction contract are global, but persistent visibility is reserved for the primary canvas of `technical-design/technical-design-package`; all other templates use overflow behavior. If 75% cannot fit, keep semantic content unchanged and use scrolling. Re-test fit, selected scale, and control visibility after the canvas or stage resizes. Print, no-JavaScript, reduced-motion, and runtime-error paths must remain readable without enhancement.

Use `data-diagram-title-region` and `data-diagram-title-copy` for the title and conclusion. Put controls only in `data-artifact-shell-controls` inside that title region. The shared shell CSS owns responsive alignment; the adaptive or sequence runtime still owns whether an overflow-mode control set is shown.

## Semantic relation contract

Authors provide stable identifiers. Canonical templates use `layout-node-NNN` and `layout-group-NNN`; their `data-semantic-role` values are task-filled content attributes. Relations use `layout-relation-NNN`, neutral `data-from` and `data-to` references, and task-filled `data-relation-kind` plus non-empty `data-semantic`. This preserves reference integrity without encoding an actor, service, state, boundary, or other domain answer in the layout.

For graph policies with authored topology, the canvas also declares `data-diagram-topology` and `data-primary-direction="north-to-south|south-to-north|west-to-east|east-to-west"`. Nodes and groups declare integer `data-diagram-rank` plus `data-diagram-region`; group regions cover the policy's required regions and node regions reference one of those authored group regions. Every relation declares `data-primary-relation="true|false"`. Primary relations advance from a lower rank to a higher rank, while branch and merge requirements are checked from primary-relation endpoint degree. A template policy may additionally require authored SVG geometry: each node owns one numeric rectangle, rank centers progress on the declared axis, and each primary relation's absolute path starts and ends on the permitted node boundaries without reversing the declared axis. A layered north-to-south graph specifically exits the source's south edge and enters the target's north edge. A template id, layout name, CSS class, or visible prose never establishes direction by itself.

Matrix canvases additionally identify axes and cells with `data-matrix-row-id`, `data-matrix-col-id`, `data-matrix-row`, and `data-matrix-col`. Overview/detail projections use authored identifiers and `data-detail-for`. Every mobile summary or structural fallback names the covered canvas with `data-fallback-for`. Directional graph fallbacks bind each authored relation through `data-fallback-relation-id` and repeat its structured `data-from`, `data-to`, and `data-relation-kind`; visible route wording is not parsed as direction evidence.

## Evidence ledger contract

A populated generic `evidence-and-notes` slot contains one `data-evidence-ledger="1"` container rather than bare evidence prose. Every evidence entry declares a unique `data-evidence-id`, `data-evidence-status="observed|inferred|proposed|unresolved"`, one or more whitespace-separated semantic targets in `data-evidence-for`, `data-evidence-source-kind="file|line|log|test|command|user|runtime|design|external"`, and a non-empty `data-evidence-source`. Targets resolve against authored canvas, node, group, relation, or detail ids. Unfilled canonical placeholders are not runtime evidence.

The ledger is a local evidence boundary at the top-left of its owning canvas, before that canvas stage. Keep its visible content to two compact rows when the canvas already encodes evidence state by node color: put line styles and node evidence colors together, using a label, the same visual tokens as the diagram, and a non-color signal for each meaning. Do not wrap the rows in an independent card or add a guide heading, interaction group, or page-level operating instructions. Do not repeat file paths, implementation inventories, or validation prose in the guide; preserve those facts in structured attributes and mapped node details.

## Node detail disclosure

Templates that opt into node details give every outer semantic node one `data-detail-for` target and one matching native primary link. The outer node remains a non-link container so internal module links are never nested inside another anchor. Every independently visible auxiliary node likewise uses a native link and a unique native `details[data-diagram-detail]` target. With enhancement active, the shared runtime opens the mapped authored detail in a small anchored popover beside the selected trigger, clamps it to the viewport, and avoids scrolling the reader away from the node. Escape, the close control, and an outside click close the popover and return focus to its trigger. Native href navigation, no-JavaScript access, and print expansion remain authored in the HTML.

## Screenshot-free computed layout audit

`artifact-shell@1` runs `VibeDiagramQuality.auditAll()` after the DOM and fonts are ready and again after observed size changes. The audit reads computed DOM/SVG rectangles and path geometry rather than rasterizing the page. It checks node overlap, node-content overflow, auxiliary-node backgrounds, relation length and arrowheads, relation crossings through nodes or labels, endpoint anchoring, configured canvas-utilization thresholds, title-control order, and page-level horizontal overflow.

Each canvas exposes `data-computed-layout-audit="passed|failed"`, `data-computed-layout-issue-count`, and a bounded issue list; the document exposes aggregate status. This is the required efficient browser-layout signal. Screenshot capture, visual-diff storage, and pixel-baseline maintenance are not part of the normal gate.

## Complexity and disclosure

`contracts/family-policies.json` is the trusted allowlist for the eleven generic families and 55 non-sequence templates. Family budgets are hard upper bounds; a template may only narrow them. When a canvas exceeds its budget, author an overview plus linked details instead of hiding semantics in runtime behavior. Progressive disclosure is optional enhancement: the baseline HTML must preserve native navigation, natural document flow, and printable detail content.

`contracts/template-routing.json` separately controls delivery readiness. Every family has exactly one routing-ready default, every template is classified as ready or blocked, and the scaffold refuses blocked templates. This keeps unfinished legacy grammars available for controlled migration without allowing them to re-enter normal generation. A ready template with authored relations must render those relations as primary SVG paths; an HTML relation ledger remains a narrow-screen or print fallback and cannot satisfy the geometric carrier contract.

## 0.1.10 straight-first routing contract

- Direct relationships have zero bends. Curves or decorative detours cannot bypass this rule.
- Branch and merge routes have at most one necessary bend and enter or leave through clear boundary anchors.
- Feedback loops declare `data-route-reason`, use an independent channel, and never compete with the primary path for the same space.
- The linter checks declared bend budgets. Computed browser layout separately checks collisions between arrows, nodes, labels, and other visible relationships.
- Size nodes for their actual copy before layout. Runtime checks text overflow, empty nodes, canvas utilization, and label overlap; never hide a failure by shrinking important text.

## Scope and evidence boundaries

All 61 canonical templates are registered under `artifact-shell@1`. The 55 generic templates additionally use the adaptive and semantic relation contracts. The six sequence templates remain governed by `sequence-contract@1` for canvas behavior while sharing only the global artifact shell; do not double-parse them as generic canvases.

Canonical completeness is a source and static-contract statement. A computed-layout result is evidence only for the browser and viewport in which it ran. Neither source completeness nor a passing computed audit proves any client lifecycle. Keep `client_runtime` unverified until installation, discovery, invocation, output delivery, upgrade, and uninstall have actually been exercised.

The linter can prove that authored ranks, regions, SVG rectangle coordinates, supported absolute path vertices, fallback bindings, detail mappings, policy thresholds, and evidence references are internally consistent. It also applies visible-language checking to every Chinese HTML artifact, independent of diagram family; stable semantic ids and recognizable technical names may remain untranslated, while ordinary labels and unresolved visible placeholders fail closed. Computed layout, clipping, collisions, route/label intersections, page overflow, and control placement are evaluated by the shared in-browser audit and reported as structured state, not inferred from a screenshot or from a passing linter.
