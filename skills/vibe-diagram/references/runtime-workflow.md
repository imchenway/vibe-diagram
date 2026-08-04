# Vibe Diagram Runtime Workflow

## Scope and activation

Use this skill when relationships, flow, time, causality, state, evidence, or before/after change would be harder to verify as prose. Do not force a diagram when one short sentence, a command, or a small list is clearer.

Follow the user's language for visible content; use English when the language cannot be determined. Preserve explicit uncertainty and distinguish observed facts, inferences, proposed design, and unresolved questions.

Determine the authored output language before filling the scaffold. Set the document `lang` accordingly and translate every visible template-authored string, not only the title and free-text slots. Node titles, node summaries, region labels, legends, controls, detail summaries, mobile fallbacks, evidence headings, and status wording must all follow the current user request. Canonical English is only the source default; it must not leak into a Chinese artifact.

## Artifact contract

Produce a self-contained single-file HTML document as the primary artifact. Inline all CSS and JavaScript and keep the document readable without a network connection.

PNG or SVG may be added only when the user explicitly requests an image supplement; either must not replace the HTML artifact. Start from a matching asset template and replace its slots instead of rebuilding a generic card page.

Create the artifact with `python3 <skill-root>/scripts/vibe_diagram_scaffold.py --type <family> --template <id> --standard native --output <path>` when no external notation was named. Do not hand-create the file. Preserve the canonical style and script blocks, global artifact shell, slot inventory, template contract, and visual grammar. A canonical template is a content-neutral layout contract: it may fix topology, relative position, hierarchy, geometry, connection anchors, complexity budget, responsive transformation, and interaction capability, but it must not prescribe an entry, core, operations area, actor, component, state, module, title, icon, description, relation label, semantic role, relation kind, or evidence claim. Fill every neutral `layout-slot-NNN`, `canvas-text-NNN`, and `canvas-attribute-NNN` placeholder from the current task's facts. Keep canonical object, detail, relation, participant, matrix, and sequence references on their neutral `layout-*-NNN` identifiers; do not rename them to domain assumptions. If the selected layout cannot hold the primary model, choose another template or create mapped overview and detail artifacts.

For a code-review package, use `--review-spec <spec.json>` or repeat `--review-kind <kind>`. The scaffold resolves each kind through the trusted route matrix and generates the current and proposed-repair diagrams from the same topology, with an evidence-authored trigger/process/impact scenario between them. It rejects an unknown or ambiguous kind instead of choosing a visual fallback.

`contracts/template-routing.json` is the fail-closed delivery allowlist. Use its family default when the user names only a diagram family or asks for a common view without a more specific topology. The scaffold and delivery linter reject templates whose true-diagram migration is still blocked; never bypass that result by copying a legacy file manually. For a generic request such as “draw a flowchart”, “show the logic”, or “explain this if/else”, select `business-flow/logic-flowchart`. Select exception, swimlane, or stage grammars only when the user's facts actually require compensation, responsibility lanes, or time stages.

Native mode is the default only when the user has not named an external notation. If the user explicitly asks for UML, BPMN, C4, ArchiMate, or another standard, pass that name through `--standard` and apply the standard's real syntax and conformance rules. The scaffold fails closed while no strict canonical implementation exists; never omit `--standard`, silently downgrade to native mode, or route an explicit BPMN request to `bpmn-light-flow`.

### 0.1.10 domain terms and drawing order

- **Native family**: the Vibe Diagram grammar used when the user does not name an external standard. Every family has an independent structure; they do not share one card-grid grammar.
- **Primary canvas**: the view carrying the main relationship geometry, not a thumbnail preview, relationship list, or explanation card.
- **Direct route**: a zero-bend relationship between source and target. A **necessary bend** is reserved for one branch or merge. A **feedback loop** has a semantic reason and independent channel.
- **Static contract**, **computed browser layout**, and **client lifecycle** are independent evidence classes; an earlier class never substitutes for a later one.

The fixed work order is: select the correct family and grammar, size nodes and relationships for real copy, complete a readable primary canvas, then run scripts to detect regressions efficiently. Never assemble a diagram backward merely to pass checks, and never shrink text to conceal structural failure.

## Invocation completion

Treat a visual request as `invocation-complete` only after the update gate, workflow load, template selection, canonical scaffold, strict linter, and HTML delivery all succeed. Loading this Skill, describing a diagram, or returning Mermaid is incomplete. Mermaid may supplement the HTML only when useful.

