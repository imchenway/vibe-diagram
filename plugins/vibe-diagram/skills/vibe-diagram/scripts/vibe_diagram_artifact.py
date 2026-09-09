#!/usr/bin/env python3
"""准备独立候选、比较修改，并在验收后安全替换最终 HTML。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from vibe_diagram_lint import ArtifactParser, LintError, lint_text

# 三个真实浏览器视口与原有阅读契约一致。
VIEWPORTS = {(1440, 900), (1280, 800), (390, 844)}
# 仅移除本命令生成的候选标识，不改写作者任意 HTML。
CANDIDATE_RE = re.compile(r'\s*<meta name="vibe-diagram-candidate" content="[a-f0-9]{32}">')
# 对比数据不参与当前图的内容比较，也不执行历史文件脚本。
COMPARISON_RE = re.compile(r'\s*<script id="vibe-diagram-comparison" type="application/json">.*?</script>', re.DOTALL)


def digest(payload: bytes) -> str:
    """使用完整文件字节计算指纹，不尝试把文件自身指纹嵌入自身。"""
    return hashlib.sha256(payload).hexdigest()


def parse(text: str) -> tuple[ArtifactParser, dict]:
    """历史 HTML 只解析，不执行；身份缺失或冲突时拒绝比较。"""
    parser = ArtifactParser()
    parser.feed(text)
    parser.close()
    if parser.errors or parser.manifest_count != 1:
        raise ValueError("图形编号或清单有歧义，不能比较或交付：" + "; ".join(parser.errors))
    manifest = json.loads("".join(parser.manifest_chunks))
    if not isinstance(manifest, dict) or not manifest.get("artifactId"):
        raise ValueError("缺少有效的图形身份")
    return parser, manifest


def inventory(text: str) -> tuple[str, dict]:
    """提取已编写对象、关系、证据和视图，分别保存内容与手工几何。"""
    parser, manifest = parse(text)
    result = {}
    for element in parser.elements:
        attrs = element.attrs
        if not any(key in attrs for key in ("data-vd-node", "data-vd-edge", "data-vd-group", "data-vd-compare")):
            continue
        if not element.identifier:
            raise ValueError("对比对象缺少稳定编号")
        labels = [item.text for item in parser.elements if item.attrs.get("data-vd-edge-label") == element.identifier]
        details = [item.text for item in parser.elements if item.attrs.get("data-vd-detail-for") == element.identifier]
        semantics = {key: value for key, value in attrs.items() if key in {"data-vd-node", "data-vd-group", "data-vd-edge", "data-from", "data-to", "data-vd-member-of", "data-vd-message-kind", "data-vd-cardinality", "data-vd-evidence-state"}}
        semantics.update(text=element.text, labels=labels, details=details, view=element.view_id)
        # 时序消息 DOM 顺序就是作者给出的时间顺序，不能只比较端点。
        if "data-vd-message-kind" in attrs:
            semantics["order"] = len([item for item in result.values() if item["content"].get("view") == element.view_id and "order" in item["content"]])
        result[element.identifier] = {"label": element.text or " / ".join(labels) or element.identifier, "content": semantics, "geometry": [] if element.automatic else element.geometry}
    # 清单和入口变更也必须出现，不能只比较画布节点。
    for key in ("title", "questions", "criticalFacts", "views", "evidence"):
        result["manifest:" + key] = {"label": {"title": "标题", "questions": "关注问题", "criticalFacts": "关键事实", "views": "视图安排", "evidence": "证据"}[key], "content": manifest.get(key), "geometry": []}
    result["summary"] = {"label": "摘要", "content": [element.text for element in parser.elements if "data-vd-summary" in element.attrs], "geometry": []}
    return manifest["artifactId"], result


def compare(before: str, after: str) -> dict:
    """稳定编号相同才视作同一对象；位置变化不会变成业务变化。"""
    old_id, old = inventory(before)
    new_id, new = inventory(after)
    if old_id != new_id:
        raise ValueError("只能比较同一 artifactId 的前后两份图；不能按相似文字猜对象身份")
    changes = []
    for identifier in sorted(old.keys() | new.keys()):
        previous, current = old.get(identifier), new.get(identifier)
        kind = "added" if previous is None else "removed" if current is None else "changed" if previous["content"] != current["content"] else "moved" if previous["geometry"] != current["geometry"] else ""
        if kind:
            changes.append({"id": identifier, "kind": kind, "label": (current or previous)["label"], "beforeLabel": previous["label"] if previous else "", "afterLabel": current["label"] if current else "", "before": json.dumps(previous["geometry"] if kind == "moved" else previous["content"], ensure_ascii=False, sort_keys=True) if previous else "", "after": json.dumps(current["geometry"] if kind == "moved" else current["content"], ensure_ascii=False, sort_keys=True) if current else ""})
    return {"artifactId": new_id, "changes": changes}


def validate(text: str, allow_candidates: bool = False) -> None:
    """静态失败在写入前报告，绝不更换校验器来接受坏图。"""
    errors = lint_text(text, allow_candidates=allow_candidates)
    if errors:
        raise ValueError("静态检查未通过：\n" + "\n".join(errors))


def candidate_id(text: str) -> str:
    """候选标识必须唯一，由独立候选准备步骤生成。"""
    parser, _manifest = parse(text)
    tokens = [element.attrs.get("content", "") for element in parser.elements if element.tag == "meta" and element.attrs.get("name") == "vibe-diagram-candidate"]
    if len(tokens) != 1 or re.fullmatch(r"[a-f0-9]{32}", tokens[0]) is None:
        raise ValueError("候选标识缺失或不唯一，请重新 prepare")
    return tokens[0]


def write_candidate(output: Path, payload: bytes) -> None:
    """独立候选禁止覆盖，写入异常时移除本次创建的未完成文件。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        try:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            output.unlink(missing_ok=True)
            raise


