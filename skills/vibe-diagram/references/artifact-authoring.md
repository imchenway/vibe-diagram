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

Additional family markers are allowed. Common useful markers are `data-vd-lifeline-for`, `data-vd-activation-for`, `data-vd-message-kind`, `data-vd-cardinality`, and `data-vd-review-section`.

通常标记不限制标签、形状和数量。明确选择自动排版的 SVG 采用下方最小结构要求；其余复杂组合仍直接编排。

## Global shell

Keep the generated shell's title region, controls, audit output, style block, and runtime block. Replace the empty content and manifest arrays. The shell owns only:

- restrained light canvas, grid, type and shared visual tokens;
- a persistent `75% / 90% / 100% / fit` control group at the title's right;
- optional node-anchored non-modal detail popovers and focus restoration;
- print, reduced-motion, keyboard, and narrow-screen behavior;
- computed geometry inspection, optional measured layout, direct-relation highlighting, stable-identity comparison and complete-view SVG/PNG export.

自动排版按下节约定读取现有 SVG 标记。Use page-level vertical scrolling. A view may use local horizontal overflow only when the 75% readability floor cannot fit its natural width. Do not create a nested vertical scroller for the diagram.

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
- data model: independent entities with visible cardinality; data movement belongs to architecture;
- architecture: real components/boundaries plus visible dependency, ownership, trust, or data relations;

No family policy sets a maximum node count, a DOM skeleton, business wording, coordinate system, or required number of views.

## Product reading review

Close every detail and ignore visually secondary implementation identifiers. Use only the visible summary and primary view to answer each critical Manifest question. Confirm the current conclusion or target change, business impact, applicable rules or branches, decision or next action, acceptance meaning, and unresolved items when those concepts matter to the request. Then verify that exact technical evidence remains traceable from the corresponding fact. Record `product-reading-reviewed` only when both conditions pass; lint and browser geometry cannot establish it.

同时查看真实页面截图与 `receipt().readingMetrics`，核对节点留白、主线与侧支、页面长度及重复内容。页面高或图数多本身不是错误；但把相同链路逐例复制、窄图占满宽屏、用阶段切片维持流水账，都需要重新构图。按真实问题选择共用视图、差异标注或独立视图，不规定统一图数、方向或坐标。小样例和几何检查不能代替当前真实需求的阅读。

## 共享排版、阅读与导出

默认对五种基础图法使用 `svg[data-vd-layout="auto"][data-vd-zoom-target]`，外套 `data-vd-viewport`。SVG 内直接放置作者确定的节点 `<g id="…" data-vd-node="…">`、连线 `<path id="…" data-vd-edge="…" data-from="…" data-to="…">` 与有编号的 `<text data-vd-edge-label="连线编号">`，所有文字在字体载入后测量。节点内用 `data-vd-shape` 标记一个 rect、ellipse 或决策 polygon；文本可用 tspan 分行。程序按实际文字加内边距收紧形状，不继承草稿的大框，不缩字或删文案。确需为内容保留空间时在节点显式声明 `data-vd-min-width`、`data-vd-min-height`；大段说明应移至映射详情。

流程默认横向，其他非时序图默认纵向；SVG 上 `data-vd-direction="right|down"` 可明确主方向，时序仍按消息顺序。中心对齐的相邻节点优先直连，分支、回路或障碍才需要折线。图标仅作辅助且通常为 16–20 像素，不代替流程符号。连线 marker 的形状、含义和证据由作者保留；普通箭头使用 `markerUnits="userSpaceOnUse"`、`markerWidth="8"`、`markerHeight="8"`、`viewBox="0 0 10 10"`、`refX="10"`、`refY="5"`、`orient="auto-start-reverse"`，箭头尖端与路径终点重合，不随线宽放大。数据关系和时序的专用符号保留自身语义。

单层边界用同级 `<g id="边界编号" data-vd-group="职责"><rect/><text>业务职责</text></g>`，节点用 `data-vd-member-of="边界编号"` 表明归属。时序消息使用已有 `data-vd-message-kind`，每个参与者有 `line[data-vd-lifeline-for="参与者编号"]`；消息 DOM 顺序即时间顺序，返回、异步、错误和超时仍需可见区别。手工绘制的执行条使用 `data-vd-activation-for="参与者编号"`，处于该执行区间的消息连接执行条真实边缘，不补造执行时段。`data-vd-gap` 可增大留白。

需要解释关系或证据状态时，把短图例放在本图 SVG 左上角，不用独立的阅读指南段落、卡片或边框。写成 `<g data-vd-legend><g data-vd-legend-for="本图真实元素编号"><text>实际业务含义</text></g></g>`；共享代码从引用元素复制真实色样和线型，并为自动图安排位置。手工图为外层图例组预留位置。图族和证据决定图例项目，不把所有图固定为三种状态。不同关系笔触缺少图内图例会使浏览器检查失败。执行过与未执行过通常是关系状态，无真实职责边界时不要为颜色另造泳道。

详情沿用 `dialog[data-vd-detail-for]` 和稳定触发编号，由共享代码显示为节点旁的非模态小浮层。保留关闭、外部点击、Esc、键盘焦点返回、节点深链接、无脚本来源和打印；不要调用 showModal 或模糊整张图来显示节点详情。窄屏浮层可占可用宽度，不能移到画面外。

复杂嵌套边界、时序片段或自由形状直接编排并保留同样的检查，不强行转成统一卡片。自动布局失败会恢复原 SVG 并明确报错，不能带着失败状态交付。该边界的优势是共用排版而不另建图描述协议；代价是高密度图仍可能需要分图和人工安排。

节点支持点击、Enter、空格高亮当前图的直接关联；Esc 或取消高亮恢复全图。已有详情与原生控件维持其操作。图片按视图导出，清除临时高亮，附带标题、摘要和 `data-vd-export-note` 图注；图片不代替 HTML 里的交互证据。需要图片的视图应只包含一幅 SVG、视图标题和声明的图注，不能把必要图例放到未声明的旁边。

混排表格、原型、多个 SVG、HTML 控件等无法完整转成单幅 SVG 时只提供整页打印，不能静默导出局部。PNG 使用浏览器原生画布并限制总像素，大图使用 SVG 或分图。无需第三方运行依赖。

## 场景内容审核

场景容器使用有编号的 `data-vd-task`，内容用可见的 `data-vd-task-section` 标记；它们可包含多种基础图法，不固定图数或坐标。

- `fault-debugging`：symptom、impact、cause 或 hypothesis、repair、verification，假设与已确认原因必须区分。
- `code-review`：每条发现一个容器，依次显示 current、scenario、repair、acceptance；场景必须是真实触发过程，不能只写泛泛风险。
- `technical-design`：change、boundary、decision、acceptance；按问题补充必要的基础视图。

场景容器检查能发现内容遗漏，不能证明事实或业务判断正确。没有把属性标上就视作验证通过的捷径。
