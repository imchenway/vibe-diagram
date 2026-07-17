# Codex GitHub 发布投影设计规格

## 文档状态

- 任务：`TASK_20260716_001`
- 日期：2026-07-16
- 状态：设计已逐节确认，规格自审与用户审阅已完成；实施计划已编制
- 阶段：PLAN；尚未获得 develop、Git、GitHub、Marketplace 或客户端执行授权
- 主审计工件：`docs/TASK_20260716_001_vibe-diagram_GitHub公共安装就绪度审计.html`
- 适用里程碑：Codex 首发；Claude Code、Gemini CLI、GitHub Copilot CLI 不进入首发兼容声明

## 1. 目标与成功边界

本设计为 `vibe-diagram` 增加一个可审计、可重算、不可手工维护的 Codex 仓内发布投影，使未来的公开仓库同时具备以下两种来源结构：

1. Repo Marketplace：`.agents/plugins/marketplace.json` 指向 `./plugins/vibe-diagram`。
2. GitHub skill 路径直装：稳定 tag 下的 `skills/vibe-diagram/` canonical core。

本设计的本地完成状态是 `local-release-ready`，不是 `public-installable` 或 `runtime-verified`。当前阶段不创建 Git 仓库、不访问 GitHub、不安装 Codex CLI/App、不触碰用户配置，也不执行发现、调用、HTML 交付、升级或卸载测试。

稳定版只能沿 `v0.1.0-rc.1` → `v0.1.0` 提升。运行时门禁固定为 2 种安装入口 × 2 个 macOS 客户端表面 × 6 个生命周期动作，共 24 个独立证据单元；安装、发现、调用、HTML 交付、升级和卸载不能跨入口或跨 CLI/App 借用结论。24 个单元和所有静态 CI 门禁全部通过后，才能提升 `v0.1.0`。Linux 与 Windows 继续标记为 `Unverified`。

## 2. 已确认的产品与仓库决策

| 决策 | 已确认口径 |
| --- | --- |
| 公开仓库 | 未来目标为 `github.com/imchenway/vibe-diagram`，唯一 Git 根是当前目录，默认分支为 `main`。本设计不授权 `git init`。 |
| 发布者 | 仓库、plugin manifest 与 marketplace 统一使用 `imchenway`；不公开个人邮箱。 |
| canonical | 唯一可编辑事实源仍为 `skills/vibe-diagram/`。 |
| Codex 投影 | `plugins/vibe-diagram/` 是 builder-only、受版本控制的生成投影，不是第二 canonical。 |
| Marketplace | `.agents/plugins/marketplace.json` 是确定性生成的 repo marketplace catalog。 |
| 构建入口 | 选定方案 A：只在现有 `scripts/build_packages.py` 增加显式 `--sync-publication`；不新增第二个发布脚本。 |
| 普通 build | `--output build` 的输入、输出、成功 JSON、退出码与 tracked 文件副作用保持不变。 |
| 只读检查 | `--check` 保留现有双构建确定性检查，并新增 publication drift 校验；成功输出契约保持不变。 |
| CI | 未来只添加最小静态 GitHub Actions；PR、push、tag 均运行，不自动创建 tag、Release 或发布 Marketplace。 |
| 版本 | develop 阶段先把当前 `VERSION` 的 `0.1.0` development snapshot 收敛为 `0.1.0-rc.1`；只有 24 个运行时证据单元和 CI 全部通过，才允许改为 `0.1.0` 并创建稳定 tag。 |
| 运行时 | 客户端安装与测试已明确暂停；所有静态状态持续写 `runtime_validation: unverified`。 |
| 公共源集合 | 纳入产品源码、测试、构建/CI 定义、稳定文档/ADR、静态证据与 Codex 生成投影；排除 `docs/TASK_*`、`build/` 和事务临时目录。 |
| 回滚单位 | 本地同步按 plugin + catalog 完整对恢复；公开发布后按完整稳定 tag/release 回滚，禁止只替换其中一个目标。 |

