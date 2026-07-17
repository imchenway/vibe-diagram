# Codex App 插件 smoke 请求

使用本次会话已安装并注入的 `vibe-diagram:vibe-diagram` skill，生成一个简体中文、单文件、自包含的 delivery-acceptance HTML：

`docs/runtime/outputs/codex-app-plugin-smoke.html`

必须遵守以下约束：

1. 读取当前仓库的 `AGENTS.md`、`CONTEXT.md`、所有适用 ADR，以及该 skill 的 `references/delivery-acceptance.md`。
2. 从 `assets/templates/delivery-acceptance/acceptance-ledger.html` 复制骨架，保留 `data-diagram-type`、`data-template-family`、`data-template-id`、`data-template-layout` 和 ledger slots。
3. 只呈现以下已观测事实：
   - `codex plugin marketplace add <repository-root> --json` 成功，Marketplace 名为 `imchenway`；其中 `<repository-root>` 是本次本地仓库绝对路径的公开占位符；
   - `codex plugin add vibe-diagram@imchenway --json` 成功，版本为 `0.1.0-rc.1`；
   - App 内置 `/Applications/Codex.app/Contents/Resources/codex plugin list` 显示 `installed, enabled`；
   - App 内置 Codex 新会话发现实际调用项为 `vibe-diagram:vibe-diagram`，路径位于 `<codex-home>/plugins/cache/imchenway/vibe-diagram/0.1.0-rc.1/skills/vibe-diagram/SKILL.md`；其中 `<codex-home>` 是本机 Codex home 的公开占位符。
4. GitHub 仓库、GitHub skill 路径安装、升级和卸载必须标记为 `Unverified`，不得写成已完成。
5. 不得加载远程 CSS、JavaScript、字体或图片；不要修改任何其他文件。
6. 不得输出本机用户名、用户主目录的绝对路径或缩写路径；所有本机路径必须使用上述公开占位符。
7. 生成后运行：

   `PYTHONDONTWRITEBYTECODE=1 python3 skills/vibe-diagram/scripts/vibe_diagram_lint.py docs/runtime/outputs/codex-app-plugin-smoke.html --type delivery-acceptance`

最终回复只报告输出路径、linter 结果，以及你实际调用的 skill 标识。
