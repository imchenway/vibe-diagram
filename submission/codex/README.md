# Codex 官方提交候选包

本目录保存 `vibe-diagram` 的 skills-only plugin 提交字段和审核材料。它是仓库侧候选材料，不代表已经提交、通过审核或进入公共 Plugins Directory。

## 本地检查

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_codex_submission.py --check
```

## 生成审核工件

输出目录必须尚不存在：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_codex_submission.py \
  --output submission/codex/build
```

生成结果包含：

- 固定时间戳、固定权限、无压缩的确定性 skill ZIP；
- 供平台上传的 SVG logo；
- 绑定 listing、logo 和 skill tree hash 的 `submission-report.json`。

`validation_scope: package-static-valid` 只表示 builder production preflight 通过。它不证明真实客户端生命周期、OpenAI 身份验证、审核或公共发布。

## 仍需发布者完成

- 在 OpenAI Platform 使用已验证的个人或企业身份；
- 确保提交账号具有 `Apps Management: Write`；
- 审阅并批准 `docs/public/PRIVACY.md` 与 `docs/public/TERMS.md`；
- 选择公开国家或地区；
- 补齐 Codex App UI 与升级运行时证据；
- 在提交平台创建 `Skills only` 草稿、提交审核，并在批准后主动发布。