After the user has authorized the artifact and evidence can determine the template, continue through scaffold, authored filling, lint repair, the screenshot-free computed layout audit when browser geometry matters, and delivery in one uninterrupted workflow. Pause only for a real unresolved decision that would change meaning, scope, or authorized side effects; do not ask the user to repeat “continue” between routine stages.

## Capability-based delivery

Choose delivery only from available capabilities:

- `can_write_file`: write the HTML to the requested or current project location and return its path.
- `can_attach_file`: attach the HTML artifact when direct file attachment is available.
- `can_open_local_link`: provide an openable local link in addition to the absolute path.
- `text_only`: return one complete HTML code block and state that file writing is unavailable.

Do not infer delivery behavior from a host name, installation path, or brand.

## Candidate atlas calibration mode

When the user asks for alternatives, first produce a compact atlas of meaningfully different topologies. Label the recommended candidate, state the tradeoff for each option, and keep every candidate grounded in the same evidence. After selection, produce one final artifact rather than leaving a tabbed gallery in the deliverable.

## Automatic routing

Route by the relationship the user must understand:

- System structure that fits either a workload overview or a north-to-south logical layering: system architecture.
- Roles, capabilities, domains, rules, or value creation: business architecture.
- Ordered work across roles or exception branches: business flow.
- Calls, returns, async callbacks, retries, and time: code sequence.
- State transitions, entities, lifecycle, or data movement: state/data model.
- Symptom-to-cause evidence and repair verification: fault debugging.
- Multiple code-review findings with current diagram, factual scenario, and paired-topology repair diagram: code review. Route each finding by its primary relationship, never by severity, language, repository, or filename.
- Release, observation, gates, compensation, or rollback: business flow; use a state machine only when the user explicitly asks for state semantics.

Treat the current routing catalog as exhaustive: any absent family or code-review relation kind must fail closed instead of being replaced with a visually similar template. `delivery-acceptance` is a one-cycle compatibility alias only; new ordered acceptance requests must use business flow, while itemized requirement-to-evidence comparisons remain unsupported.

For any of the five sequence templates, read the `Sequence interaction contract` in its owning reference before editing the template.

## Shared diagram grammar

Give every major node one role, every connector one direction, and every visual encoding one stable meaning. Put the primary reading path in the dominant direction. Use boundaries for ownership or trust, lanes for actors, phases for time, and evidence annotations for claims.

Template identity is provenance, not topology evidence. A template id, layout name, CSS class, heading, or visible phrase such as “north to south” does not establish the authored primary direction. Graph canvases that make a directional claim must declare `data-primary-direction`, give semantic objects authored `data-diagram-rank` and `data-diagram-region` values, and classify relations with `data-primary-relation="true|false"`. The primary relation endpoints must advance through authored ranks; policies that require geometric direction also verify authored SVG node bounds and path endpoints against that axis. Secondary and feedback relations remain explicit without being mistaken for the primary path.

Copy the selected HTML template, preserve `data-diagram-type`, `data-template-family`, `data-template-id`, `data-template-layout`, responsive structure, and slot/macro bindings, then replace visible content. Add local structure only when existing slots cannot express the verified model.

## Global generation requirements

These requirements apply to every diagram family. They define generation discipline, not one universal drawing grammar. A family reference or policy owns family-specific fields and budgets; each template owns its topology, coordinates, slots, and permitted visual primitives.

For every routing-ready template, the primary canvas must carry the meaning geometrically. Every authored relation binds to one visible SVG route anchored to its endpoint shapes; an HTML relation ledger is secondary fallback or evidence and cannot satisfy the primary carrier. A routing-ready graph or timeline gives every semantic node measurable SVG geometry and every directed route a visible arrowhead. Declared relations with zero audited routes are a hard failure, not an empty successful audit.

### G0 — Global shell and content-neutral templates

Every artifact uses the same fail-closed shell: one title-and-conclusion region with one right-side control region, followed by the primary canvases. The shell owns title wrapping, control placement, canvas ownership, and the structural integrity of any local guide; it does not prescribe domain-specific guide groups. In a standalone artifact, make the page `h1` the only graph-level title and render its diagram type, full-width separator, and subject as the required structured parts. In a multi-diagram package, keep an independent page title only when needed and give every subgraph its own structured title. When a family or template requires a local guide, render it visibly inside the owning diagram surface at the top-left, before the diagram body, on the same continuous 24-pixel grid as that body and without an independent heading, border, background, shadow, card, or ungridded separator strip. Its group titles must be visually stronger than their items. Author each relation label from the current artifact and bind it to the actual relations it describes so the shell can reuse their computed color and line style; never copy the generic source defaults into the result without checking the filled diagram. Do not render interaction prose, evidence prose, or decorative group separators. Each title-side control set exposes 75%, 90%, 100%, then Auto; at narrower widths the control region wraps below the title copy without entering a canvas.

