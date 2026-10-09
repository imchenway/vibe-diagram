#!/usr/bin/env python3
"""运行最小验收自检，并生成供 Zeus 浏览器检查的代表性 HTML；不模拟浏览器通过。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# 所有示例使用当前 canonical 外壳，避免复制一份运行代码。
ROOT = Path(__file__).resolve().parents[1]
# 本地验收只导入脚本，不执行更新或安装。
CORE = ROOT / "skills/vibe-diagram"
sys.path.insert(0, str(CORE / "scripts"))
from vibe_diagram_scaffold import render, SHELL_CSS, SHELL_JS
from vibe_diagram_lint import lint_text
from vibe_diagram_artifact import accept, compare, digest, prepare


def node(identifier: str, role: str, label: str, *, critical: bool = False) -> str:
    """用作者选定的形状表达语义，坐标交由共享排版。"""
    shape = '<polygon data-vd-shape points="90,0 180,45 90,90 0,45"/>' if role == "decision" else '<ellipse data-vd-shape cx="85" cy="28" rx="85" ry="28"/>' if role in {"start", "end", "initial", "terminal"} else '<rect data-vd-shape width="180" height="64" rx="10"/>'
    return '<g id="' + identifier + '" data-vd-node="' + role + '"' + (' data-vd-critical' if critical else '') + '>' + shape + '<text x="16" y="36">' + label + '</text></g>'


def edge(identifier: str, source: str, target: str, label: str, kind: str = "flows", extra: str = "") -> str:
    """每条关系都保留独立编号、可见标签和作者选择的箭头。"""
    return '<path id="' + identifier + '" data-vd-edge="' + kind + '" data-from="' + source + '" data-to="' + target + '" marker-end="url(#arrow)" ' + extra + '/><text id="' + identifier + '-label" data-vd-edge-label="' + identifier + '">' + label + '</text>'


def example() -> str:
    """示例说明当前改图与交付机制；验收场景不冒充外部生产事实。"""
    flow = node("draft", "start", "编写修改") + node("check", "decision", "静态检查通过？") + node("candidate", "activity", "冻结独立候选") + node("browser", "activity", "检查画面与产品阅读") + node("accepted", "end", "安全替换交付文件", critical=True) + node("preserved", "end", "失败，原文件保留")
    flow += edge("draft-check", "draft", "check", "准备草稿") + edge("check-candidate", "check", "candidate", "通过") + edge("check-preserved", "check", "preserved", "未通过") + edge("candidate-browser", "candidate", "browser", "检查同一文件") + edge("browser-accepted", "browser", "accepted", "验收通过") + edge("browser-preserved", "browser", "preserved", "验收未通过")
    architecture = node("author", "participant", "作者确定事实") + node("shell", "component", "公共外壳") + node("delivery", "component", "安全交付命令")
    architecture += edge("author-shell", "author", "shell", "编写节点与关系", "authors") + edge("shell-delivery", "shell", "delivery", "提供检查记录", "supplies")
    sequence = "".join(node(identifier, "participant", label) + '<line data-vd-lifeline-for="' + identifier + '"/>' for identifier, label in [("writer", "作者"), ("validator", "检查命令"), ("reader", "浏览器")])
    sequence += edge("prepare-message", "writer", "validator", "准备独立候选", "message", 'data-vd-message-kind="sync"') + edge("prepared-message", "validator", "writer", "返回文件指纹", "message", 'data-vd-message-kind="return"') + edge("open-message", "writer", "reader", "打开候选检查", "message", 'data-vd-message-kind="async"') + edge("receipt-message", "reader", "writer", "返回画面检查记录", "message", 'data-vd-message-kind="return"')
    state = node("start-state", "initial", "草稿") + node("candidate-state", "state", "等待验收") + node("failed-state", "state", "需要修正") + node("accepted-state", "terminal", "已交付")
    state += edge("freeze-transition", "start-state", "candidate-state", "静态通过后冻结", "transition") + edge("fail-transition", "candidate-state", "failed-state", "检查发现问题", "transition") + edge("repair-transition", "failed-state", "candidate-state", "修正后重新冻结", "transition") + edge("accept-transition", "candidate-state", "accepted-state", "全部验收通过", "transition")
    data = node("candidate-record", "entity", "候选文件") + node("browser-record", "entity", "视口检查记录")
    data += edge("candidate-records", "candidate-record", "browser-record", "一份候选对应多个视口记录", "has", 'data-vd-cardinality="1:N"')
    views = [("flow", "business-flow", "流程图｜修改失败保留原图", flow), ("architecture", "architecture", "架构关系图｜共享能力职责", architecture), ("sequence", "code-sequence", "时序图｜冻结与检查", sequence), ("state", "state-machine", "状态图｜候选到交付", state), ("data", "data-model", "数据关系图｜文件与检查记录", data)]
    body, records = [], []
    for index, (identifier, family, title, content) in enumerate(views):
        role = "primary" if index == 0 else "supporting"
        body.append('<section id="' + identifier + '-view" data-vd-view="' + identifier + '" data-vd-family="' + family + '" data-vd-view-role="' + role + '"><h2 data-vd-view-title>' + title + '</h2><div data-vd-viewport><svg id="' + identifier + '-svg" data-vd-layout="auto" data-vd-zoom-target xmlns="http://www.w3.org/2000/svg">' + ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#176aa6"/></marker></defs>' if index == 0 else '') + content + '</svg></div></section>')
        records.append({"id": identifier, "family": family, "role": role, "elementId": identifier + "-view"})
    # 原生内容的结构检查继续存在，不增加第六套图形模板。
    body.append('<section id="matrix-view" data-vd-view="matrix" data-vd-family="comparison-matrix" data-vd-view-role="supporting"><h2 data-vd-view-title>比较表｜检查与交付</h2><table data-vd-matrix><tr><th>结果</th><th>候选</th><th>原交付图</th></tr><tr data-vd-difference><th>检查失败</th><td>保留并修正</td><td>不替换</td></tr></table><p data-vd-conclusion>只有验收通过才替换。</p></section>')
    body.append('<section id="prototype-view" data-vd-view="prototype" data-vd-family="page-prototype" data-vd-view-role="supporting"><h2 data-vd-view-title>页面原型｜本地评审记录</h2><form data-vd-prototype data-vd-responsive-state><label>评审结论 <input placeholder="填写实际观察" /></label><button type="reset">清空草稿</button></form></section>')
    records += [{"id": identifier, "family": family, "role": "supporting", "elementId": identifier + "-view"} for identifier, family in [("matrix", "comparison-matrix"), ("prototype", "page-prototype")]]
    # 场景要求复用同一组图法，不固定布局或视图数量。
    body.append('<aside id="review-task" data-vd-task="code-review"><p data-vd-task-section="current">现状：直接覆盖输出会失去上一份图。</p><p data-vd-task-section="scenario">场景：改图后检查失败。</p><p data-vd-task-section="repair">修复：候选独立检查后才替换。</p><p data-vd-task-section="acceptance">验收：失败后原文件字节不变。</p></aside>')
    body.append('<aside id="fault-task" data-vd-task="fault-debugging"><p data-vd-task-section="symptom">示例故障：连线没有接到节点。</p><p data-vd-task-section="impact">影响：读者无法确定结果。</p><p data-vd-task-section="hypothesis">待验证假设：手工坐标没有随文字更新。</p><p data-vd-task-section="repair">修复方向：重新排版并检查端点。</p><p data-vd-task-section="verification">验收：真实浏览器检查通过。</p></aside>')
    body.append('<aside id="design-task" data-vd-task="technical-design"><p data-vd-task-section="change">变化：五种图法共用能力。</p><p data-vd-task-section="boundary">边界：只处理已有事实和关系。</p><p data-vd-task-section="decision">决定：HTML/SVG 保持唯一图形来源。</p><p data-vd-task-section="acceptance">验收：保留事实、检查文件和交互。</p></aside>')
    manifest = {"$schema": "vibe-diagram/artifact-manifest@1", "artifactId": "safe-diagram-delivery", "language": "zh-CN", "title": "流程图｜改图与安全交付", "audience": ["product-manager"], "questions": [{"id": "delivery-question", "text": "什么时候替换原交付图？", "priority": "critical", "answeredBy": ["accepted"]}], "criticalFacts": [{"id": "safe-delivery", "statement": "验收通过才替换交付文件", "status": "observed", "visibleIn": ["accepted"], "evidenceIds": ["source"]}], "views": records, "evidence": [{"id": "source", "status": "observed", "sourceKind": "source-code", "source": "skills/vibe-diagram/scripts/vibe_diagram_artifact.py:accept", "supports": ["safe-delivery"]}], "extensions": {}}
    text = render(manifest["title"], "zh-CN", SHELL_CSS.read_text(), SHELL_JS.read_text())
    start, end = text.index('<script id="vibe-diagram-manifest"'), text.index('</script>', text.index('<script id="vibe-diagram-manifest"'))
    text = text[:start] + '<script id="vibe-diagram-manifest" type="application/json">' + json.dumps(manifest, ensure_ascii=False) + text[end:]
    text = text.replace('<p data-vd-summary data-vd-scaffold-empty></p>', '<p data-vd-summary>修改先形成独立候选。画面和产品阅读验收通过后，才替换正式文件；失败时原图保留。下方展示五种基本图法与原生内容。</p>')
    start, end = text.index('<main data-vd-content'), text.index('</main>')
    return text[:start] + '<main data-vd-content>' + "\n".join(body) + text[end:]


def check(output: Path) -> dict:
    """检查根因约束及失败保护，再留下真实浏览器可打开的独立候选。"""
    text = example()
    assert not lint_text(text), lint_text(text)
    assert lint_text(text.replace('data-vd-cardinality="1:N"', ""))
    assert lint_text(text.replace('data-vd-task-section="acceptance"', 'data-vd-task-section="missing"'))
    before = text.replace("冻结独立候选", "准备候选")
    differences = compare(before, text)["changes"]
    assert any(change["id"] == "candidate" and change["kind"] == "changed" for change in differences)
    # 自动坐标变化不计为内容变化，手工坐标变化单独分类。
    manual = text.replace('data-vd-layout="auto"', '').replace('id="candidate" data-vd-node', 'id="candidate" transform="translate(1 2)" data-vd-node')
    assert any(item["kind"] == "moved" for item in compare(manual, manual.replace('translate(1 2)', 'translate(3 4)'))["changes"])
    assert not compare(text, text.replace('id="candidate" data-vd-node', 'id="candidate" transform="translate(3 4)" data-vd-node'))["changes"]
    # 编号变化必须表现为新增和删除，不能按相同文字自动合并。
    changed_identity = text.replace('id="candidate" data-vd-node', 'id="candidate-new" data-vd-node')
    identity_changes = compare(text, changed_identity)["changes"]
    assert {item["kind"] for item in identity_changes if item["id"] in {"candidate", "candidate-new"}} == {"added", "removed"}
    try:
        compare(text.replace('"safe-diagram-delivery"', '"another-artifact"'), text)
        raise AssertionError("不同身份不能比较")
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        draft, candidate, final = directory / "draft.html", directory / "candidate.html", directory / "final.html"
        draft.write_text(text)
        final.write_bytes(b"previous accepted output")
        prepared = prepare(SimpleNamespace(input=str(draft), output=str(candidate), previous=None, allow_candidates=False))
        candidate.write_text(candidate.read_text() + "<!-- changed after check -->")
        try:
            accept(SimpleNamespace(input=str(candidate), output=str(final), sha256=prepared["sha256"], previous_sha256=digest(final.read_bytes()), report="not-read.json", reading_review="不应执行", allow_candidates=False))
            raise AssertionError("失效候选不能替换输出")
        except ValueError:
            assert final.read_bytes() == b"previous accepted output"
        # 人为构造失败记录仅检查拒绝路径，不能当作真实浏览器验收证据。
        candidate.write_text(candidate.read_text().replace('<!-- changed after check -->', ''))
        failed_report = directory / "failed-report.json"
        failed_report.write_text(json.dumps([{"status": "failed", "candidate": prepared["candidate"], "issues": [{"code": "deliberate-check-failure"}]}]))
        try:
            accept(SimpleNamespace(input=str(candidate), output=str(final), sha256=prepared["sha256"], previous_sha256=digest(final.read_bytes()), report=str(failed_report), reading_review="不应执行", allow_candidates=False))
            raise AssertionError("失败检查记录不能替换输出")
        except ValueError:
            assert final.read_bytes() == b"previous accepted output"
    # 直接检查纯路由算法，不以此代替浏览器的形状与可读性检查。
    javascript = 'require(process.argv[1]); const assert = require("node:assert/strict"); const path = VibeDiagramLayout.route({x:0,y:0},{x:100,y:0},[{x:40,y:-10,w:20,h:20}]); assert(path.some(p => Math.abs(p.y) >= 10)); assert.deepEqual(path[0],{x:0,y:0}); assert.deepEqual(path.at(-1),{x:100,y:0}); const levels = VibeDiagramLayout.ranks([{id:"a"},{id:"b"},{id:"c"}],[{from:"a",to:"b"},{from:"b",to:"a"},{from:"b",to:"c"}]); assert(levels.get("c") > levels.get("b"));'
    subprocess.run(["node", "-e", javascript, str(CORE / "assets/shell/layout.js")], check=True)
    output.mkdir(parents=True, exist_ok=True)
    draft, previous, candidate = output / "draft.html", output / "previous.html", output / "candidate.html"
    draft.write_text(text); previous.write_text(before)
    return prepare(SimpleNamespace(input=str(draft), output=str(candidate), previous=str(previous), allow_candidates=False))


if __name__ == "__main__":
    # 输出目录显式指定，候选仍拒绝覆盖。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    print(json.dumps(check(Path(parser.parse_args().output).resolve()), ensure_ascii=False))
