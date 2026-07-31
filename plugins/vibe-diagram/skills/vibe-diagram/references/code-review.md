# Code Review Reference

## Purpose

Use the code-review package when multiple review findings must be explained without losing the distinction between observed behavior, a factual failure scenario, and a proposed repair. The package is a single self-contained HTML artifact. It has one title-side control region, one vertical finding rail, and one three-part reader. The current and repair canvases each own a local two-row legend.

## Template

- `../assets/templates/code-review/code-review-package.html`: the only code-review package template. It routes each finding to a relation-specific reusable topology while preserving one package shell.

Create it with a structured specification:

`python3 <skill-root>/scripts/vibe_diagram_scaffold.py --type code-review --template code-review-package --review-spec <spec.json> --standard native --output <artifact.html>`

The scaffold also accepts repeatable `--review-kind <kind>` arguments for a neutral draft. A code-review request without a resolved kind or specification fails closed.

## Relation routing

Select the kind from the primary relationship the reader must understand:

| Kind | Routed topology | Use when |
|---|---|---|
| `control-branch` | `business-flow/logic-flowchart` | a condition, branch, merge, or bounded decision loop is primary |
| `exception-compensation` | `business-flow/exception-branch-flow` | failure, compensation, retry, fallback, or rejoin is primary |
| `time-concurrency` | `code-sequence/async-callback-sequence` | time ordering, lock ownership, concurrency, lease, or transaction interleaving is primary |
| `state-lifecycle` | `state-data-model/state-machine` | durable state, lifecycle, retry limit, cutoff, or terminal state is primary |
| `path-contract-drift` | `business-flow/dual-path-swimlane` | two implementation paths, contract drift, artifact drift, or a missing handoff is primary |
| `cause-evidence` | `fault-debugging/causal-chain` | evidence, cause, impact, remediation, and verification are primary |
| `architecture-boundary` | `system-architecture/component-breakdown` | module dependency, ownership boundary, or responsibility placement is primary |

Do not route by severity, programming language, repository, filename, or reviewer identity. Split a finding when two independent primary relationships would require different topologies. Ask for confirmation when the primary relation remains ambiguous.

## Paired-view invariant

Choose the route once per finding. The current-and-risk view and proposed-repair view must reuse the same family, template, node count, relation count, node-role sequence, relation-kind sequence, and path geometry. Only authored labels, details, evidence, and state meaning may differ.

This invariant makes the repair visually comparable to the observed problem. A generated artifact that changes topology between the two views is invalid even when both individual diagrams would be valid alone.

## Shell and interaction

- Use the page-title form `Code review｜title description`, localized to the authored output language.
- Put the shared percentage controls in the page title's right-side `data-artifact-shell-controls` region. Do not place operating instructions above the buttons or recreate the controls with package-local markup.
- Put finding navigation in a vertical left rail beside the reader. Keep one finding per row with a stable severity badge, aligned title, visible selected state, and keyboard tablist behavior.
- Put the selected finding in the right reader as three consecutive regions: current-state diagram, factual failure scenario, and proposed-repair diagram. Both diagrams use the full reader width and remain visible without a view-switch tab.
- Author the factual scenario as `title`, `trigger`, `process`, and `impact`. These values must come from review evidence and must not be inferred by runtime code from severity, repository, or topology.
- Give the current and repair canvases separate local two-row legends at their own grid top-left. Each legend contains only relation and evidence groups, has no independent heading or card, and resolves through `data-reading-guide-for` to its owning canvas. Route swatches must match the package's blue main path, red risk or mismatch path, amber compensation or cutoff path, and violet dashed feedback or retry path. Evidence swatches must reuse the actual blue-outline observed node, green completed-check node, and amber not-yet-verified node tokens.
- Treat the exact two groups and three evidence states above as a code-review family contract. The shared artifact shell owns only placement, ownership, structural validity, and token reuse; it must not make this review vocabulary mandatory for unrelated diagram families.
- Keep one shared persistent percentage control group in the title control region. Reuse the canonical button, pressed-state, focus-state, status, and 75% minimum contracts. One requested percentage applies to both canvases, while each canvas computes fit against its own available width and falls back to scoped horizontal scrolling below the floor.
- Let each current and repair canvas grow to its natural block height and let the page own vertical scrolling. A review canvas must not set a viewport-bound maximum height or expose a vertical scrollbar; it may own horizontal scrolling only when the readable 75% floor cannot fit.
- Keep every finding, both diagrams, and the factual scenario expanded in the no-JavaScript and print fallback.
- Do not use iframes, child HTML files, remote resources, or runtime-generated business semantics.

The left rail preserves a stable review inventory while the right reader gives each diagram enough width for readable node copy and elbow routes. The three-part order makes the evidence-backed incident easy to connect to both the observed implementation and the repair. Its costs are a narrower reader on desktop and greater vertical page height; narrow screens therefore move the finding list above the reader.

For `time-concurrency`, render independent participant header nodes before lifelines and message events. Each participant requires a stable `data-participant-id`; empty header bands or inferred actors are invalid. For path-drift routes, keep route labels in dedicated whitespace or use a text mask so labels never cover merge or outcome nodes. Every orthogonal bend needs a visible turn channel; do not create short hidden elbows between a node edge and the next long segment.

Keep the full `graph-level title` in metadata and accessible labels for routing evidence. In the visible diagram heading, remove the `diagram type｜` prefix and show only the business subject because the package already records the selected topology.

## Specification boundary

The specification owns the authored language tag, page title, summary, every visible or announced guide and control label, evidence sources, finding id, severity, finding title, finding summary, route kind, factual scenario fields, participant labels for time-concurrency findings, node labels, node details, and relation labels. The scaffold owns topology geometry, responsive behavior, finding-tab behavior, paired zoom behavior, accessibility states, and fallback rendering. Populate the language and shell labels explicitly so a non-English artifact does not inherit English source defaults.

Each route has a fixed node and relation capacity. If the verified model does not fit, split the finding instead of truncating evidence, merging unrelated nodes, or changing only one side of the pair.

Static linting proves the route, pair invariant, participant inventory, endpoint integrity, minimum bend clearance, shell and three-part reader order, single-file boundary, and fallback presence. Browser geometry and real client lifecycle remain separate evidence.
