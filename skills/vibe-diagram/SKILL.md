---
name: vibe-diagram
description: Create and deliver a product-manager-first, self-contained HTML visual artifact when the user asks to draw or when architecture, workflow, sequence, state, data, debugging, code-review, technical-design, comparison, or page-prototype relationships materially need a diagram; ordinary explanations stay textual unless a diagram is requested, and Mermaid alone never completes the request.
---

# Vibe Diagram

The model owns fact selection, business meaning, topology and authored HTML/SVG. Shared code measures and lays out marked SVG, checks results, and supplies reading, comparison and export. Never invent facts to complete a picture.

## 执行

1. 从当前 Skill 目录运行 `python3 <skill-root>/scripts/update_skill.py --check-and-update --json`。offline 或 failed 时沿用已安装内容并简短说明；明确手动更新才加 `--force-check`，不绕过完整性检查。
2. 通读 [运行步骤](references/runtime-workflow.md) 和 [作者契约](references/artifact-authoring.md)。按需加载 at most two 基础图法。
3. 检查用户的真实证据，先确定产品问题、业务含义、关键事实和证据状态。
4. 从空外壳编写最终 HTML/SVG；使用共享排版，复杂边界直接编排。检查独立候选、阅读和交互后再交付。

## 只选必要的图法

- 业务能力、系统职责、依赖、因果、数据流转：[架构关系图](references/archetypes/architecture.md)
- 步骤、判断、泳道、异常和补偿：[流程图](references/archetypes/basic-flow.md)
- 同步、异步、重试、回调和超时：[时序图](references/archetypes/code-sequence.md)
- 生命周期与转换：[状态图](references/archetypes/state-machine.md)
- 实体、字段与数量关系：[数据关系图](references/archetypes/er-data-flow.md)

比较表和页面原型直接使用 HTML 表格、真实控件。故障、代码审查、技术设计按作者契约组织上述图法，不再选择独立场景模板。

## 交付底线

- 主要读者始终是产品经理；无需读代码或点开详情即可理解结论、影响与关键规则，准确技术证据另有映射。
- 普通解释保持文字；用户要求画图时，Mermaid、文字报告或卡片清单不能代替可交付 HTML。
- 默认提供一个最合适的产物；只有用户明确探索方案才使用并列候选。
- 事实与关系不能为通过检查而删减；图标题、文字、按钮和证据状态跟随用户语言。
- 明确要求 UML、BPMN 等标准时，只有具备严格的 canonical 标准参考才使用，否则说明无法按该标准交付。
- 静态通过、浏览器检查、产品阅读、真实客户端验证各自独立；失败的修改不替换旧文件。
