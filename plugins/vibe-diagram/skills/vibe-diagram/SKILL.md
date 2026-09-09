---
name: vibe-diagram
description: Create and deliver a product-manager-first, self-contained HTML visual artifact when the user asks to draw or when architecture, workflow, sequence, state, data, debugging, code-review, or technical-design relationships materially need a diagram; ordinary explanations stay textual unless a diagram is requested, and Mermaid alone never completes the request.
---

# Vibe Diagram

The model owns fact selection, business meaning and relationships. The packaged native engine compiles the selected diagram source and supplies the full viewer; authored SVG uses that same viewer. Never invent facts to complete a picture.

## 执行

1. 从当前 Skill 目录运行 `python3 <skill-root>/scripts/update_skill.py --check-and-update --json`。offline 或 failed 时沿用已安装内容并简短说明；明确手动更新才加 `--force-check`，不绕过完整性检查。
2. 通读 [运行步骤](references/runtime-workflow.md) 和 [作者契约](references/artifact-authoring.md)。按需加载 at most two 基础图法。
3. 检查用户的真实证据，先确定产品问题、业务含义、关键事实和证据状态。
4. 图形按 [原生生成入口](references/native-engine.md) 编写图类源或 SVG，运行 `vibe_diagram_build.py`。检查独立候选、产品阅读和交互后再交付。

## 只选必要的图法

- 业务能力、系统职责、依赖、因果、数据流转：[架构关系图](references/archetypes/architecture.md)
- 步骤、判断、泳道、异常和补偿：[流程图](references/archetypes/basic-flow.md)
- 同步、异步、重试、回调和超时：[时序图](references/archetypes/code-sequence.md)
- 生命周期与转换：[状态图](references/archetypes/state-machine.md)
- 实体、字段与数量关系：[数据关系图](references/archetypes/er-data-flow.md)

故障、代码审查、技术设计按作者契约组织上述图法，不再选择独立场景模板。

## 共同能力

五种图法共享原生查找、关系聚焦、上下游、两点路径、地图、章节讲解、镜头、流程动效和演示；导出支持 SVG、PNG、JPEG、WebP、分享图、交互 HTML，以及浏览器支持时的视频与复制。保留原有背景、渐变、格子、配色和系统字体，不增加场景模板。生成需要 Python 3.10+ 和 Node.js 18+；无需联网安装依赖，生成的 HTML 可离线打开。

## 交付底线

- 主要读者始终是产品经理；无需读代码或点开详情即可理解结论、影响与关键规则，准确技术证据另有映射。
- 普通解释保持文字；用户要求画图时，Mermaid、文字报告或卡片清单不能代替可交付 HTML。
- 默认提供一个最合适的产物；只有用户明确探索方案才使用并列候选。
- 事实与关系不能为通过检查而删减；图标题、文字、按钮和证据状态跟随用户语言。
- 明确要求 UML、BPMN 等标准时，只有具备严格的 canonical 标准参考才使用，否则说明无法按该标准交付。
- 静态通过、浏览器检查、产品阅读、真实客户端验证各自独立；失败的修改不替换旧文件。
