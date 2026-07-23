# Vibe Diagram Runtime Workflow

## Scope and activation

Use this skill when relationships, flow, time, causality, state, evidence, or before/after change would be harder to verify as prose. Do not force a diagram when one short sentence, a command, or a small list is clearer.

Follow the user's language for visible content; use English when the language cannot be determined. Preserve explicit uncertainty and distinguish observed facts, inferences, proposed design, and unresolved questions.

Determine the authored output language before filling the scaffold. Set the document `lang` accordingly and translate every visible template-authored string, not only the title and free-text slots. Node titles, node summaries, region labels, legends, controls, detail summaries, mobile fallbacks, evidence headings, and status wording must all follow the current user request. Canonical English is only the source default; it must not leak into a Chinese artifact.

## Artifact contract

Produce a self-contained single-file HTML document as the primary artifact. Inline all CSS and JavaScript and keep the document readable without a network connection.

PNG or SVG may be added only when the user explicitly requests an image supplement; either must not replace the HTML artifact. Start from a matching asset template and replace its slots instead of rebuilding a generic card page.

Create the artifact with `python3 <skill-root>/scripts/vibe_diagram_scaffold.py --type <family> --template <id> --output <path>`. Do not hand-create the file. Preserve the canonical style and script blocks, slot inventory, template contract, and visual grammar. If the selected template cannot hold the primary model, choose another template or create mapped overview and detail artifacts.

## Invocation completion

Treat a visual request as `invocation-complete` only after the update gate, workflow load, template selection, canonical scaffold, strict linter, and HTML delivery all succeed. Loading this Skill, describing a diagram, or returning Mermaid is incomplete. Mermaid may supplement the HTML only when useful.

After the user has authorized the artifact and evidence can determine the template, continue through scaffold, authored filling, lint repair, any required browser acceptance, and delivery in one uninterrupted workflow. Pause only for a real unresolved decision that would change meaning, scope, or authorized side effects; do not ask the user to repeat “continue” between routine stages.

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

- System boundary, component, deployment, security, or runtime topology: system architecture.
- Roles, capabilities, domains, rules, or value creation: business architecture.
- Ordered work across roles or exception branches: business flow.
- Calls, returns, async callbacks, retries, and time: code sequence.
- State transitions, entities, lifecycle, or data movement: state/data model.
- Symptom-to-cause evidence and repair verification: fault debugging.
- Current-to-target behavior and rollout or rollback: feature iteration.
- Screen hierarchy, responsive states, or page journeys: page mockup.
- Module contracts, consistency, release switching, or detailed engineering constraints: technical design.
- Options, tradeoffs, recommendations, and decisions: decision communication.
- Requirements, changes, evidence, risk, and sign-off: delivery acceptance.

For any of the six sequence templates, read the `Sequence interaction contract` in its owning reference before editing the template.

## Shared diagram grammar

Give every major node one role, every connector one direction, and every visual encoding one stable meaning. Put the primary reading path in the dominant direction. Use boundaries for ownership or trust, lanes for actors, phases for time, and evidence annotations for claims.

Template identity is provenance, not topology evidence. A template id, layout name, CSS class, heading, or visible phrase such as “north to south” does not establish the authored primary direction. Graph canvases that make a directional claim must declare `data-primary-direction`, give semantic objects authored `data-diagram-rank` and `data-diagram-region` values, and classify relations with `data-primary-relation="true|false"`. The primary relation endpoints must advance through authored ranks; policies that require geometric direction also verify authored SVG node bounds and path endpoints against that axis. Secondary and feedback relations remain explicit without being mistaken for the primary path.

Copy the selected HTML template, preserve `data-diagram-type`, `data-template-family`, `data-template-id`, `data-template-layout`, responsive structure, and slot/macro bindings, then replace visible content. Add local structure only when existing slots cannot express the verified model.

## Global generation requirements

These requirements apply to every diagram family. They define generation discipline, not one universal drawing grammar. A family reference or policy owns family-specific fields and budgets; each template owns its topology, coordinates, slots, and permitted visual primitives.

### G1 — Evidence status and uncertainty

Separate observed facts, supported inferences, proposed design, and unresolved questions. Never complete missing modules, endpoints, permissions, timing, or root causes merely to make a diagram look complete.

### G2 — Structured and visible relationships

Give every important object, relationship, direction, and boundary a stable identity, and bind each authored relationship to a visible encoding in the primary artifact. Hidden metadata alone is not a diagram.

### G3 — Primary path and layered evidence

Expose the conclusion and primary reading path first. Place concise evidence beside the object or transition it supports, then place the complete evidence ledger later. Interactive disclosure may enhance access but must not be the only carrier of a fact.

