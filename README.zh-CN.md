# vibe-diagram

英文主文档见 [README.md](README.md)。

## 项目定位

`vibe-diagram` 是一个生成自包含 HTML 图的可移植 agent skill。本仓只维护一份宿主中立的 canonical skill，并为四类客户端生成确定性静态包。当前版本是 Unreleased 0.1.0-rc.2 release-candidate snapshot；它不是稳定版，也不代表四类客户端的聚合运行时兼容。

## 单一事实源

`skills/vibe-diagram/` 是 skill 行为的唯一可编辑事实源。该目录包含 `SKILL.md`、11 份 reference、58 个 HTML 模板和一个仅使用 Python 标准库的 linter，保持零第三方运行时依赖。

`adapters/` 只保存各端 manifest 和白名单 overlay 定义。下列目录均为可重新生成的产物，不得手工维护：

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

本仓不会复制第二份中文 canonical Skill；中文 README 只是快速入口。

仓库根 `plugins/vibe-diagram/` 是本仓为 Codex publication 纳入的 builder-only 生成投影；它不是第二份 canonical，也不得手工编辑。确定性 repo marketplace catalog 位于 `.agents/plugins/marketplace.json`，并指向 `./plugins/vibe-diagram`。

## Codex 安装

公开仓库是 <https://github.com/imchenway/vibe-diagram>。两种 Codex 公开来源结构分别是由 `.agents/plugins/marketplace.json` 支持的 repo marketplace，以及由 `skills/vibe-diagram/` 支持的 GitHub skill 路径。

GitHub 安装说明固定到 RC 标签 `v0.1.0-rc.2`。该 RC 的运行时验证仍为 `Unverified`：尚未在任何客户端表面确立安装、发现、调用、HTML 交付、升级或卸载结论。以下说明只标识源路径，不代表稳定支持或聚合兼容性。

### Codex App 插件

使用 macOS Codex App 内置的 Codex CLI，或其他兼容的 `codex` 可执行文件：

```bash
codex plugin marketplace add imchenway/vibe-diagram --ref v0.1.0-rc.2
codex plugin add vibe-diagram@imchenway
```

安装完成后新建一个 Codex 任务，使新的 skill catalog 被加载。卸载插件与仓库 marketplace：

```bash
codex plugin remove vibe-diagram@imchenway
codex plugin marketplace remove imchenway
```

### GitHub skill 路径

在 Codex 任务中提出：

> 使用 `$skill-installer` 安装 `https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.2/skills/vibe-diagram`。

安装器完成后新建一个 Codex 任务。

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

构建报告中的 `static_validation: passed` 属于 package-static-valid，仅表示 builder production preflight 已通过。它不能证明完整 unit suite、确定性流程检查或第二轮完整 suite。static-valid 要求这些命令整体通过；证据保留在命令或 CI 输出中，不作为仓库文档提交。

RC.2 的运行时验证仍为 `Unverified`。它不继承旧标签的安装、发现、调用、HTML 交付、升级或卸载结论。在得到当前、范围明确的真实客户端证据前，稳定版提升继续阻断。

## 许可

Apache-2.0，详见 [LICENSE](LICENSE)。
