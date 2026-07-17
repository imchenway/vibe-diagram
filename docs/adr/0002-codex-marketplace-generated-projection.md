---
status: accepted
---

# Codex Marketplace 使用受验证的仓内生成投影

Codex 首发同时支持 Plugin Marketplace 与 GitHub skill 路径直装。canonical 继续只位于 `skills/vibe-diagram/`；repository builder 负责创建或替换受版本控制的 `plugins/vibe-diagram/`，`.agents/plugins/marketplace.json` 固定指向该目录，同一稳定 tag 下的 skill 内容、manifest 版本与 Codex package 必须一致。这样保留单一事实源和标准 marketplace 目录约定，同时接受仓库包含一份不可手工编辑的派生副本。

## Rejected alternatives

- 不让仓库根目录直接充当插件，避免把测试、脚本和内部文档纳入插件边界，也避免偏离 `./plugins/<plugin-name>` 约定。
- 不采用仅 Release 压缩包的方案，因为它不能独立闭环已确认的 repo marketplace 安装入口。

## Consequences

发布前必须验证 `plugins/vibe-diagram/` 由 builder 生成、没有手工漂移，并与同版本 Codex package 的完整文件集和哈希一致。回滚以完整稳定 tag 为单位，不能只回退 marketplace catalog 或单独替换投影目录。