Treat every canonical template as layout, not domain guidance. Never infer visible content from a template filename, CSS class, structural id, former example, position, color, or placeholder order. The canonical source must keep content surfaces neutral; generated artifacts replace those neutral placeholders with language-matched, evidence-backed content. The builder and linter reject a canonical template that restores hard-coded canvas copy, domain-named content slots, a moved guide, or controls outside the title control region.

When a canonical template is opened before filling, suppress unresolved `canvas-text-NNN` tokens throughout every canvas so the preview shows geometry instead of colliding macro names. This preview-only behavior must preserve the source macros and must no-op after real task content has replaced them.

### G1 — Evidence status and uncertainty

Separate observed facts, supported inferences, proposed design, and unresolved questions. Never complete missing modules, endpoints, permissions, timing, or root causes merely to make a diagram look complete.

### G2 — Structured and visible relationships

Give every important object, relationship, direction, and boundary a stable identity, and bind each authored relationship to a visible encoding in the primary artifact. Hidden metadata alone is not a diagram.

### G3 — Primary path and layered evidence

Expose the conclusion and primary reading path first. Place concise evidence beside the object or transition it supports, then place the complete evidence ledger later. Interactive disclosure may enhance access but must not be the only carrier of a fact.

For a generic canvas, put complete evidence in one `data-evidence-ledger="1"` container. Each evidence entry declares a unique `data-evidence-id`, one status (`observed`, `inferred`, `proposed`, or `unresolved`), the semantic ids it supports through `data-evidence-for`, and an authored source kind plus source reference. Plain prose in the `evidence-and-notes` slot is a note, not a verifiable evidence ledger, and must not be used as the only evidence carrier.

When the selected family or template requires an evidence ledger, place it at the top-left of its owning canvas before the primary stage and link it with `data-reading-guide-for`. Keep the guide local instead of scattering related legends around the page. Do not add interaction instructions to the guide or float them inside the SVG canvas. The family reference owns the required guide groups, labels, and evidence-state vocabulary; detailed provenance remains in structured attributes and mapped node details.

### G4 — Stable, collision-free visual encoding

Use each shape, line style, and color for one stable meaning. Color must never be the only signal. Give distinct flows visibly distinct line colors, keep arrowheads readable without making them oversized, keep connectors out of labels, anchor every route to the owning object boundary, and use deliberate whitespace or a label mask where a route crosses text. Relation endpoints and routes must remain bound to the outer semantic object when internal chip counts or columns change.

### G5 — Readability without unlimited shrinking

Keep essential text readable. When the viewport or complexity budget is exceeded, prefer reflow, scoped scrolling, or mapped overview/detail views. Keep the zoom component in every template, keep it visible whenever the canvas is measurable, and keep its size, pressed state, focus state, and status treatment consistent. The current fit result may change its status wording, but it must not hide the component.

Use `data-diagram-controls-mode="persistent"` for every adaptive canvas. Sequence canvases follow the same persistent-visibility rule through their sequence toolbar. A code-review package keeps exactly one canonical control group and applies the same requested zoom to its current and repair diagrams; its factual scenario remains normal text and is never scaled. Keep controls visible whenever the stage is measurable, even when it already fits; manual percentages must still apply. Re-evaluate fit, status text, and selected scale after container or viewport resize. Controls always stay in `data-artifact-shell-controls` inside the title region; they never move into finding navigation or a canvas. A code-review canvas grows with the document and must not create a nested vertical scroll container.

A code-review canvas never owns vertical scrolling. Its block size follows the authored graph, the page owns the only vertical reading flow, and the canvas exposes scoped horizontal scrolling only when the graph cannot fit at the 75% readability floor. Do not use a viewport-bound maximum height, `overflow: auto`, or vertical overscroll containment on a review canvas.

### G6 — Equivalent fallback across environments

Preserve the same core identities, directions, boundaries, ordering, and evidence on mobile, keyboard, touch, reduced-motion, no-JavaScript, print, and enhancement-failure paths. Avoid page-level horizontal overflow and do not replace the primary model with an unrelated summary.

### G7 — Complexity requires mapped decomposition

Apply the trusted family budget. When it is exceeded, produce explicitly mapped overview and detail artifacts. Do not conceal overload by hiding content, merging distinct identities, or reducing essential text below the reading floor.

