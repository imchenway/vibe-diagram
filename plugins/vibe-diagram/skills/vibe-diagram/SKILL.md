---
name: vibe-diagram
description: Create and deliver a product-manager-first, self-contained HTML visual artifact when the user asks to draw or when architecture, workflow, sequence, state, data, debugging, code-review, or technical-design relationships materially need a diagram; ordinary explanations stay textual unless a diagram is requested, and Mermaid alone never completes the request.
---

# Vibe Diagram

The model owns fact selection, business meaning, topology and authored HTML/SVG. Shared code measures and lays out marked SVG, checks results, and supplies reading, comparison and export. Never invent facts to complete a picture.

## 执行

1. 从当前 Skill 目录运行 `python3 <skill-root>/scripts/update_skill.py --check-and-update --json`。offline 或 failed 时沿用已安装内容并简短说明；明确手动更新才加 `--force-check`，不绕过完整性检查。
2. 通读 [运行步骤](references/runtime-workflow.md) 和 [作者契约](references/artifact-authoring.md)，按需加载 at most two 基础图法。同一内容仍在当前上下文中时直接复用；更新、内容变化或必要规则已不在上下文中时补读，不重复搜索有效标准参考。
3. 从当前任务最新文档、证据位置和已有图稿定位事实，核对本次变化与证据适用范围，确定产品问题、业务含义、关键事实和证据状态。
4. 新图创建空外壳；重画从仍适用的图稿工作副本增量修改。使用共享排版，复杂边界直接编排；集中修正候选问题，完成阅读和交互检查后立即交付 HTML。

流程按业务动作、判断、分支、汇合与结果组织，不按日志顺序罗列。先使用紧凑的通用流程符号、对齐的直连主线与侧方例外；方向和分区服从业务关系。具体规则见流程图指导。

## 只选必要的图法

- 业务能力、系统职责、依赖、因果、数据流转：[架构关系图](references/archetypes/architecture.md)
- 步骤、判断、泳道、异常和补偿：[流程图](references/archetypes/basic-flow.md)
- 同步、异步、重试、回调和超时：[时序图](references/archetypes/code-sequence.md)
- 生命周期与转换：[状态图](references/archetypes/state-machine.md)
- 实体、字段与数量关系：[数据关系图](references/archetypes/er-data-flow.md)。用户要求完整数据库表结构或数据库 UML 样式时，必须读取其中的表结构布局规则，直接展示表名注释、字段同行注释、右对齐类型、键字段分区和独立索引区。

故障、代码审查、技术设计按作者契约组织上述图法，不再选择独立场景模板。不生成独立比较表或页面原型；图形修改前后的差异对比仍保留。

## 交付底线

- 主要读者始终是产品经理；无需读代码或点开详情即可理解结论、影响与关键规则，准确技术证据另有映射。
- 普通解释保持文字；用户要求画图时，Mermaid、文字报告或卡片清单不能代替可交付 HTML。
- 默认提供一个最合适的产物；只有用户明确探索方案才使用并列候选。
- 默认只交付自包含 HTML，保留页面内的 SVG 绘图。除非用户另行明确要求图片，否则不调用生图工具，不生成或导出 PNG 等图片、独立 SVG 文件或图片预览，也不为图片交付额外添加或点击导出控件。
- 事实与关系不能为通过检查而删减；图标题、文字、按钮和证据状态跟随用户语言。
- 明确要求 UML、BPMN 等标准时，只有具备严格的 canonical 标准参考才使用，否则说明无法按该标准交付。
- 静态通过、浏览器检查、产品阅读、真实客户端验证各自独立；失败的修改不替换旧文件。
