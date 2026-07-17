# Codex App GitHub 插件 smoke 请求

使用本次新执行已安装并注入的 `vibe-diagram:vibe-diagram` skill，生成一个简体中文、单文件、自包含的 delivery-acceptance HTML：

`docs/runtime/outputs/codex-app-github-plugin-smoke.html`

必须遵守以下约束：

1. 读取当前仓库的 `AGENTS.md`、`CONTEXT.md`、所有适用 ADR，以及已安装 skill 的 `references/delivery-acceptance.md`。
2. 从已安装 skill 的 `assets/templates/delivery-acceptance/acceptance-ledger.html` 复制骨架，保留 `data-diagram-type`、`data-template-family`、`data-template-id`、`data-template-layout` 和 ledger slots。
3. 只呈现以下已观测事实：
   - App 内置 Codex 从 `https://github.com/imchenway/vibe-diagram.git` 的 `v0.1.0-rc.1` 标签成功添加 Marketplace，名称为 `imchenway`；
   - `codex plugin add vibe-diagram@imchenway --json` 成功，版本为 `0.1.0-rc.1`；
   - Marketplace clone 的 HEAD 为 `31dff0c170ef33ae779890330d58cf689a6b95e7`，且精确匹配 `v0.1.0-rc.1`；
   - App 内置 Codex 的 `plugin list --json` 显示该插件 `installed: true`、`enabled: true`，Marketplace 来源类型为 `git`；
   - 新执行实际发现并调用的 skill 标识必须在最终回复中报告；若未发现 `vibe-diagram:vibe-diagram`，不得生成伪造的通过结论。
4. GitHub skill 路径独立安装、升级和 Codex App UI 确认必须标记为 `Unverified`，不得写成已完成。
5. 不得加载远程 CSS、JavaScript、字体或图片；不要修改任何其他文件。
6. 不得输出本机用户名、用户主目录的绝对路径或缩写路径；所有本机路径必须使用 `<codex-home>` 或 `<repository-root>` 公开占位符。
7. 生成后运行：

   `PYTHONDONTWRITEBYTECODE=1 python3 skills/vibe-diagram/scripts/vibe_diagram_lint.py docs/runtime/outputs/codex-app-github-plugin-smoke.html --type delivery-acceptance`

最终回复只报告输出路径、linter 结果，以及你实际调用的 skill 标识。
