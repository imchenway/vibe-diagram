# vibe-diagram

英文主文档见 [README.md](README.md)。

## 项目定位

`vibe-diagram` 是一个生成自包含 HTML 图的可移植 agent skill。本仓只维护一份宿主中立的 canonical skill，并为四类客户端生成确定性静态包。当前仓库版本以 `VERSION` 为准；`v0.1.1` 建立了已发布、具备更新能力的独立 Skill lane，`v0.1.3` 则让 current 与 offline 检查保持只读，并消除了发行归档中生成插件投影造成的歧义。GitHub Skill 证据不代表四类生成包的聚合兼容性。

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

公开 GitHub-path 证据已覆盖从 `stable` 安装、新进程发现与调用、HTML 交付与 bundled-linter 修复、offline fail-open 检查，以及 `v0.1.1` 的在线 current 检查。首次真实执行 `v0.1.1` 到 `v0.1.2` 时，完整仓库 ZIP 同时暴露 canonical 与生成插件的版本标记，更新器因此安全保留了原安装。仓库版本 `0.1.3` 增加归档导出规则和精确 canonical 根路径选择；成功的公开替换仍需在该版本提升并实际执行后补齐。

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

对直装的 `v0.1.1+`，bootstrap 每次调用都运行更新门禁：版本已最新时静默继续；发现新稳定标签时先校验、备份并更新，再加载运行时工作流；stable 来源不可用时继续使用本地版本。从 `v0.1.2` 起，current 与 offline 检查不创建锁文件，只有检测到更高版本后才需要写权限。从 `v0.1.3` 起，发行归档只导出 canonical 版本标记，updater 也只接受仓库根下的精确 canonical 路径；激活阶段仍可能要求宿主授权网络或文件操作。

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

静态验证命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --check
```

在该检查通过后，可生成本地包：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --output build
```

构建器只使用 Python 标准库，并从 `VERSION` 读取版本。

显式的本地投影命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --sync-publication
```

`--sync-publication` 是唯一 publication 写入口。`--check` 是只读检查：它会发现 publication 漂移，但不会修复 publication 文件。

## GitHub Skill 发布编排

标准库发布入口当前已实现 R00–R07，以及 R08 中的本地贡献者与只读 CI 切片。贡献者可以准备候选、执行完整本地门禁、刷新只读远端证据，并演练隔离 updater 生命周期；具备仓库写权限的维护者或 fork 所有者可以先调用受控的 `publish` 阶段，再分别授权 stable 推进和已安装客户端验证。角色化 fork 流程和维护者 checklist 见 [CONTRIBUTING.md](CONTRIBUTING.md)：

```bash
python3 scripts/release_github_skill.py prepare --version 0.1.4 --dry-run --json
python3 scripts/release_github_skill.py prepare --version 0.1.4 --json
python3 scripts/release_github_skill.py verify --version 0.1.4 --json
python3 scripts/release_github_skill.py status --version 0.1.4 --refresh --json
python3 scripts/release_github_skill.py publish --version 0.1.4 \
  --commit <main-merge-sha> \
  --notes-file /absolute/path/to/release-notes.md \
  --confirm-remote-actions \
  --json
python3 scripts/release_github_skill.py promote-stable --version 0.1.4 \
  --confirm-stable-promotion \
  --json
python3 scripts/release_github_skill.py verify-runtime --version 0.1.4 \
  --mode isolated \
  --json
python3 scripts/release_github_skill.py verify-runtime --version 0.1.4 \
  --mode installed-client \
  --artifact /absolute/path/to/runtime-smoke.html \
  --confirm-installed-skill-mutation \
  --json