## 3. 当前事实与不变式

### 3.1 已存在的可复用能力

- `scripts/build_packages.py:1488-1545` 已集中实现客户端 package 的组装、白名单、manifest 字节、canonical 与 extra file 校验。
- `scripts/build_packages.py:1555-1626` 已从受信输入生成四端 package 与确定性 `build-report.json`。
- `scripts/build_packages.py:1629-1673` 已给出单目标 build 的 backup/promote/rollback 语义基线。
- `scripts/build_packages.py:1695-1736` 已区分只读双构建检查与 `build/` 发布。
- `scripts/build_packages.py:1739-1778` 已冻结 `--check` / `--output build` 的严格互斥 CLI 与成功摘要。
- `adapters/codex/adapter.json:1-14` 和 `adapters/codex/manifest.template.json:1-25` 是 Codex package 的现有输入定义。
- `tests/test_build_transaction.py:116-155` 固化了离线、HOME 清洁、现有 build 保持与四端整体生成契约。
- `tests/test_build_transaction.py:310-323` 固化了必选、互斥、禁止参数缩写的 CLI 契约。
- `tests/test_documentation_contract.py:505-544` 已能从仓库重算 `docs/static-validation.json` 的 schema v1 证据。

### 3.2 不得改变的边界

1. `build/` 继续是可丢弃生成物，只能由 builder 创建或替换，不得成为 publication 的输入。
2. `build/build-report.json` 保持 schema v1 和现有字段集，不加入 tracked publication 信息。
3. canonical、adapter、`VERSION`、根 `LICENSE` 是 publication 组装的唯一受信输入。
4. package 或静态证据通过不能外推为客户端运行时通过。
5. 实现不得增加第三方运行时或测试依赖，不得访网，不得调用客户端，不得写用户 HOME。
6. 当前目录不是 Git 仓库；在另获授权前不能用 Git 状态替代文件级验证，也不能 commit。

## 4. 方案选择

### 4.1 选定：同一 builder，显式同步

`scripts/build_packages.py --sync-publication` 从与四端构建相同的受信输入组装 Codex package 与 marketplace catalog。普通 build 不产生 tracked diff；只读 check 不修复 drift。该方案复用一份组装真理，符合 ADR-0001 与 ADR-0002。

### 4.2 拒绝：普通 build 自动同步

不让 `--output build` 同时改写忽略的 `build/` 与 tracked publication。两类生命周期、回滚语义和审计边界不同，绑定后会让日常构建意外产生待提交变化。

### 4.3 拒绝：独立同步脚本

不新增 `scripts/sync_codex_publication.py`。第二 CLI 会复制参数、错误模型、事务与测试契约，增加漂移面。

## 5. 发布投影的数据模型

### 5.1 受跟踪 plugin

目标目录为 `plugins/vibe-diagram/`。它必须与同一输入、同一版本生成的完整 `build/codex/` package 具备完全相同的相对文件集、文件模式、字节与 tree hash，包括：

- `.codex-plugin/plugin.json`
- 根 `LICENSE`
- `skills/vibe-diagram/` 下的完整 canonical 字节
- Codex adapter 白名单中的 `skills/vibe-diagram/agents/openai.yaml`

实现必须直接复用 Codex package 组装/校验内核，禁止复制 `build/codex/`，也禁止读取现存 `build/`。

### 5.2 Marketplace catalog

`.agents/plugins/marketplace.json` 的逻辑对象固定为：