### G8 — Self-evidencing single-file delivery

Keep the artifact self-contained, free of remote runtime dependencies, and traceable to its template identity. Run the formal linter before delivery and state static and runtime evidence separately.

## Layout, arrows, and collision control

Lay out the main path before secondary evidence. Keep arrows outside label boxes, route branches through explicit junctions, and avoid crossings through nodes. Prefer vertical scrolling on narrow screens; never solve density by shrinking essential text below readable size.

Direct relations declare `data-route-intent="direct"` and have zero bends. Branch and merge routes declare their intent and may use at most one necessary bend. Feedback routes declare `data-route-intent="feedback"` plus a non-empty `data-route-reason`, stay in a dedicated channel, and must not re-enter through an ambiguous shared arrowhead.

Use progressive detail: overview first, local evidence second, full ledger last. A large diagram may use internal navigation, but its default view must still expose the conclusion and primary path.

For graph fallbacks, repeat authored relation ids and their `data-from`, `data-to`, and `data-relation-kind` endpoints. A list of node names or a sentence that merely says “A to B” is not an equivalent directional fallback because its direction cannot be verified without parsing visible prose.

When the selected template supports node details, author one concise, language-matched title and summary on the primary node, then give it one owned native primary link mapped through `data-detail-for` to one native `details[data-diagram-detail]` block. Keep the outer semantic node as a non-link container when it also contains independent small-node links. Give every visible internal module, chip, or supporting card its own native auxiliary link and unique authored detail. With enhancement active, open the detail as a small anchored popover beside the selected trigger; clamp and flip it within the viewport rather than turning it into a side inspector or full-width sheet. Esc, point-outside, the close button, and browser history must close or restore the correct deep-linked detail, and closing returns focus to the originating trigger. Native details stay out of normal layout when enhanced but must remain available without JavaScript and expand for print.

## Visual quality and accessibility

Use semantic HTML, one visible `h1`, high-contrast text, keyboard-operable controls, visible focus, and reduced-motion handling. Keep touch targets usable, labels concise, and color supplementary rather than the sole carrier of meaning.

On mobile, preserve reading order and avoid page-level horizontal overflow. For print, expand hidden or scrollable content and prevent sticky or transformed layers from clipping the artifact.

## Evidence and uncertainty

Attach file paths, anchors, logs, tests, or user-provided facts to the claims they support. Mark inferred links as inference and future behavior as design. If sources conflict, show the conflict and stop short of a false conclusion.

Do not invent modules, actors, fields, timings, permissions, or root causes merely to make the picture look complete.

## Pre-delivery checks

Before delivery:

1. Confirm the chosen reference and template match the user's question.
2. Confirm the primary path, exceptions, evidence, uncertainty, and result are visible.
3. Confirm the HTML is self-contained, responsive, keyboard readable, and printable.
4. Confirm template identity and macros remain valid.
5. Run `python3 <skill-root>/scripts/vibe_diagram_lint.py <artifact> --type <family>` and fix every reported error.
6. When computed browser geometry is material, serve the artifact over local HTTP, wait for fonts, and run `VibeDiagramQuality.auditAll()` at `1440×900`, `1280×800`, and `390×844`. Require `data-computed-layout-audit="passed"` with zero issues, guide/canvas horizontal alignment within `1 CSS px`, zero text or node overflow, zero empty components, and zero meaningless bends. Exercise every node detail for positioning, close button, Esc, outside click, focus return, deep linking, browser history, and narrow-screen avoidance. Do not create screenshots or pixel baselines for this gate.
7. Confirm the final response contains an HTML artifact path or, in text-only mode, one complete HTML code block; Mermaid-only delivery is forbidden.
8. Return the artifact path plus only the brief context needed to use it.

Static checks establish authored structure and supported SVG coordinates only. The shared browser audit evaluates the real computed layout at the declared desktop and narrow widths: node collisions and overflow, relation endpoints and crossings, group utilization, page-level horizontal overflow, and interaction/zoom order. Record viewport sizes plus the structured audit result. A screenshot is optional communication material only when explicitly requested; it is not acceptance evidence and no visual-diff baseline is maintained.

The 0.1.10 evidence report has three layers. `static-contract-valid` covers only canonical sources and linting. `browser-layout-verified` covers only the actual Chromium build and tested viewports. `client-runtime-verified` requires real installation, discovery, invocation, delivery, upgrade, and uninstall. If the client lifecycle was not exercised in the current run, it remains explicitly unverified.