def prepare(args: argparse.Namespace) -> dict:
    """冻结草稿与可选前后差异，返回需要浏览器验收的精确文件指纹。"""
    source, output = Path(args.input).expanduser().absolute(), Path(args.output).expanduser().absolute()
    if source.resolve() == output.resolve():
        raise ValueError("候选文件必须与草稿、正式交付文件分开")
    text = COMPARISON_RE.sub("", CANDIDATE_RE.sub("", source.read_text(encoding="utf-8")))
    validate(text, args.allow_candidates)
    if args.previous:
        previous = Path(args.previous).expanduser().absolute()
        if previous.resolve() == output.resolve():
            raise ValueError("不能覆盖上一份图来准备新候选")
        comparison = compare(previous.read_text(encoding="utf-8"), text)
        data = json.dumps(comparison, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        text = text.replace("</head>", '<script id="vibe-diagram-comparison" type="application/json">' + data + "</script>\n</head>")
    token = uuid.uuid4().hex
    text = text.replace("</head>", '<meta name="vibe-diagram-candidate" content="' + token + '">\n</head>')
    if candidate_id(text) != token:
        raise ValueError("候选文件必须具有明确的 head/body 结束标签")
    validate(text, args.allow_candidates)
    payload = text.encode("utf-8")
    write_candidate(output, payload)
    return {"status": "candidate-prepared", "artifact": str(output), "candidate": token, "sha256": digest(payload), "bytes": len(payload), "browser_layout": "not-verified", "product_reading": "not-reviewed"}


def accept(args: argparse.Namespace) -> dict:
    """校验已冻结字节及外部真实浏览器记录，然后原子替换正式交付文件。"""
    source, output = Path(args.input).expanduser().absolute(), Path(args.output).expanduser().absolute()
    if source.resolve() == output.resolve() or output.is_symlink():
        raise ValueError("候选与最终输出必须分开，最终输出不能是符号链接")
    payload = source.read_bytes()
    if digest(payload) != args.sha256:
        raise ValueError("候选文件已改变，旧的浏览器记录失效；请重新准备和检查")
    text = payload.decode("utf-8")
    validate(text, args.allow_candidates)
    token = candidate_id(text)
    checks = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if not isinstance(checks, list) or not checks:
        raise ValueError("浏览器记录必须是 receipt() 返回结果组成的数组")
    seen = set()
    for check in checks:
        if not isinstance(check, dict) or check.get("candidate") != token or check.get("status") != "passed" or check.get("issues") != []:
            raise ValueError("浏览器检查失败，或记录属于其他候选文件")
        viewport = check.get("viewport", {})
        if not isinstance(viewport, dict) or any(type(viewport.get(key)) is not int or viewport[key] <= 0 for key in ("width", "height")) or not isinstance(check.get("url"), str):
            raise ValueError("浏览器视口和来源地址格式无效")
        seen.add((viewport.get("width"), viewport.get("height")))
        if Path(unquote(urlparse(check.get("url", "")).path)).name != source.name:
            raise ValueError("浏览器打开的不是当前候选文件")
    if not VIEWPORTS.issubset(seen) or not args.reading_review.strip():
        raise ValueError("需要三个约定视口的真实检查和明确的产品阅读结论")
    output.parent.mkdir(parents=True, exist_ok=True)
    # 同目录锁只保护交付操作；用户编辑仍由旧文件指纹再次核对。
    lock = output.with_name("." + output.name + ".accepting")
    with lock.open("x") as lock_stream:
        # 文件存在即持有锁；关闭句柄后再替换和清理，兼容 Windows 文件占用规则。
        lock_stream.close()
        temporary = None
        try:
            old = output.read_bytes() if output.exists() else None
            if (old is not None and digest(old) != args.previous_sha256) or (old is None and args.previous_sha256):
                raise ValueError("正式文件与预期不一致；请检查最新文件，不能覆盖其他修改")
            with tempfile.NamedTemporaryFile(prefix="." + output.name + ".", dir=output.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if output.is_symlink() or (output.read_bytes() if output.exists() else None) != old:
                raise ValueError("写入前正式文件发生变化，已取消本次替换")
            os.replace(temporary, output)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
            lock.unlink(missing_ok=True)
    return {"status": "artifact-accepted", "artifact": str(output), "sha256": digest(payload), "bytes": len(payload), "candidate": token, "browser_viewports": sorted(seen), "reading_review": args.reading_review.strip(), "client_runtime": "not-verified"}


def main() -> int:
    """命令仅处理本地文件，不安装客户端，也不调用外部浏览器。"""
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare_parser = actions.add_parser("prepare", help="冻结待检查的新候选")
    accept_parser = actions.add_parser("accept", help="验收后安全替换最终图")
    for command in (prepare_parser, accept_parser):
        command.add_argument("--input", required=True, help="输入 HTML")
        command.add_argument("--output", required=True, help="输出 HTML")
        command.add_argument("--allow-candidates", action="store_true", help="用户已明确要求多方案探索")
    prepare_parser.add_argument("--previous", help="用于比较的上一份 HTML")
    accept_parser.add_argument("--sha256", required=True, help="prepare 返回的候选指纹")
    accept_parser.add_argument("--report", required=True, help="真实浏览器记录 JSON 文件")
    accept_parser.add_argument("--reading-review", required=True, help="人工产品阅读结论")
    accept_parser.add_argument("--previous-sha256", default="", help="覆盖前一份输出时必填的旧文件指纹")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args) if args.action == "prepare" else accept(args), ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, LintError) as exc:
        print(json.dumps({"status": "failed", "message": str(exc), "output": args.output}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
