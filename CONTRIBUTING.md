# 贡献与发布指南

感谢你参与 Vibe Diagram。仓库为 GitHub 直装 Skill 提供同一个标准发布入口：`scripts/release_github_skill.py`。该入口按阶段运行，不会替代分支、提交、Pull Request、评审或合并流程。

## 角色与权限

| 角色 | 可以执行 | 权限边界 |
|---|---|---|
| 普通贡献者 | `prepare --dry-run`、`prepare`、`verify`、`status`、isolated runtime 演练 | 不需要官方仓库写权限，不应使用官方发布凭据 |
| Fork 维护者 | 普通贡献者阶段，以及自己 fork 范围的发布演练 | 仅使用 `--repo <owner>/<repository>` 指向自己的 fork；远端写入仍需自己的写权限和逐阶段确认 |
| 官方维护者 | tag、GitHub Release、stable 推进和真实客户端验收 | 本地 `static-valid` 后可直接发布；CI 作为异步证据，仍分别确认每类有副作用的动作 |

静态验证、远端发布、stable 推进和 runtime-verified 是四层不同证据。GitHub-path Codex CLI 的结果不能外推到 Codex App、其他客户端或公共 Plugins Directory。

## 普通贡献流程

先在候选分支执行无写入预检，再准备候选并运行完整本地门禁：

```bash
python3 scripts/release_github_skill.py prepare --version <next-version> --dry-run --json
python3 scripts/release_github_skill.py prepare --version <next-version> --json
python3 scripts/release_github_skill.py verify --version <next-version> --json
python3 scripts/release_github_skill.py status --version <next-version> --json
```

`prepare` 会更新版本和发布元数据，并通过 builder 同步 tracked 生成投影；`verify` 会执行只读 builder 检查、`--output build` 本地构建、投影一致性和 diff，最后完成 canonical archive 校验。通过只表示 `static-valid`，不表示远端已经发布或客户端已经运行。

完成本地验证后，按仓库正常流程提交 PR。脚本不会创建分支、commit、push、PR、审批或 merge。

## Fork 发布演练

fork 所有者在所有阶段都应显式覆盖仓库坐标：

```bash
python3 scripts/release_github_skill.py status --version <next-version> \
  --repo <owner>/<repository> \
  --refresh \
  --json
```

如需在 fork 中演练 `publish` 或 `promote-stable`，只能使用 fork 自己的写权限，并分别提供 `--confirm-remote-actions` 与 `--confirm-stable-promotion`。这些确认不授权修改官方仓库，也不允许 force push、删除 tag、重写历史或倒退 `stable`。

## CI 只读门禁

`.github/workflows/static-validation.yml` 只授予 `contents: read`。CI 直接调用标准入口的 `verify` 完成确定性构建、投影、diff 和 canonical archive 校验，并将状态写到 runner 临时目录中的 `RELEASE_STATE_DIR`。该 job 不执行 `status --refresh`、`publish`、`promote-stable` 或 `verify-runtime --mode installed-client`，也不需要发布密钥。

## 官方维护者发布 checklist

1. 选择严格递增的稳定 patch 版本，先执行 `prepare --version <next-version> --dry-run`。
2. 执行 `prepare --version <next-version>` 与 `verify --version <next-version>`，确认结果为 `static-valid` 且 `runtime_validation` 仍为 `unverified`。
3. 将本地已验证候选提交并推送到 `main`；不等待 GitHub Actions。
4. 准备普通 UTF-8 release notes，传入已推送的 main commit，并在当前动作得到明确授权后使用 `--confirm-remote-actions` 立即执行 `publish`。
5. `publish` 只读取一次当前 workflow 状态作为异步证据；无论它是 missing、pending、success 还是 failure，都不取代本地门禁，也不阻断 tag/Release。
6. 确认状态为 `TAG_VERIFIED` 后，再单独取得授权并使用 `--confirm-stable-promotion` 推进 `stable`。
7. 先执行 `verify-runtime --mode isolated`；它不会触碰已安装 Skill，也不能单独形成客户端发现证据。
8. 只有在允许修改真实安装时，才提供全新绝对 artifact 路径和 `--confirm-installed-skill-mutation` 执行 installed-client 验证。
9. installed-client 成功后只把对应版本、GitHub-path 和 Codex CLI lane 记录为 `RUNTIME_VERIFIED`；失败则检查 `PROMOTED_RUNTIME_FAILED` 和精确 previous-version 恢复结果，不删除或改写已发布 tag。

## 当前验收边界

直接稳定发布以本地 `static-valid` 为远端写入门禁，不等待 GitHub Actions；CI 结果仅作为发布后的异步证据。仓库中的确定性构建、投影检查、归档校验和只读 CI 定义不能证明真实客户端发现或卸载生命周期已经发生。