```

`prepare` 更新发布元数据，并把 tracked publication 投影委托给仓库 builder；`verify` 执行只读确定性 builder 检查，通过 `python3 scripts/build_packages.py --output build` 生成被忽略的本地 build 树，将其中的 Codex 包与 tracked plugin 投影比对，检查 diff 并验证 canonical archive，同时始终把运行时验证标记为未验证；`status --refresh` 只读取 GitHub main、stable、tag、Release、workflow、manifest 和 tag ZIP 证据，不执行远端写入。

`publish` 要求已有持久化的 `LOCAL_VERIFIED` 证据、干净的工作树与 index、本地 HEAD 和远端 main 与目标提交一致、`origin` 与目标仓库一致、当前 GitHub 身份具备 push 权限、release notes 是不含凭据特征的普通 UTF-8 文件，并且显式提供 `--confirm-remote-actions`。它创建 annotated tag，仅执行非强制的 tag push，创建或复用同 tag 的 GitHub Release，只读取一次当前 workflow 状态而不等待，并通过真实 updater 归档路径校验远端 tag ZIP。同提交 tag/Release 会幂等复用；冲突 tag 失败关闭；可恢复的部分成功记录为 `PARTIAL_REMOTE`。

`promote-stable` 要求已有持久化的 `TAG_VERIFIED` 证据，并单独提供 `--confirm-stable-promotion` 授权。写入前，它会重新读取 main、tag、Release、当前异步 workflow 状态、不可变 tag ZIP、stable 祖先关系和 stable manifest；workflow 完成不再是推进前置条件。它只接受把已验证 release commit 以普通、非强制方式快进到 stable。push 后必须再次确认 stable commit、raw manifest 与不可变归档一致；对 raw/CDN 的短暂延迟使用有上限的指数退避。成功或已完成的推进记录为 `STABLE_PROMOTED`；如果 push 后最终一致性超时，会保留已推进但待确认的状态，不自动倒退，也不伪造验证成功。

`verify-runtime --mode isolated` 在临时目录安装前一个不可变 tag，通过已发布 stable manifest 完成升级，验证 current 与 offline fail-open，执行回滚、重升级、全新归档安装，并移除两份隔离安装。它不会触碰已安装 Skill，也不能证明 Codex 客户端发现。isolated 通过后只记录为前置证据，发行状态仍是 `STABLE_PROMOTED`。

`verify-runtime --mode installed-client` 要求 matching isolated 证据、已安装的前一稳定版本、一个尚不存在的绝对 artifact 路径，以及独立的 `--confirm-installed-skill-mutation`。它通过真实已安装 updater 完成升级、回滚和重升级；在全新的 ephemeral `codex exec` 进程中调用 `$vibe-diagram`；用升级后自带 linter 验证 HTML 工件；再临时隔离并恢复 Skill，由第二个全新进程确认不可发现。只有两种模式都通过，状态才成为限定于 Codex CLI lane 的 `RUNTIME_VERIFIED`。修改安装后若失败，脚本恢复本轮精确的前一版本备份并记录 `PROMOTED_RUNTIME_FAILED`，不会改写发行 tag，也不会倒退 stable。

脚本不会 commit、merge、修改 remote URL、force push、删除 tag、重写历史或把 `stable` 倒退；`publish`、stable 推进和已安装客户端修改分别使用独立确认。当前代码变更尚未执行真实运行时生命周期，因此实现 R07 能力本身不构成 runtime 证据。贡献者可以通过 `--repo owner/name` 使用 fork 范围的证据能力；只有具备自己 fork 写权限并提供相应显式确认时，才可执行 fork 范围发布或 stable 推进。

## 状态边界

构建报告中的 `static_validation: passed` 属于 package-static-valid，仅表示 builder production preflight 已通过。static-valid 还要求确定性 builder 检查、生成投影比对、干净 diff 检查和 canonical archive 校验通过；证据保留在命令或 CI 输出中，不作为仓库文档提交。

GitHub-path Codex CLI 证据仅覆盖独立 Skill lane：公开 `stable` 安装、新进程发现与调用、HTML 交付与 lint、offline fail-open、`v0.1.1` 的在线 current 检查，以及拒绝 `v0.1.2` 歧义归档后保留原安装。成功的公开更高版本替换仍待实际执行；这里不代表 Codex 插件、Claude Code、Gemini CLI 或 GitHub Copilot CLI 的聚合兼容性。

## 许可

Apache-2.0，详见 [LICENSE](LICENSE)。
