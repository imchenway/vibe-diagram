# vibe-diagram

英文主文档见 [README.md](README.md)。

## 项目定位

`vibe-diagram` 是一个生成自包含 HTML 图的可移植 agent skill。本仓只维护一份宿主中立的 canonical skill，并为四类客户端生成确定性静态包。`v0.1.1` 建立了已发布、具备更新能力的独立 Skill lane；仓库版本 `0.1.2` 让 current 与 offline 检查保持只读，只有发现更高版本后才进入写入激活。GitHub Skill 证据不代表四类生成包的聚合兼容性。

## 单一事实源

`skills/vibe-diagram/` 是 skill 行为的唯一可编辑事实源。该目录包含 bootstrap `SKILL.md`、12 份 reference、58 个 HTML 模板、一个标准库 updater 和一个标准库 linter，保持零第三方运行时依赖。

`adapters/` 只保存各端 manifest 和白名单 overlay 定义。下列目录均为可重新生成的产物，不得手工维护：

- `build/codex/`
- `build/claude/`
- `build/gemini/`
- `build/copilot/`

本仓不会复制第二份中文 canonical Skill；中文 README 只是快速入口。

仓库根 `plugins/vibe-diagram/` 是本仓为 Codex publication 纳入的 builder-only 生成投影；它不是第二份 canonical，也不得手工编辑。确定性 repo marketplace catalog 位于 `.agents/plugins/marketplace.json`，并指向 `./plugins/vibe-diagram`。

## Codex Skill 安装

公开仓库是 <https://github.com/imchenway/vibe-diagram>。移动的 `stable` ref 已建立，永久的独立 Skill 安装入口为：

<https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram>

永久 URL 是面向新直装用户的移动安装通道。每次调用直装的 `0.1.1+` 时，bootstrap 都会读取轻量 stable manifest、比较严格版本，并在加载运行时工作流前从不可变版本标签升级。网络失败或发行包无效时继续使用本地版本；由生成包管理的副本跳过自更新。

公开 GitHub-path 证据已覆盖从 `stable` 安装、新进程发现与调用、HTML 交付与 bundled-linter 修复、offline fail-open 检查，以及 `v0.1.1` 的在线 current 检查。`v0.1.1` 到更高 stable 标签的真实替换，仍需在 `v0.1.2` 提升并实际执行后补齐。

### 在 Codex 任务中安装

向 Codex 提出：

> 使用 `$skill-installer` 安装 `https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram`。

安装完成后新建一个 Codex 任务，使新的 Skill catalog 被加载。首次调用可使用：

> 使用 `$vibe-diagram` 为当前仓库生成一份自包含 HTML 架构图，并运行 bundled linter。

### 使用内置 helper 安装

也可以直接调用系统 Skill 安装器：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref stable
```

当 `$CODEX_ROOT/skills/vibe-diagram` 已存在时，helper 会停止而不会覆盖。此时应使用下方的可恢复替换流程。

### 从 `v0.1.0` 一次性迁移

`v0.1.0` 不包含 updater。发布 `v0.1.1` 后，先把已安装 Skill 移出发现目录一次，再安装固定的桥接版本：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
BACKUP_ROOT="$CODEX_ROOT/backups/skills"
BACKUP_PATH="$BACKUP_ROOT/vibe-diagram-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_ROOT"
mv "$CODEX_ROOT/skills/vibe-diagram" "$BACKUP_PATH"
python3 "$CODEX_ROOT/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo imchenway/vibe-diagram \
  --path skills/vibe-diagram \
  --ref v0.1.1
```

在替换后的版本通过新任务调用和 bundled linter 前保留备份。不要移动或重写不可变的 `v0.1.0` 标签。

### 自动与手动更新

对直装的 `v0.1.1+`，bootstrap 每次调用都运行更新门禁：版本已最新时静默继续；发现新稳定标签时先校验、备份并更新，再加载运行时工作流；stable 来源不可用时继续使用本地版本。从 `v0.1.2` 起，current 与 offline 检查不创建锁文件，只有检测到更高版本后才需要写权限；激活阶段仍可能要求宿主授权网络或文件操作。

可以直接向已安装 Skill 提出：

> 使用 `$vibe-diagram` 将自身更新到最新稳定版。

也可以执行公开的手动更新命令：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/vibe-diagram/scripts/update_skill.py" \
  --force-check \
  --json
```

updater 会把新版下载到同级 staging 目录，校验发行 manifest 和目录摘要，保留可恢复备份，并仅在验证通过后启用新版。需要时可恢复最近备份：

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_ROOT/skills/vibe-diagram/scripts/update_skill.py" --rollback --json
```

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

GitHub-path Codex CLI 证据仅覆盖独立 Skill lane：公开 `stable` 安装、新进程发现与调用、HTML 交付与 lint、offline fail-open，以及 `v0.1.1` 的在线 current 检查。公开的更高版本替换仍待实际执行；这里不代表 Codex 插件、Claude Code、Gemini CLI 或 GitHub Copilot CLI 的聚合兼容性。

## 许可

Apache-2.0，详见 [LICENSE](LICENSE)。