For a generic canvas, put complete evidence in one `data-evidence-ledger="1"` container. Each evidence entry declares a unique `data-evidence-id`, one status (`observed`, `inferred`, `proposed`, or `unresolved`), the semantic ids it supports through `data-evidence-for`, and an authored source kind plus source reference. Plain prose in the `evidence-and-notes` slot is a note, not a verifiable evidence ledger, and must not be used as the only evidence carrier.

Place that evidence ledger immediately after the title region and before the first diagram canvas. When the diagram also uses multiple line kinds, combine the line-style legend and node evidence-color legend into one compact reading guide instead of scattering separate legends around the page. When nodes expose mapped details, put one concise interaction hint in that same reading guide; never float the hint inside the SVG canvas. Keep the evidence portion to observed implementation, completed checks, and not-yet-verified claims. Keep detailed provenance in structured attributes and mapped node details instead of repeating it as a paragraph.

### G4 — Stable, collision-free visual encoding

Use each shape, line style, and color for one stable meaning. Color must never be the only signal. Keep connectors out of labels, anchor arrows to object edges, and use deliberate whitespace or a label mask where a route crosses text.

### G5 — Readability without unlimited shrinking

Keep essential text readable. When the viewport or complexity budget is exceeded, prefer reflow, scoped scrolling, or mapped overview/detail views. Show controls only when useful, but keep their size, pressed state, focus state, and status treatment consistent whenever they appear.

Use `data-diagram-controls-mode="overflow"` for a compact diagram where zoom is only a recovery aid. Use `data-diagram-controls-mode="persistent"` when user-controlled Fit, 75%, 90%, and 100% views are part of the intended viewer. In persistent mode, keep the controls visible whenever the stage is measurable, even when it already fits; manual percentages must still apply. In overflow mode, reveal controls only when the unscaled stage overflows. Re-evaluate both modes after container or viewport resize. Controls may be embedded beside the diagram title by using the shared title-region attributes; their absence must never remove the scroll fallback.

### G6 — Equivalent fallback across environments

Preserve the same core identities, directions, boundaries, ordering, and evidence on mobile, keyboard, touch, reduced-motion, no-JavaScript, print, and enhancement-failure paths. Avoid page-level horizontal overflow and do not replace the primary model with an unrelated summary.

### G7 — Complexity requires mapped decomposition

Apply the trusted family budget. When it is exceeded, produce explicitly mapped overview and detail artifacts. Do not conceal overload by hiding content, merging distinct identities, or reducing essential text below the reading floor.

### G8 — Self-evidencing single-file delivery

Keep the artifact self-contained, free of remote runtime dependencies, and traceable to its template identity. Run the formal linter before delivery and state static and runtime evidence separately.

## Layout, arrows, and collision control

Lay out the main path before secondary evidence. Keep arrows outside label boxes, route branches through explicit junctions, and avoid crossings through nodes. Prefer vertical scrolling on narrow screens; never solve density by shrinking essential text below readable size.

Use progressive detail: overview first, local evidence second, full ledger last. A large diagram may use internal navigation, but its default view must still expose the conclusion and primary path.

For graph fallbacks, repeat authored relation ids and their `data-from`, `data-to`, and `data-relation-kind` endpoints. A list of node names or a sentence that merely says “A to B” is not an equivalent directional fallback because its direction cannot be verified without parsing visible prose.

When the selected template supports node details, author one concise, language-matched title and summary on the primary node, then map that node through `data-detail-for` to one native `details[data-diagram-detail]` block. The node remains a real focusable link without JavaScript. With enhancement active, open the detail as a small anchored popover beside the selected node; clamp it to the viewport rather than turning it into a side inspector or full-width sheet. Closing it returns focus to the originating node. Detail content may contain paths and implementation evidence that would overload the primary canvas. Print must expose every detail block.

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
6. Confirm the final response contains an HTML artifact path or, in text-only mode, one complete HTML code block; Mermaid-only delivery is forbidden.
7. Return the artifact path plus only the brief context needed to use it.

Static direction checks establish authored structure and supported SVG coordinates only. When direction, grouping, responsive reflow, interaction, or control visibility is material to acceptance, also render the artifact at the declared desktop and narrow widths. Verify computed node bounding-box order follows `data-primary-direction`, arrows terminate at the authored target, groups occupy their declared regions, labels and routes do not collide, page-level horizontal overflow is absent, and zoom controls follow the declared mode: persistent controls remain available on a measurable desktop stage while overflow controls appear only when needed. Record those viewport sizes and observations as browser evidence; do not infer rendered acceptance from the template name or a passing linter.
