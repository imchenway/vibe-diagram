# vibe-diagram

英文主文档见 [README.md](README.md)。

## 项目定位

`vibe-diagram` 是一个生成自包含 HTML 图的可移植 agent skill。本仓只维护一份宿主中立的 canonical skill，并为四类客户端生成确定性静态包。当前版本是 Unreleased 0.1.0-rc.1 release-candidate snapshot；它只是本地仓库工件，不代表已经公开发布或客户端运行时兼容。

## 单一事实源

`skills/vibe-diagram/` 是 skill 行为的唯一可编辑事实源。该目录包含 `SKILL.md`、11 份 reference、58 个 HTML 模板和一个仅使用 Python 标准库的 linter，保持零第三方运行时依赖。

`adapters/` 只保存各端 manifest 和白名单 overlay 定义。下列目录均为可重新生成的产物，不得手工维护：

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

本仓不会复制第二份中文 canonical Skill；中文 README 只是快速入口。

仓库根 `plugins/vibe-diagram/` 是面向 Codex 的 builder-only 生成投影，也是未来纳入版本控制的候选；它不是第二份 canonical，也不得手工编辑。确定性 repo marketplace catalog 位于 `.agents/plugins/marketplace.json`，并指向 `./plugins/vibe-diagram`。

## 计划中的 Codex 公开来源

计划中的两种公开来源结构分别是由上述 catalog 支持的 repo marketplace，以及未来稳定 tag 下由 `skills/vibe-diagram/` 支持的 GitHub skill 路径来源。它们只是正在准备的仓库结构，不是现在可用的安装命令。真实安装命令、URL 和生命周期说明必须等 GitHub 公开发布并取得真实客户端证据后再补充。

## 产物契约

每个静态包都逐字节包含 canonical skill、根 `LICENSE` 和唯一客户端 manifest。Codex 包另含白名单中的 `agents/openai.yaml`。构建器会拒绝 symlink、路径越界、非白名单文件、远程资源、manifest 漂移和 canonical hash 漂移。

四端在同一个 staging 树中整体生成；发布时以整个 `build/` 为事务单位，提升失败会恢复旧树。

## 静态验证

三条静态验证命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3.9 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --check
```

在这些检查通过后，可生成本地包：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --output build
```

构建器只使用 Python 标准库，并从 `VERSION` 读取版本。

显式的本地投影命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --sync-publication
```

`--sync-publication` 是唯一 publication 写入口。`--check` 是只读检查：它会发现 publication 漂移，但不会修复 publication 文件。

## 状态边界

兼容性账本见 [docs/compatibility.md](docs/compatibility.md)。构建报告中的 `static_validation: passed` 属于 package-static-valid，仅表示 builder production preflight 已通过。它不能证明完整 unit suite、two-build deterministic check、transaction failure matrix、static evidence 重算或第二轮完整 suite；这些流程门禁需要另行执行并留存证据。`docs/static-validation.json` 只记录当前工件 hash 绑定，同样不能证明上述流程门禁。

四端聚合兼容性层面的运行时验证仍为 `Unverified`。当前新增一份 scoped 本地仓库 Marketplace 证据，覆盖 Codex App 内置运行时的安装、发现、调用和 HTML 交付；它不覆盖 App UI、GitHub 来源、升级或卸载。证据记录在 `docs/runtime/macos-codex-app-local-marketplace.json`。

Codex 稳定版门禁是 2 种安装入口 x 2 个 macOS 客户端表面 x 6 个生命周期动作 = 24 个相互独立的真实客户端证据单元。4 个本地真实客户端证据单元已通过，20 个真实客户端证据单元仍未执行，因此当前 release-candidate snapshot 不能提升为稳定版。Linux 与 Windows 仍为 `Unverified`。macOS 浏览器时序交互单独记录，不是客户端运行时证据。

## 许可

Apache-2.0，详见 [LICENSE](LICENSE)。
