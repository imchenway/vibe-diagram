# Artifact Authoring Contract

This contract makes a product-manager-first, model-authored diagram auditable without dictating its content or composition.

## ArtifactManifest v1

Embed one JSON object in `script#vibe-diagram-manifest[type="application/json"]`:

```json
{
  "$schema": "vibe-diagram/artifact-manifest@1",
  "artifactId": "stable-kebab-case-id",
  "language": "zh-CN",
  "title": "图类型｜业务主题",
  "audience": ["product-manager"],
  "questions": [
    {
      "id": "question-id",
      "text": "The product question the primary view must answer",
      "priority": "critical",
      "answeredBy": ["visible-element-id"]
    }
  ],
  "criticalFacts": [
    {
      "id": "fact-id",
      "statement": "A business-readable, decision-relevant fact",
      "status": "observed",
      "visibleIn": ["visible-element-id"],
      "evidenceIds": ["evidence-id"]
    }
  ],
  "views": [
    {
      "id": "view-id",
      "family": "business-flow",
      "role": "primary",
      "elementId": "view-element-id"
    }
  ],
  "evidence": [
    {
      "id": "evidence-id",
      "status": "observed",
      "sourceKind": "source-code",
      "source": "A real source locator or supplied statement",
      "supports": ["fact-id"]
    }
  ],
  "extensions": {}
}
```

Allowed evidence states are `observed`, `inferred`, `proposed`, `unresolved`, and `verified`. Question priorities are `critical`, `important`, and `supporting`. View roles are `primary`, `supporting`, and `appendix`.

`audience` must contain `product-manager`; additional readers may be appended but cannot replace it. Phrase questions and critical facts in business language. Every question target and critical-fact target must be a real visible element id. Every evidence reference must resolve. Extra fields belong under `extensions`; they cannot override the core meanings. Do not add node arrays, edge arrays, ranks, lanes, or coordinates to the manifest.

## Semantic markers

Use these markers on the final authored elements:

| Marker | Meaning |
|---|---|
| `data-vd-view="view-id"` | One independently readable visual view. |
| `data-vd-family="family"` | The grammar used by that view. |
| `data-vd-view-role="primary|supporting|appendix"` | Its information priority. |
| `data-vd-node="semantic-role"` | A visible semantic object; the value describes its role without a global allowlist. |
| `data-vd-group="semantic-role"` | A visible boundary, lane, phase, or ownership region. |
| `data-vd-edge="relation-kind"` | A visible directed relation. |
| `data-from="element-id"`, `data-to="element-id"` | Existing endpoint ids for one relation. |
| `data-vd-edge-label="edge-id"` | The visible label for one edge element id. |
| `data-vd-critical` | A visible target that directly answers a critical question or fact. |
| `data-vd-detail-for="element-id"` | Authored detail for one semantic element. |

Additional family markers are allowed. Common useful markers are `data-vd-lifeline-for`, `data-vd-message-kind`, `data-vd-cardinality`, `data-vd-review-section`, `data-vd-matrix`, and `data-vd-prototype`.

Markers expose meaning to validation; they do not determine element tags, classes, shape, position, or count.

## Global shell

Keep the generated shell's title region, controls, audit output, style block, and runtime block. Replace the empty content and manifest arrays. The shell owns only:

- restrained light canvas, grid, type and shared visual tokens;
- a persistent `75% / 90% / 100% / fit` control group at the title's right;
- optional authored detail dialogs and focus restoration;
- print, reduced-motion, keyboard, and narrow-screen behavior;
- computed geometry inspection.

It does not own family layout. Use page-level vertical scrolling. A view may use local horizontal overflow only when the 75% readability floor cannot fit its natural width. Do not create a nested vertical scroller for the diagram.

## Product-manager-first information

The one visible `data-vd-summary` is the product entry: state the conclusion, change, or problem and its relevant business impact in natural language. Do not lead with repository, class, API, field, table, middleware, or error identifiers.

Treat these as reading responsibilities, not fixed regions or a required number of views:

1. the product entry explains why the artifact matters;
2. the primary view shows the real business roles, objects, actions, states, rules, decisions, exceptions, and outcomes that answer the current questions;
3. supporting views explain implementation relationships only when they materially improve the answer;
4. mapped details or appendices preserve exact source locations, identifiers, logs, fields, and long evidence.

Use business-first labels. A visible primary label says what an object or action means; an exact implementation name may follow in smaller or visually quieter text. If the exact name does not help the product decision, put it only in the mapped detail. For example, prefer `CRM 导入没有执行品牌匹配` with `CrmMaintenanceOrderImportService.resolveBrandCode` as secondary evidence, not the reverse.

Express evidence states in the artifact language while retaining the stable Manifest value. In Chinese, suitable visible meanings are `已确认事实`, `分析判断`, `拟议方案`, `待确认`, and `已验证`. Never use friendlier wording to strengthen the evidence state.

Critical elements must be visibly rendered in a primary view at load time. A target inside a closed `details`, unopened `dialog`, hidden candidate tab, or appendix does not satisfy critical coverage. Keep cause, difference, decision, and result copy concise enough to scan, but preserve full evidence in mapped details.

Cards are permitted as nodes, participants, entities, or boundaries. A set of cards without meaningful visible relationships is not a diagram.

The natural reading order is conclusion or problem → primary relationship → key decision or result → technical evidence. Do not encode it as a fixed DOM. Avoid terminal-style visual dominance, large code blocks on the primary canvas, `true/false` branch labels without business meaning, equal-weight card walls, and shrinking below the readable floor. Color may reinforce status but never carry status alone.

## Family outcome grammar

The machine-readable policy is `contracts/family-outcomes.json`. It verifies only recognizable visual grammar:

- flow: visible start and end, directed paths, labeled branches from decisions, and visible merge or terminal outcomes;
- sequence: separate participants, one lifeline per participant, ordered messages with real endpoints, and distinct message kinds;
- state: initial state, authored states, transitions, guards when applicable, and a terminal or explicitly cyclic lifecycle;
- data model: entities or stores, visible relations, and cardinality or data-movement meaning;
- architecture: real components/boundaries plus visible dependency, ownership, trust, or data relations;
- debugging: symptom/evidence, cause or unresolved hypothesis, impact, repair, and verification remain traceable;
- comparison: real row/column axes, visible fact values, differences, and conclusion without invented weights;
- page prototype: real controls and responsive states;
- code review: finding navigation or headings and visible current → scenario → repair reading order;
- technical design: one product-readable primary overview and only the supporting views the implementation question needs.

No family policy sets a maximum node count, a DOM skeleton, business wording, coordinate system, or required number of views.

## Product reading review

Close every detail and ignore visually secondary implementation identifiers. Use only the visible summary and primary view to answer each critical Manifest question. Confirm the current conclusion or target change, business impact, applicable rules or branches, decision or next action, acceptance meaning, and unresolved items when those concepts matter to the request. Then verify that exact technical evidence remains traceable from the corresponding fact. Record `product-reading-reviewed` only when both conditions pass; lint and browser geometry cannot establish it.
