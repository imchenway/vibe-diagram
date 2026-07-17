# 兼容性账本

本账本将“本仓能确定性生成并静态验证包”与“厂商客户端真实运行”分开记录。四端 `Static package` 以同一事务整体推进；安装、发现、调用、HTML 交付和升级/卸载必须分别取得客户端运行证据。

当前状态是 Unreleased 0.1.0-rc.1 release-candidate snapshot。`skills/vibe-diagram/` 是唯一可编辑 canonical；`plugins/vibe-diagram/` 是 builder-only Codex 生成投影，`.agents/plugins/marketplace.json` 是指向该投影的确定性 catalog。`--sync-publication` 是唯一 publication 写入口，`--check` 保持只读。

| Client | Static package | Install | Discovery | Invocation | HTML delivery | Upgrade/uninstall |
|---|---|---|---|---|---|---|
| Codex | Passed | Unverified | Unverified | Unverified | Unverified | Unverified |
| Claude Code | Passed | Unverified | Unverified | Unverified | Unverified | Unverified |
| Gemini CLI | Passed | Unverified | Unverified | Unverified | Unverified | Unverified |
| GitHub Copilot CLI | Passed | Unverified | Unverified | Unverified | Unverified | Unverified |

`Static package: Passed` 表示当前 canonical、manifest、文件集、hash 与 Codex publication 在静态工件层相互一致；it is not a vendor CLI validator result，也不是流程门禁或运行时结论。

`docs/static-validation.json` 只绑定当前 artifact、package 与 publication hash；完整 unit suite、two-build deterministic check、transaction failure matrix、evidence recomputation 与 second full suite 是另行执行的流程证据。这些流程不能由 build report 或 evidence JSON 单独证明，也不代表聚合运行时列通过。

已观测的 scoped Codex 证据记录在 `docs/runtime/macos-codex-app-local-marketplace.json`：installation entry = local repository marketplace；client surface = App-bundled Codex runtime。Install = Passed; Discovery = Passed; Invocation = Passed; HTML delivery = Passed。Upgrade = Unverified; Uninstall = Unverified; Codex App UI confirmation = Unverified。公开 GitHub repository 已建立，但 GitHub marketplace install 与 GitHub skill install 的运行时验证仍为 Unverified，因此上方 Codex 聚合行不提升。

Codex stable gate: 2 installation entries x 2 macOS surfaces x 6 lifecycle actions = 24 independent real-client evidence units. 4 local real-client evidence units have passed; 20 real-client evidence units remain unexecuted. 固定 RC 标签下的 repo marketplace 与 GitHub skill 路径安装说明已经给出，但其 GitHub 运行时验证仍为 Unverified；Linux and Windows remain Unverified。

macOS sequence interaction: Passed

该状态只覆盖当前 macOS 本地浏览器中的时序交互观察，不外推到客户端运行时。
