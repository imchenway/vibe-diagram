# ADR 0001：单一 canonical 与生成式客户端包

## 状态

已接受。

## 背景

同一个图形 skill 需要提供给四类客户端。如果分别维护四份完整副本，模板、reference、linter 和行为契约会产生不可审计的漂移。

## 决策

- 仓库只维护 single canonical：`skills/vibe-diagram/`。
- 四端目录都是 generated packages，由 adapter 约束 manifest 与少量白名单 overlay。
- No symlinks；也采用 no hand-maintained mirrors，所有客户端包都复制并验证 canonical 的完整字节。
- 发布事务覆盖 all four clients；只有四端全部组装并验证成功，新的 `build/` 才可提升。
- `build/` 与构建报告都是可重新生成的本地产物，不是 canonical 输入。

## Trade-offs

收益是单一事实源、可复算 hash、四端一致升级和明确的运行时未知边界。成本是每次修改 canonical 都要重新生成全部客户端包，并维护严格的 adapter、manifest 和构建报告契约。

不使用 symlink 会增加本地生成产物的字节量，但避免客户端、归档工具和跨平台复制对链接语义产生不同解释。

## Rollback

发布前把旧 `build/` 移到固定 backup，再提升完整 staging。提升失败时恢复旧树；提升与恢复同时失败时保留 staging 和 backup 作为取证现场。提升成功后才清理 backup；清理失败不回滚已提交的新树，而是返回 cleanup pending，要求人工确认后处理残留 backup。
