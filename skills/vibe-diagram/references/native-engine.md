# 原生生成入口

图形默认通过 `scripts/vibe_diagram_build.py`，调用技能包内固定的 Archify 2.16.0 编译器和完整查看器。无需 npm 安装或网络。生成需要 Python 3.10+、Node.js 18+；已生成的 HTML 完全自包含。

## 输入与能力边界

| 基础图法 | 图形来源 | 布局由谁确定 |
|---|---|---|
| 架构关系 `architecture` | `diagram_type: architecture`，components / connections；纯数据流也可选 dataflow 的 nodes / flows | 作者给组件 pos/size 与边界，原生几何引擎计算端口和路线并检查 |
| 流程 `business-flow` | `diagram_type: workflow`，nodes / edges | 作者给真实泳道和逻辑列；编译器计算分层、避障、分支与回路 |
| 时序 `code-sequence` | `diagram_type: sequence`，participants / messages | 作者给参与者顺序与消息 y；引擎生成生命线、消息和执行条 |
| 状态 `state-machine` | `diagram_type: lifecycle`，states / transitions | 作者给 lane / col 及明确转换，引擎安排图类空间与路线 |
| 数据关系 `data-model` | 带语义标记的独立 SVG | 作者安排实体、字段和数量关系，共用查看器和几何检查 |

先按图类读取 `assets/archify/schemas/<图类>.schema.json`，公共枚举按需读取 `common.schema.json`。workflow 支持自己的输入版本；其他格式不要凭印象混用字段。每个节点和关系都必须有稳定 id。不要使用 docs 样例、另一安装目录或退役的通用模板编译器作为运行依赖。

每份原生图声明一个主要视图。多个阅读重点使用 `meta.views`，每个章节声明 `{id, label, focus: [节点id], note}`；这些编号选择同一张图中的对象，不复制图形结构。图类不同且都不可省略时分别生成 HTML，并在交付说明中关联。

## 最小原生流程示意

以下仅说明输入格式，业务节点必须随真实需求重新确定，不能当作固定模板套用。

```json
{
  "schema_version": 2,
  "diagram_type": "workflow",
  "meta": {
    "title": "流程图｜请求处理",
    "subtitle": "示例设定：收到请求后进行处理，完成后返回结果。",
    "locale": "zh-CN",
    "animation": "trace",
    "visual_preset": "signal-flow"
  },
  "lanes": [{"id": "main", "label": "业务办理"}],
  "phases": [],
  "groups": [],
  "mainPath": ["start", "process", "done"],
  "nodes": [
    {"id": "start", "lane": "main", "col": 0, "type": "external", "label": "收到请求", "width": 140},
    {"id": "process", "lane": "main", "col": 1, "type": "backend", "label": "处理请求", "width": 140},
    {"id": "done", "lane": "main", "col": 2, "type": "external", "label": "返回结果", "width": 140}
  ],
  "edges": [
    {"id": "accept", "from": "start", "to": "process", "label": "开始处理"},
    {"id": "finish", "from": "process", "to": "done", "label": "处理完成"}
  ]
}
```

配套清单按 [作者契约](artifact-authoring.md) 编写，标题和 language 必须与 meta 完全一致。`views` 只声明一个主要视图；清单不保存节点、连线、坐标或泳道数组。此例 family 为 business-flow，`extensions.nodeRoles` 为 `{"start":"start","done":"end"}`，未标注节点默认为 activity。判断必须显式标 decision，且每个出口有真实条件标签。原生编译后节点 DOM id 是 `node-<节点id>`；固定标题与摘要 id 为 `diagram-title` / `diagram-summary`，可用于关键事实覆盖。

```sh
python3 <skill-root>/scripts/vibe_diagram_build.py --input <diagram.json> --manifest <coverage.json> --output <new-draft.html>
```

时序中 return 代表返回、dashed 代表异步，其余默认同步；security 是视觉分类，不能据此认定错误。特殊消息明确写入清单 `extensions.messageKinds`，例如 `{"timed-out":"timeout","retry":"self"}`，同时在可见文字中说明。状态图的 `extensions.nodeRoles` 指定 initial / state / terminal / cyclic，每条 transitions 必须显式写 id 和 label；排列相邻不自动产生转换。

## 作者 SVG

实体图或原生图类确实无法准确表达的组合使用：

```sh
python3 <skill-root>/scripts/vibe_diagram_build.py --svg <diagram.svg> --manifest <coverage.json> --summary '<产品结论与规则>' --output <new-draft.html>
```

SVG 须有 `xmlns="http://www.w3.org/2000/svg"`、有限且正面积的 viewBox，样式嵌在 SVG 内，优先引用原主题 `--vd-*` 变量。节点 `<g id="customer" data-vd-node="entity">` 内含真实轮廓 `data-vd-shape` 和可见业务主标签。关系使用一条完整几何，例如 `<path id="owns" data-vd-edge="owns" data-from="customer" data-to="booking" data-vd-cardinality="1:0..N" d="…"/>`；对应文字 `<text id="owns-label" data-vd-edge-label="owns">一位客户可有零至多份预约</text>`。id 不能使用查看器保留的 `vibe-canvas-` 前缀。

清单 coverage 直接引用作者 SVG 的稳定 DOM id。`extensions.guidedViews` 可声明与原生 meta.views 相同的章节。引擎为 SVG 绑定查找、焦点、路径、动效、地图和导出，不改写其关系或猜测字段含义。

## 交互、导出与检查

默认沿用原主题背景和网格，完整查看器提供名称查找、节点和关系聚焦、上下游、最短有向路径、地图、类型筛选、章节、镜头跟随、演示与流程线条动效。路径表示图中关系，不是已执行流程或耗时分析。

导出菜单包含完整 SVG / PNG / JPEG / WebP、全图或选定路径及上下游分享图、交互 HTML；浏览器支持时还有复制图片和 WebM 视频。完整 HTML 保留代码许可、覆盖清单、折叠证据及全部交互。图片包含图形、标题和摘要，分享卡明确保留所选范围。减少动效和后台保留静态图；视频编码成功、前台动画实际推进和剪贴板权限必须分别实测，不得仅凭按钮存在宣称通过。

生成时依次检查固定引擎摘要、输入格式、原生布局、编译前后的对象与关系数量、语义标记、关键事实及自包含性；失败不写输出。不得关闭质量门禁、按布局便利删除条件或覆盖旧图。准备、浏览器检查和交付步骤见 [运行步骤](runtime-workflow.md)。

采用固定源码的优势是可离线、可审查、跨客户端分发一致；代价是包体积增加，升级上游时必须核对接入点、许可、摘要及真实产物。上游源码保持原样，兼容适配只在 `scripts/vibe_diagram_native.py` 和 `assets/native/` 中维护；不要复制独立业务预览脚本。
