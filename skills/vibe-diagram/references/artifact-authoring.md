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

原生编译入口自动在最终 SVG 绑定这些标记；作者 SVG 和原生 HTML 则直接标注。覆盖清单中的节点目标使用 `node-<原生节点id>`，作者 SVG 使用自己的 DOM id；标题和摘要分别是 `diagram-title`、`diagram-summary`。

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

标记不限制业务文字或数量。原生编译器生成一次最终几何；直接编写的 SVG 保留作者几何，两者都使用同一个完整查看器。

## Global shell

保留用户确定的渐变背景、二十四像素方格、系统字体、配色和留白。图形调用完整原生查看器，公共层只负责主题、覆盖检查、差异与交付；不能再写一套简化的阅读、动效或导出逻辑。表格与页面原型继续使用公共 HTML 外壳的缩放、详情、打印和 HTML 下载。

图形支持名称查找、关联对象、上下游、路径、地图、筛选、章节、镜头、演示、流程线条动效及导出。一个原生文件声明一个主要图形视图，多条阅读路线用章节，不增加同义模板。问题确实需要多种图法时可以交付多份互相关联的 HTML；不要为了合成一幅图混淆时序、结构与实体含义。

新增能力不构成重新设计视觉的理由。不得使用不透明大底色遮住公共背景，不通过更换主题预设制造所谓新图类型。默认原主题；只有用户明确要求时才切换视觉。使用页面级纵向滚动；窄屏保持自然比例并在图内横向滚动。镜头缩放、地图总览是读者主动操作，不作为把复杂图压小的交付捷径。

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
- comparison: real row/column axes, visible fact values, differences, and conclusion without invented weights;
- page prototype: real controls and responsive states;

No family policy sets a maximum node count, a DOM skeleton, business wording, coordinate system, or required number of views.

## Product reading review

Close every detail and ignore visually secondary implementation identifiers. Use only the visible summary and primary view to answer each critical Manifest question. Confirm the current conclusion or target change, business impact, applicable rules or branches, decision or next action, acceptance meaning, and unresolved items when those concepts matter to the request. Then verify that exact technical evidence remains traceable from the corresponding fact. Record `product-reading-reviewed` only when both conditions pass; lint and browser geometry cannot establish it.

## 原生生成、阅读与导出

运行格式与命令见 [原生生成入口](native-engine.md)。架构、流程、时序、生命周期各使用自己的原生格式，不重新建立通用模板协议。流程编译器处理分层、端口与回路；其他图类使用各自的坐标、列、泳道或消息纵坐标与走线规则，不能笼统声称所有类型都有完全自动布局。

复杂图与实体关系采用有标准命名空间、有效 viewBox 的 SVG。节点必须有稳定 id、`data-vd-node`、一个 `data-vd-shape` 实际轮廓和可见主标签；每条关系必须有稳定 id、一条完整 path/line/polyline、真实 `data-from`/`data-to`，标签单独引用该关系 id。实体关系还须有 `data-vd-cardinality` 和可见数量含义。SVG 内嵌样式使用原主题变量；不嵌脚本、外部资源或 foreignObject。图形结构和字段只写这一份，清单不复制节点数组。

节点与关系沿原生入口聚焦；路径是按已有有向关系找到的最少连线数路线，不能说成所有路径、真实执行轨迹或业务耗时。章节显式选择阅读对象和讲解文字；播放、镜头和流动标记用于解释图中关系，后台及减少动效时保留静态内容。关系热区和动效克隆不携带业务检查身份，避免被当成新增关系。生命周期只保留作者明列的转换，不根据排列顺序补出转换。

普通图片导出完整 SVG、PNG、JPEG、WebP，保留原主题、标题、摘要和图内标签图例，清除临时选择。分享图可以明确选择全图、路径或上下游范围；不能把局部图冒充全图。视频和剪贴板沿用原生入口，受浏览器编码、前台状态及权限约束；能力存在不等于已经在真实客户端验证。图片不包含折叠证据卡中的完整正文，需要完整交互时下载 HTML。下载文件保存初始化前正文，重开不能重复添加控件。

技术证据以清单保留准确来源，原生 `cards` 可承载本地文字说明，节点与关系使用稳定编号关联；关键事实仍须在主要图和摘要中可见。绘图命令不访问 Git 或抓取远程品牌标志。包内代码来源、逐文件摘要和 MIT 许可见 `assets/archify/source.json` 与 `assets/archify/LICENSE`；上游代码原样固定，主题和标记适配位于目录之外。

收益是五类图共享完整且可分发的交互能力，不依赖一次性样例；代价是技能包增大、生成阶段需要 Node.js，复杂图仍需要作者安排空间并检查。已有 HTML 阅读无需 Python 或 Node。

## 场景内容审核

场景容器使用有编号的 `data-vd-task`，内容用可见的 `data-vd-task-section` 标记；它们可包含多种基础图法，不固定图数或坐标。

- `fault-debugging`：symptom、impact、cause 或 hypothesis、repair、verification，假设与已确认原因必须区分。
- `code-review`：每条发现一个容器，依次显示 current、scenario、repair、acceptance；场景必须是真实触发过程，不能只写泛泛风险。
- `technical-design`：change、boundary、decision、acceptance；按问题补充必要的基础视图。
- `comparison-matrix`：原生 `table[data-vd-matrix]`，条件和候选形成两条轴，关键差异 `data-vd-difference` 与结论 `data-vd-conclusion` 可见，不编造评分。
- `page-prototype`：真实 HTML 控件，`data-vd-prototype` 与 `data-vd-responsive-state`；空、加载、失败、权限与成功状态按需求可见或可达。

场景容器检查能发现内容遗漏，不能证明事实或业务判断正确。没有把属性标上就视作验证通过的捷径。
