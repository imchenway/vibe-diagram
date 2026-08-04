# Vibe Diagram

`vibe-diagram` 是一个可移植的 Agent Skill，可根据代码、文档和需求生成自包含的单文件 HTML 图，适用于架构图、流程图、时序图、状态图和技术设计等场景。

## 安装

### Codex

在 Codex 中发送：

```text
使用 $skill-installer 安装 https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram
```

安装完成后，新建 Codex 任务并说明要画的内容即可。

### TRAE

以用户级全局方式安装一次，所有项目均可使用，无需在每个项目中重复安装。安装前请确保已有 Node.js 18+，并且可通过 `python3` 命令运行 Python 3。

TRAE 国际版：

```bash
npx --yes skills@latest add https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram --skill vibe-diagram --agent trae --global --copy --yes
```

TRAE 中国版：

```bash
npx --yes skills@latest add https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram --skill vibe-diagram --agent trae-cn --global --copy --yes
```

命令会复制完整 Skill，包括脚本、参考资料、校验规则和模板。安装完成后，新建 TRAE 对话并明确要求使用 `vibe-diagram` 即可。
