# vibe-diagram

英文主文档见 [README.md](README.md)。

## 项目定位

`vibe-diagram` 是一个生成自包含 HTML 图的可移植 agent skill。本仓只维护一份宿主中立的 canonical skill，并为四类客户端生成确定性静态包。`v0.1.0` 是稳定 GitHub 标签。已验证的 GitHub Skill lane 不代表四类生成包的聚合兼容性。

## 单一事实源

`skills/vibe-diagram/` 是 skill 行为的唯一可编辑事实源。该目录包含 `SKILL.md`、11 份 reference、58 个 HTML 模板和一个仅使用 Python 标准库的 linter，保持零第三方运行时依赖。

`adapters/` 只保存各端 manifest 和白名单 overlay 定义。下列目录均为可重新生成的产物，不得手工维护：

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

本仓不会复制第二份中文 canonical Skill；中文 README 只是快速入口。

仓库根 `plugins/vibe-diagram/` 是本仓为 Codex publication 纳入的 builder-only 生成投影；它不是第二份 canonical，也不得手工编辑。确定性 repo marketplace catalog 位于 `.agents/plugins/marketplace.json`，并指向 `./plugins/vibe-diagram`。

## Codex Skill 安装

公开仓库是 <https://github.com/imchenway/vibe-diagram>。稳定的独立 Skill 来源为：

<https://github.com/imchenway/vibe-diagram/tree/v0.1.0/skills/vibe-diagram>

GitHub-path Codex CLI lane 已针对 `v0.1.0` 完成运行时验证：全新安装、新进程发现与调用、HTML 交付、从候选基线替换升级以及卸载隔离均已通过。该 lane 级结论不代表聚合兼容性，也不覆盖其他客户端生成包。

### 在 Codex 任务中安装

向 Codex 提出：

> 使用 `$skill-installer` 安装 `https://github.com/imchenway/vibe-diagram/tree/v0.1.0/skills/vibe-diagram`。

安装完成后新建一个 Codex 任务，使新的 Skill catalog 被加载。首次调用可使用：

> 使用 `$vibe-diagram` 为当前仓库生成一份自包含 HTML 架构图，并运行 bundled linter。

### 使用内置 helper 安装

也可以直接调用系统 Skill 安装器：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref v0.1.0
```

当 `$CODEX_ROOT/skills/vibe-diagram` 已存在时，helper 会停止而不会覆盖。此时应使用下方的可恢复替换流程。

### 升级或重新安装

先把已安装 Skill 移出发现目录，再重新安装固定的稳定标签：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
BACKUP_ROOT="$CODEX_ROOT/backups/skills"
BACKUP_PATH="$BACKUP_ROOT/vibe-diagram-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_ROOT"
mv "$CODEX_ROOT/skills/vibe-diagram" "$BACKUP_PATH"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref v0.1.0
```

在替换后的版本通过新任务调用和 bundled linter 前保留备份。

### 可恢复卸载

把 Skill 移出 `$CODEX_ROOT/skills/`，新 Codex 任务将不再发现它：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
BACKUP_ROOT="$CODEX_ROOT/backups/skills"
BACKUP_PATH="$BACKUP_ROOT/vibe-diagram-uninstalled-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_ROOT"
mv "$CODEX_ROOT/skills/vibe-diagram" "$BACKUP_PATH"
```

移除后新建一个 Codex 任务。需要回滚时，把选定备份恢复到 `$CODEX_ROOT/skills/vibe-diagram`。

### 可搜索性边界

GitHub-path 是直装 lane，不会让 `vibe-diagram` 出现在 curated `$skill-installer` 索引或公共 Plugins Directory 中。本仓仍包含 `plugins/vibe-diagram/` 与 `.agents/plugins/marketplace.json` 下由 builder 生成的独立 Codex marketplace 投影；插件发布遵循另一套审核生命周期。

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

GitHub-path Codex CLI lane 已针对 `v0.1.0` 完成运行时验证。该结论只覆盖从固定 GitHub 标签安装的独立 Skill，不代表 Codex 插件、Claude Code、Gemini CLI 或 GitHub Copilot CLI 的聚合兼容性。

## 许可

Apache-2.0，详见 [LICENSE](LICENSE)。