```json
{
  "name": "imchenway",
  "interface": {
    "displayName": "imchenway"
  },
  "plugins": [
    {
      "name": "vibe-diagram",
      "source": {
        "source": "local",
        "path": "./plugins/vibe-diagram"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

约束如下：

- 根对象只能包含 `name`、`interface`、`plugins`；`plugins` 只能有一个条目。
- `interface.displayName` 只属于 marketplace 根，不写入 plugin entry。
- plugin entry 只能包含 `name`、`source`、`policy`、`category`。
- `policy.products` 不存在；`ON_INSTALL` 只是 catalog 默认策略，不表示本 skill 引入凭证。
- 序列化复用 `_deterministic_json_bytes`：`ensure_ascii=True`、`allow_nan=False`、`indent=2`、`sort_keys=True`，文件以一个换行结尾。
- 上线前仍须在获得访网授权后按当时 OpenAI 官方规范复核；规范变化必须回退 PLAN，不得在发布时静默改字段。

### 5.3 Publication record

组装与校验内核返回不含绝对路径、时间戳或临时目录名的记录：

```json
{
  "package_version": "0.1.0-rc.1",
  "plugin_manifest_sha256": "64-char lowercase hex SHA-256",
  "plugin_tree_sha256": "64-char lowercase hex SHA-256",
  "marketplace_sha256": "64-char lowercase hex SHA-256",
  "runtime_validation": "unverified"
}
```

该记录只用于进程内校验、成功摘要组装和静态证据生成，不新增独立 tracked report。

## 6. CLI 与副作用契约

### 6.1 三个严格互斥模式

`parse_args` 的 required mutually-exclusive group 扩展为：

- `--check`
- `--output build`
- `--sync-publication`

仍保持 `allow_abbrev=False`。零模式、多模式、`--out`、`--che`、`--sync` 和其他未知参数均由 argparse 返回退出码 2。

### 6.2 旧模式兼容

- `--output build` 只写 `build/`，不读、不写 `plugins/`、`.agents/`、`.publication.*` 或静态证据。
- `--check` 仍不接受 output；在现有双 build 确定性检查后重算 publication 并与 tracked 目标比较。
- 两个旧模式成功时的 stdout JSON 字段集、值、退出码与 stderr 行为不变。
- `--check` 发现 publication 缺失或漂移时返回 1，只在 stderr 输出首个可操作差异，不执行同步或修复。

### 6.3 新模式成功摘要

`--sync-publication` 成功时 stdout 只输出一行确定性 JSON：

```json
{
  "backup_cleanup_pending": false,
  "changed": true,
  "mode": "sync-publication",
  "output": [
    "plugins/vibe-diagram",
    ".agents/plugins/marketplace.json"
  ],
  "runtime_validation": "unverified",
  "static_validation": "passed"
}
```

相同输入的第二次同步必须返回 `changed: false`，不创建 backup，不 rename tracked 目标，也不改变任何字节。

预期业务错误继续使用现有 `BuildError` 家族，stderr 以 `error:` 开头并返回 1，不输出 traceback。publication cleanup pending 是新模式中唯一会同时输出结构化摘要与非零退出码的已验证新对状态：摘要中 `backup_cleanup_pending: true`，stderr 给出残留 backup 绝对路径与人工处理提示，退出码为 1。现有 `--output build` 遇到 `.build.backup` 清理失败时返回 0 的旧契约保持不变。

## 7. 写入数据流

1. 在创建任何 staging 前验证 repository root、固定目标、父路径、symlink 与残留 `.publication.backup/`。
2. 在仓库根以 `.publication.staging-` 为固定前缀创建操作系统生成唯一后缀的 staging 目录，从受信输入组装完整 plugin 与 catalog。
3. 对 staging 执行精确文件集、模式、字节、manifest 版本、canonical hash、catalog schema 与 source path 校验。
4. 若 staging 与两个 tracked 目标完全一致，清理 staging 并返回 `changed: false`。
5. 原子创建 `.publication.backup/` 作为事务互斥标记和旧值保存根。
6. 在 backup 内写入 `transaction.json`。字段集固定为 `schema_version`、`package_version`、`plugin_existed`、`catalog_existed`、`created_parent_paths`、`phase`；不得写时间戳或绝对路径。`phase` 只允许 `backup-created`、`plugin-backed-up`、`catalog-backed-up`、`plugin-promoted`、`catalog-promoted`、`validated`、`cleanup-pending`，每次更新采用临时文件加 `os.replace`。
7. 按顺序备份旧 plugin、备份旧 catalog、提升新 plugin、提升新 catalog。
8. 对就地新对重新执行完整 publication 校验。
9. 最终校验通过后清理 staging，再清理 backup；两者完成后才返回成功。

这是可恢复的多路径事务，不宣称为操作系统级多路径原子提交。所有 staging、backup 和 tracked 目标均位于同一仓库文件系统，单次 rename 使用 `os.replace`。

## 8. 只读检查数据流

1. 在临时目录重新执行两次完整四端 build，保持现有字节级确定性比较。
2. 从同一受信输入重算一次 expected publication tree。
3. 校验 tracked plugin 与 catalog 自身结构，再比较目录、文件集、文件模式、字节和 hash。
4. 任一缺失、多余、手工修改、symlink、模式变化、manifest/version 错位或 catalog 指针错误均为 drift。
5. 报告首个稳定排序后的差异路径，返回 1；不写 tracked 目标、不写 `build/`、不写 HOME、不调用客户端。
6. 临时目录必须清理；如果清理失败，命令返回非零并报告残留路径。

存在 `.publication.backup/` 时，sync 与 check 都必须在创建 staging 前 fail-closed。该目录是未完事务证据，不是可自动删除的 cache。

## 9. 错误、事务与回滚

| 场景 | 必须行为 | 结果 |
| --- | --- | --- |
| 输入、路径、symlink、manifest 或 catalog 无效 | 事务前失败；只清理本次 staging | 退出 1；tracked 目标不变 |
| 已有 `.publication.backup/` | 在 staging 前阻断，不覆盖、不合并、不删除 | 退出 1；保留现场 |
| 新旧完全一致 | 幂等 no-op，不创建 backup、不 rename | 退出 0，`changed: false` |
| 首次同步部分提升失败 | 删除已提升的新目标，恢复 plugin 与 catalog 都缺席的原状；只删除本次创建且仍为空的父目录 | 回滚成功仍退出 1 |
| 更新时部分提升或最终校验失败 | 恢复旧 plugin + catalog 完整对 | 回滚成功仍退出 1 |
| 回滚也失败 | 保留 staging、backup、transaction journal、部分就地状态和原始/回滚错误 | 退出 1；禁止 local-release-ready |
| 新对已验证但 backup 清理失败 | 保留新对和旧 backup，不回滚新对 | 退出 1，`backup_cleanup_pending: true`；后续 sync/check 继续阻断 |
| check 发现 drift | 报告差异但不修复 | 退出 1；阻断 CI/RC 提升 |

回滚只能操作 transaction journal 声明由本次事务拥有的路径。不得递归清理不属于本次事务的父目录或用户文件。人工恢复残留现场后，必须重新运行 `--sync-publication` 和 `--check`，不能直接把状态标记为通过。

## 10. Ignore 与跟踪边界

`.gitignore` 新增：

```gitignore
.publication.staging-*/
.publication.backup/
```

不得忽略：

- `plugins/vibe-diagram/`
- `.agents/plugins/marketplace.json`
- `.github/workflows/`
- `docs/static-validation.json`
- `docs/superpowers/specs/`

未来公开历史纳入本规格和稳定 ADR；`docs/TASK_*` 继续作为本地任务记忆，不进入公共源集合。

## 11. 静态证据 schema v2

`docs/static-validation.json` 升级为严格 schema v2。现有字段保持原义，新增唯一根字段 `codex_publication`：

```json
{
  "schema_version": 2,
  "package_version": "0.1.0-rc.1",
  "runtime_validation": "unverified",
  "build_report_sha256": "64-char lowercase hex SHA-256",
  "canonical_tree_sha256": "64-char lowercase hex SHA-256",
  "clients": {
    "codex": {
      "manifest_sha256": "64-char lowercase hex SHA-256",
      "package_tree_sha256": "64-char lowercase hex SHA-256"
    }
  },
  "codex_publication": {
    "manifest_sha256": "64-char lowercase hex SHA-256",
    "package_tree_sha256": "64-char lowercase hex SHA-256",
    "marketplace_sha256": "64-char lowercase hex SHA-256"
  }
}
```

示例中的 `clients` 省略了其余三个现有客户端；实际文件仍必须精确包含 codex、claude、gemini、copilot 四个键。`codex_publication` 的 manifest 与 package tree 必须分别等于同版本 `clients.codex` 的对应值；marketplace hash 从 tracked catalog 字节重算。证据不包含时间戳、机器路径、Git SHA 或客户端运行时结论。

`build/build-report.json` 继续保持 schema v1，因为普通四端 build 不读取 tracked publication。`static-valid` 仍要求完整测试、package-static-valid build、可重算证据和第二次完整测试；`local-release-ready` 还要求 publication、文档和未来 CI 定义的本地静态门禁全部成立。

## 12. 测试设计

### 12.1 测试落点

| 测试文件 | 新增或扩展契约 |
| --- | --- |
| `tests/test_publication_projection.py` | publication 精确组装、catalog 严格 schema、确定性字节、投影/Codex package 同一性、幂等与 drift。 |
| `tests/test_build_transaction.py` | 三模式 CLI、旧模式零回归、首次/更新事务、每个 rename 失败点、最终校验失败、回滚失败、cleanup pending、残留 backup。 |
| `tests/test_repository_contract.py` | tracked/ignored 路径边界、禁止 symlink、标准库与离线约束、未来 workflow 静态契约。 |
| `tests/test_documentation_contract.py` | 中英文 README 双入口与未发布边界、schema v2 可重算、运行时不得外推、RC/stable 门禁。 |

实现必须遵循 TDD：先增加会因缺失 publication 行为而失败的测试，观察红灯；再做最小实现转绿；最后在全绿下重构。生成 tracked 投影不能作为绕过红灯的手段。

### 12.2 预计变更面

| 路径 | 设计内变更 |
| --- | --- |
| `scripts/build_packages.py` | 复用/抽取 Codex package 内核，增加 publication 组装、校验、diff、事务与第三 CLI 模式。 |
| `tests/test_publication_projection.py` | 新增 publication 专项契约。 |
| `tests/test_build_transaction.py`、`tests/test_repository_contract.py`、`tests/test_documentation_contract.py` | 扩展既有兼容、事务、仓库、文档和证据契约。 |
| `VERSION` | 在获准 develop 后从当前 `0.1.0` development snapshot 改为 `0.1.0-rc.1`。 |
| `.gitignore` | 只新增 publication staging/backup；不得忽略 tracked projection。 |
| `plugins/vibe-diagram/`、`.agents/plugins/marketplace.json` | 只能由新 builder 模式生成或替换。 |
| `.github/workflows/static-validation.yml` | 新增只读静态 CI 定义，不自动发布。 |
| `README.md`、`README.zh-CN.md`、`CHANGELOG.md`、`docs/compatibility.md`、`docs/static-validation.json` | 同步 RC、双入口、静态/运行时边界与 schema v2。 |

`skills/vibe-diagram/`、四端 adapter 定义和 `build-report.json` schema 不在行为变更范围。`build/` 只能通过正式 builder 重算，不能手工编辑。

### 12.3 必须覆盖的反向用例

- plugin 缺失、多余文件、字节改动、模式变化、symlink、manifest 名称或版本错位。
- catalog 缺字段、多字段、重复 JSON key、非对象根、非有限数字、错误相对路径、错误 policy/category、多个 plugin、非确定性字节。
- 旧 CLI 零参数、多参数、缩写、非法 output；旧成功 JSON、退出码、stderr 与副作用不变。
- 二次 sync 仍 rename 或产生字节变化。
- check 隐式修复、改写 build/HOME/tracked 文件、访问 socket/URL 或启动客户端。
- 首次同步与更新时每个 backup/promote/final-validate 失败点。
- rollback 失败、journal 残缺、cleanup pending、并发/崩溃残留 backup。
- evidence 无法重算、publication 与 clients.codex hash 不等、runtime 被写成 passed。
- CI 缺少 PR/push/tag 任一入口、执行 sync、自动发布、运行客户端或检查后留下工作树变化。

## 13. 可测试验收标准

| AC | 通过条件 | 失败判定 |
| --- | --- | --- |
| AC-01 | `--sync-publication` 与两个旧模式严格互斥；旧 build/check 成功 JSON 与副作用不变。 | 任一旧命令、退出码、stdout/stderr 或 tracked 副作用漂移。 |
| AC-02 | `plugins/vibe-diagram/` 与同版本 Codex package 文件集、模式、字节和 tree hash 完全一致。 | 任一文件、模式、字节或 hash 不一致。 |
| AC-03 | marketplace JSON 精确符合第 5.2 节字段、值、路径与确定性序列化。 | 缺/多字段、重复 key、值错位、非确定性字节或错误 plugin 指针。 |
| AC-04 | 相同输入连续第二次同步返回 `changed: false`，tracked tree 无字节变化。 | 第二次 rename、hash 变化或产生 diff。 |
| AC-05 | `--check` 捕获所有投影/catalog drift，执行前后 tracked tree、HOME 与 `build/` 不变。 | 漏报 drift 或隐式修复/生成文件。 |
| AC-06 | 首次/更新的每个提升失败点恢复完整旧对或原始缺席；回滚失败保留全部恢复证据。 | 新旧混用、单目标恢复、异常被吞或证据被清理。 |
| AC-07 | cleanup pending 保留已验证新对与旧 backup，返回非零；下一次 sync/check 继续阻断。 | 返回 0、删除 backup、回滚新对或允许绕过现场。 |
| AC-08 | 构建器与测试仅用 Python 标准库，不访网、不启动客户端、不写用户配置。 | 新依赖、socket/URL、Codex CLI/App 调用或 HOME 改动。 |
| AC-09 | schema v2 可从工作树重算并绑定 projection；build report schema 保持 v1。 | 证据不可重算，或普通 build 被迫读取 tracked publication。 |
| AC-10 | Python 3.9 + 3.14 首次全量、build、两次 sync、check、证据刷新、Python 3.9 + 3.14 二次全量全部成功。 | 任一命令非零、测试失败、二次 sync 非 no-op、drift 或证据错位。 |
| AC-11 | GitHub Actions 在 PR/push/tag 运行双 Python 与只读 check，检查后工作树无变化且不自动发布。 | 缺事件、CI 运行 sync/客户端、自动 Release 或失败后继续提升。 |
| AC-12 | 所有静态状态保持 `runtime_validation: unverified`；运行时矩阵未通过持续阻断 stable。 | 把测试、CI、hash 或当前会话产图写成真实客户端证据。 |

## 14. 本地静态签收顺序

获得 develop 授权并完成实现后，必须按顺序执行；任一步失败立即停止：

1. `PYTHONDONTWRITEBYTECODE=1 python3.9 -m unittest discover -s tests -v`
2. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，当前支持基线为 Python 3.14
3. `PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --output build`
4. `PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --sync-publication`
5. 立即再次执行相同 sync，要求退出 0 且 `changed: false`
6. `PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_packages.py --check`
7. 用当次可重算 hash 更新 `docs/static-validation.json` schema v2
8. 重跑 Python 3.9 完整测试
9. 重跑当前 Python 3.14 完整测试
10. 在真实 Git 仓建立后检查工作树只包含预期 tracked 变更；当前非 Git 目录阶段不能伪造此证据

这套管线只建立 `local-release-ready`。它不访问 GitHub、不安装客户端、不产生 runtime 证据。

## 15. 未来 GitHub Actions

未来 `.github/workflows/static-validation.yml` 只承担静态 fail-closed 门禁：

- 事件：pull request、push 到 `main`、匹配 `v*` 的 tag push。
- 测试矩阵：Python 3.9 与 3.14，各运行完整 `unittest discover`。
- 静态 job：运行 `scripts/build_packages.py --check`，随后要求 `git diff --exit-code` 且 `git status --porcelain` 为空。
- CI 不执行 `--sync-publication`，不安装 Codex，不写用户配置，不创建 tag/Release，不调用 Marketplace 发布。
- 任一测试、确定性、projection、catalog、文档、证据或工作树清洁检查失败，都阻断 RC/stable 提升。

## 16. 文档与公开声明

中英文 README 在本地准备阶段只说明：canonical、两种计划中的 Codex 安装来源、生成投影、静态验证命令与 `Unreleased`/`Unverified` 边界。目标仓库尚未公开时，不得写成用户现在已经可以安装，也不得把计划命令描述为已验证命令。

真实公共安装命令、稳定 tag URL 与升级/卸载步骤必须在获得 GitHub 和客户端执行授权后，依据当时官方文档与真实运行证据补齐。当前 `docs/compatibility.md` 的安装、发现、调用、HTML、升级/卸载列继续为 `Unverified`。

## 17. 风险与控制

| 风险 | 控制 |
| --- | --- |
| Marketplace schema 在真正发布前变化 | 公开发布前重新核对官方 OpenAI 规范；变化则回退 PLAN 和测试，不静默兼容。 |
| 双目标不是 OS 原子事务 | 固定 backup 互斥、journal、成对恢复、最终就地校验、失败保留现场。 |
| generated projection 被手改 | `--check` 字节级 drift、CI 工作树清洁、schema v2 hash 绑定。 |
| 普通 build 产生 tracked diff | `--output build` 契约冻结；只有显式 sync 可写 publication。 |
| 静态通过被误写为运行时通过 | report/evidence/README/compatibility 全部保留 `unverified`，AC-12 反向测试。 |
| 当前没有 Git 仓库 | 只做文件级静态准备；Git 状态、branch、remote、tag 和 CI 结果均留到另行授权阶段。 |

## 18. 回滚边界

- 本地实现回滚：恢复 `scripts/`、测试、README、evidence、workflow 定义与 tracked projection 的前一组受跟踪内容；`build/` 由 builder 重算。
- 本地同步事务回滚：严格按第 9 节恢复 plugin + catalog 完整对或原始缺席。
- 公开 RC/stable 回滚：按完整 tag/release 回退，不单独替换 catalog 或 plugin。
- 运行时失败：保持 RC，不提升 stable；不得以“静态测试通过”覆盖真实客户端失败。

## 19. 明确非目标

- 本规格不修改 `skills/vibe-diagram/` 的可复用行为。
- 不发布 Claude Code、Gemini CLI 或 GitHub Copilot CLI。
- 不创建 Git 仓库、commit、push、tag、Release 或 PR。
- 不运行 Marketplace、Codex CLI/App 或任何安装/卸载命令。
- 不引入自动发布、签名、公证、遥测、外部服务或第三方依赖。
- 不声称覆盖 Linux、Windows、企业策略限制或所有 GitHub 账号环境。

## 20. 下一门禁

用户审阅并明确批准本规格后，下一步只能使用 `superpowers:writing-plans` 生成可执行实施计划。写计划不等于 develop 授权；实施前仍须复核变更点、兼容影响、风险、AC、验证与回滚，并再次取得用户明确确认。
