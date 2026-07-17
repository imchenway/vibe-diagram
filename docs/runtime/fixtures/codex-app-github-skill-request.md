# Codex App GitHub skill smoke 请求

使用本次新执行已安装并注入的 `$vibe-diagram` skill，生成一个简体中文、单文件、自包含的 delivery-acceptance HTML：

`docs/runtime/outputs/codex-app-github-skill-smoke.html`

必须遵守以下约束：

1. 读取当前仓库的 `AGENTS.md`、`CONTEXT.md`、所有适用 ADR，以及已安装 skill 的 `references/delivery-acceptance.md`。
2. 从已安装 skill 的 `assets/templates/delivery-acceptance/acceptance-ledger.html` 复制骨架，保留 `data-diagram-type`、`data-template-family`、`data-template-id`、`data-template-layout` 和 ledger slots。
3. 只呈现以下已观测事实：
   - 系统 `skill-installer` 使用 `https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.1/skills/vibe-diagram` 成功安装 `vibe-diagram`；
   - 安装位置为 `<codex-home>/skills/vibe-diagram`，其中 `<codex-home>` 是本机 Codex home 的公开占位符；
   - 安装树与当前仓库 `skills/vibe-diagram/` 逐文件一致，且当前仓库 canonical skill 与 `v0.1.0-rc.1` 标签无差异；
   - 新执行实际发现并调用的 skill 标识必须在最终回复中报告；若未发现 native `vibe-diagram` skill，不得生成伪造的通过结论。
4. 升级和 Codex App UI 确认必须标记为 `Unverified`，不得写成已完成。
5. 不得加载远程 CSS、JavaScript、字体或图片；不要修改任何其他文件。
6. 不得输出本机用户名、用户主目录的绝对路径或缩写路径；所有本机路径必须使用 `<codex-home>` 或 `<repository-root>` 公开占位符。
7. 生成后运行：

   `PYTHONDONTWRITEBYTECODE=1 python3 skills/vibe-diagram/scripts/vibe_diagram_lint.py docs/runtime/outputs/codex-app-github-skill-smoke.html --type delivery-acceptance`

最终回复只报告输出路径、linter 结果，以及你实际调用的 skill 标识。
