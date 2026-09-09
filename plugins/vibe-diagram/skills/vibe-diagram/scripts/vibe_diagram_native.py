"""调用包内固定引擎，绑定业务覆盖清单，并组装原主题的完整原生查看器。"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# 引擎和适配文件均相对当前 Skill 定位，不依赖开发仓库或任务文档。
CORE = Path(__file__).resolve().parents[1]
# 上游源码保持原样，适配在目录之外完成。
ENGINE = CORE / "assets/archify"
# 页面与导出共用的视觉适配目录。
CANVAS = CORE / "assets/native"
# 数据流表达系统关系，不能与实体数量关系混淆。
FAMILIES = {"architecture": "architecture", "dataflow": "architecture", "workflow": "business-flow", "sequence": "code-sequence", "lifecycle": "state-machine"}
# 对应的原生节点和关系集合名，不复制用户的节点清单。
COLLECTIONS = {"architecture": ("components", "connections"), "dataflow": ("nodes", "flows"), "workflow": ("nodes", "edges"), "sequence": ("participants", "messages"), "lifecycle": ("states", "transitions")}
# 原生图形命名空间；作者 SVG 使用相同标准。
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def read_json(path: Path) -> dict:
    """拒绝重复键和非有限值，避免同一份源被两个环节理解成不同内容。"""
    def unique(pairs):
        """同名字段只能出现一次。"""
        # 每个对象独立检查键的唯一性。
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"JSON 字段重复：{key}")
            value[key] = item
        return value

    def invalid(value):
        """JSON 不能含 NaN 或 Infinity。"""
        raise ValueError(f"JSON 数值无效：{value}")

    # 文件作为数据解析，不执行其中任何字符串。
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("输入必须是 JSON 对象")
    return value


def verify_engine() -> dict:
    """核对固定上游文件，丢失或改变时停止，不在线修补技能包。"""
    # 来源清单随包发行；发布包本身还由已有完整性机制验证。
    provenance = read_json(ENGINE / "source.json")
    for relative, expected in provenance["files"].items():
        # 只允许来源清单指向包内的普通文件。
        path = ENGINE / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ENGINE.resolve()):
            raise ValueError(f"内置引擎文件缺失或路径无效：{relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"内置引擎文件发生改变：{relative}")
    return provenance


def node_command(arguments: list[str], cwd: Path) -> str:
    """以独立参数调用本机 Node，不安装依赖、不构造 shell 命令。"""
    # 运行要求从固定上游的运行声明而来。
    node = shutil.which("node")
    if not node:
        raise ValueError("需要本机 Node.js 18 或以上才能生成原生图形；阅读已生成的 HTML 不需要 Node。")
    # 防止开发机环境偷偷改变质量标准或触发仓库校验。
    environment = {key: value for key, value in os.environ.items() if key not in {"ARCHIFY_REPO_ROOT", "ARCHIFY_QUALITY_PROFILE", "NODE_OPTIONS"}}
    # 输出与错误均保留，调用方明确区分编译失败与浏览器验证。
    result = subprocess.run([node, *arguments], cwd=cwd, env=environment, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError("内置绘图引擎未通过：\n" + (result.stderr or result.stdout).strip())
    return result.stdout


def tag(element: ET.Element) -> str:
    """忽略命名空间前缀，保留注释节点。"""
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def parse_svg(source: str) -> ET.Element:
    """作者 SVG 必须为可离线检查的图形，不允许嵌入脚本或外部实体。"""
    if re.search(r"<!DOCTYPE|<!ENTITY", source, re.I):
        raise ValueError("SVG 不能包含外部实体或文档类型声明")
    # 保留上游用于标识图例和结构的注释。
    root = ET.fromstring(source, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    if tag(root) != "svg" or root.tag != "{" + SVG_NS + "}svg":
        raise ValueError("输入必须是带标准命名空间的独立 SVG")
    if any(item.get('id', '').startswith('vibe-canvas-') for item in root.iter()):
        raise ValueError('SVG 编号不能使用保留的 vibe-canvas- 前缀')
    # 这些内容不能完整、安全地投影为单幅可导出的图形。
    if any(tag(item) in {"script", "foreignObject", "iframe"} or any(key.lower().startswith("on") for key in item.attrib) for item in root.iter()):
        raise ValueError("SVG 不能含脚本、事件属性或嵌入页面；交互由公共查看器提供")
    return root


def bind_svg(svg_text: str, family: str, manifest: dict, diagram: dict | None = None) -> str:
    """在最终 SVG 上绑定检查标记，不改变节点、文字或已计算的路线。"""
    # 对象映射只在本次组装期间生成，不成为第二份人工维护的来源。
    # 上游内联 SVG 由 HTML 提供命名空间；转成独立 XML 前补齐声明。
    if diagram is not None and not re.search(r'<svg\b[^>]*\bxmlns=', svg_text):
        svg_text = svg_text.replace('<svg ', '<svg xmlns="' + SVG_NS + '" ', 1)
    # 生命周期的装饰轨道会暗示输入中不存在的转换；实际转换始终以 transitions 为准。
    if diagram is not None and diagram['diagram_type'] == 'lifecycle':
        svg_text, count = re.subn(r'(<!-- Primary lifecycle rail -->)\s*<path\b[^>]+/>', r'\1', svg_text, count=1)
        if count != 1:
            raise ValueError('生命周期装饰轨道接入点发生变化')
    root = parse_svg(svg_text)
    if diagram is not None and diagram['diagram_type'] == 'lifecycle':
        # 上游固定画三个区域，只保留实际状态使用的区域，避免补造业务分组。
        used_bands = {state['lane'] if state['lane'] in {'main', 'terminal'} else 'event' for state in diagram['states']}
        # ponytail: 固定上游的三个区域坐标；升级上游时随接入点重新核对。
        for band, line_y, text_y in [('main', 112, 100), ('event', 264, 252), ('terminal', 436, 424)]:
            if band not in used_bands:
                for item in list(root):
                    if (tag(item) == 'path' and re.fullmatch(rf'M 72 {line_y} L [\d.]+ {line_y}', item.get('d', ''))) or (tag(item) == 'text' and item.get('x') == '72' and item.get('y') == str(text_y)):
                        root.remove(item)
    # 归属用于找到原生关系分组内真正的路径及文字。
    parents = {child: parent for parent in root.iter() for child in parent}
    # 补充角色只用于解释图法，不能在清单中重复填写节点或连线。
    roles = manifest.get("extensions", {}).get("nodeRoles", {})
    if not isinstance(roles, dict) or any(not isinstance(value, str) or not value for value in roles.values()):
        raise ValueError("extensions.nodeRoles 必须是节点编号到业务角色的映射")
    # 已编译原生节点和作者自写 SVG 都投影到同一个查看器。
    nodes = [item for item in root.iter() if item.get("data-node-id") or item.get("data-vd-node")]
    # 图中稳定编号不能重名，渲染器不会通过删掉节点来修复重名。
    by_id = {}
    for node in nodes:
        # 原生节点保留原 DOM 编号；作者 SVG 继续使用自己的 DOM 编号。
        identity = node.get("data-node-id") or node.get("id")
        if not identity or identity in by_id or not node.get("id"):
            raise ValueError("图形节点必须有唯一且稳定的编号")
        by_id[identity] = node
        node.set("data-node-id", identity)
        # 原生类型是视觉分类，不能仅凭颜色猜业务判断或结束状态。
        default = "component" if family == "architecture" else "participant" if family == "code-sequence" else "entity" if family == "data-model" else "state" if family == "state-machine" else "activity"
        node.set("data-vd-node", node.get("data-vd-node") or roles.get(identity, default))
        # 原生节点文字已明确标记，作者 SVG 优先使用可见主标签。
        label = node.get("data-node-label") or next(("".join(item.itertext()).strip() for item in node if tag(item) == "text"), "")
        if not label:
            raise ValueError(f"节点没有业务名称：{identity}")
        node.set("data-node-label", label)
        node.set("data-node-kind", node.get("data-node-kind") or node.get("data-vd-node"))
        node.set("tabindex", "0"); node.set("role", "button"); node.set("aria-pressed", "false")
        # 只标记真实外轮廓，图标和阴影不作为边界。
        shape = next((item for item in node if item.get("data-vd-shape") is not None), None)
        if shape is None:
            shape = next((item for item in node if tag(item) in {"rect", "circle", "ellipse", "polygon"}), None)
        if shape is None:
            raise ValueError(f"节点缺少真实形状：{identity}")
        shape.set("data-vd-shape", "")
        # 作者 SVG 沿用原有几何进入上游动效系统。
        if diagram is None:
            shape.set("data-animate", "node")
    if diagram is not None and len(by_id) != len(diagram[COLLECTIONS[diagram["diagram_type"]][0]]):
        raise ValueError("编译前后的节点数量不一致")
    if set(roles) - set(by_id):
        raise ValueError("角色标注引用不存在的节点：" + ", ".join(sorted(set(roles) - set(by_id))))

    def owner(element):
        """找到拥有端点身份的原生关系分组。"""
        while element is not None:
            if element.get("data-edge-from") or element.get("data-vd-edge"):
                return element
            element = parents.get(element)
        return None

    # 关系身份和字段由原图取得，时序类型来自原生消息类型。
    metadata = {}
    if diagram is not None:
        metadata = {item["id"]: item for item in diagram.get(COLLECTIONS[diagram["diagram_type"]][1], [])}
    if family == "code-sequence" and diagram is not None:
        kinds = manifest.get("extensions", {}).get("messageKinds", {})
        if not isinstance(kinds, dict) or set(kinds) - set(metadata) or any(value not in {"sync", "return", "async", "self", "error", "timeout"} for value in kinds.values()):
            raise ValueError("extensions.messageKinds 须引用已有消息并使用明确的消息类型")
    # 每条关系只有一个被检查的真实几何对象。
    edges = {}
    for shape in root.iter():
        if tag(shape) not in {"path", "line", "polyline"}:
            continue
        # 原生标签分组的背景矩形不属于关系路径。
        relation = owner(shape)
        if relation is None:
            continue
        identity = relation.get("data-edge-id") or relation.get("id")
        if not identity or identity in edges:
            raise ValueError("每条关系必须有唯一编号及一条完整路径")
        # 作者 SVG 使用 DOM 端点；原生编译器使用语义端点。
        source = relation.get("data-edge-from") or relation.get("data-from")
        target = relation.get("data-edge-to") or relation.get("data-to")
        if source not in by_id or target not in by_id:
            raise ValueError(f"关系端点缺失：{identity}")
        shape.set("id", shape.get("id") or "edge-" + identity)
        shape.set("data-vd-edge", "transition" if family == "state-machine" else "message" if family == "code-sequence" else relation.get("data-vd-edge") or "relation")
        shape.set("data-from", by_id[source].get("id")); shape.set("data-to", by_id[target].get("id"))
        # 保留消息语义，不能把异步或返回统一成普通调用。
        if family == "code-sequence":
            kind = metadata.get(identity, {}).get("variant", "default")
            shape.set("data-vd-message-kind", relation.get("data-vd-message-kind") or manifest.get("extensions", {}).get("messageKinds", {}).get(identity) or {"return": "return", "dashed": "async"}.get(kind, "sync"))
        if diagram is None:
            relation.set("data-edge-id", identity); relation.set("data-edge-key", str(len(edges)))
            relation.set("data-edge-from", source); relation.set("data-edge-to", target)
            shape.set("data-animate", "edge")
        edges[identity] = (shape, relation)
    # 将原生标签绑定到自己的关系；没有补造或重写分支条件。
    for identity, (shape, relation) in edges.items():
        labels = [item for item in root.iter() if tag(item) == "text" and ((owner(item) is not None and (owner(item).get("data-edge-id") or owner(item).get("id")) == identity) or item.get("data-vd-edge-label") == shape.get("id"))]
        for index, label in enumerate(labels):
            label.set("id", label.get("id") or shape.get("id") + "-label" + ("-" + str(index) if index else ""))
            label.set("data-vd-edge-label", shape.get("id"))
        if labels and not relation.get("data-edge-label"):
            relation.set("data-edge-label", " / ".join("".join(label.itertext()).strip() for label in labels))
    if diagram is not None and len(edges) != len(metadata):
        raise ValueError("编译前后的关系数量不一致，拒绝交付缺少关系的图")
    # 时序生命线由原生参与者中心线生成；位置只用来识别既有线条。
    if family == "code-sequence" and diagram is not None:
        for identity, node in by_id.items():
            shape = next(item for item in node if item.get("data-vd-shape") is not None)
            center = float(shape.get("x")) + float(shape.get("width")) / 2
            matches = [item for item in root.iter() if tag(item) == "path" and owner(item) is None and re.fullmatch(r"M\s*" + re.escape(str(int(center)) if center.is_integer() else str(center)) + r"\s+[\d.]+\s+L\s*" + re.escape(str(int(center)) if center.is_integer() else str(center)) + r"\s+[\d.]+", item.get("d", ""))]
            if len(matches) != 1:
                raise ValueError(f"无法唯一绑定参与者生命线：{identity}")
            matches[0].set("data-vd-lifeline-for", node.get("id"))
    if family == "code-sequence" and diagram is not None:
        bind_sequence_geometry(root, by_id, edges, diagram)
    # 关键事实只能引用已经存在的可见目标。
    critical = {target for fact in manifest.get("criticalFacts", []) for target in fact["visibleIn"]}
    critical.update(target for question in manifest.get("questions", []) if question.get("priority") == "critical" for target in question["answeredBy"])
    for item in root.iter():
        if item.get("id") in critical:
            item.set("data-vd-critical", "")
    root.set("data-vd-zoom-target", "")
    root.set("data-animation", root.get("data-animation") or "trace")
    root.set("data-preset", root.get("data-preset") or "signal-flow")
    return ET.tostring(root, encoding="unicode")


def bind_sequence_geometry(root: ET.Element, nodes: dict, edges: dict, diagram: dict) -> None:
    """时序端点接触实际生命线或已声明执行条，不保留上游固定七像素空隙。"""
    # 参与者中心来自实际已绘制标题，消息顺序和纵坐标来自同一份源。
    centers = {}
    for identity, node in nodes.items():
        shape = next(item for item in node if item.get("data-vd-shape") is not None)
        centers[identity] = float(shape.get("x")) + float(shape.get("width")) / 2
    # 执行条完全采用作者给出的区间，不补造处理时长。
    activations = diagram.get("activations", [])
    for activation in activations:
        identity = activation["participant"]
        for item in root.iter():
            if tag(item) == "rect" and item.get("class") != "c-mask" and item.get("width") == "10" and float(item.get("x", "nan")) == centers[identity] - 5 and float(item.get("y", "nan")) == activation["from"] and float(item.get("height", "nan")) == activation["to"] - activation["from"]:
                item.set("data-vd-activation-for", nodes[identity].get("id"))
    for message in diagram["messages"]:
        shape = edges[message["id"]][0]
        # 固定上游的时序消息是水平路径；复杂自调用应使用作者 SVG。
        if not re.fullmatch(r"M [-\d.]+ [-\d.]+ L [-\d.]+ [-\d.]+", shape.get("d", "")):
            raise ValueError("时序端点接入点发生变化")
        direction = 1 if centers[message["to"]] >= centers[message["from"]] else -1
        endpoints = []
        for identity, side in [(message["from"], direction), (message["to"], -direction)]:
            active = any(item["participant"] == identity and item["from"] <= message["y"] <= item["to"] for item in activations)
            endpoints.append(centers[identity] + (side * 5 if active else 0))
        start, end = endpoints
        y = message["y"]
        shape.set("d", f"M {start:g} {y:g} L {end:g} {y:g}")
        shape.set("data-composition-points", f"{start:g},{y:g};{end:g},{y:g}")


def replace_once(document: str, original: str, replacement: str) -> str:
    """上游接入点变化时明确失败，不悄悄漏掉某项功能。"""
    if document.count(original) != 1:
        raise ValueError("原生接入点发生变化：" + original[:80])
    return document.replace(original, replacement, 1)


def compose(document: str, manifest: dict, diagram: dict | None, provenance: dict) -> str:
    """把完整原生查看器、公共画布、检查和交付清单组成单文件。"""
    # 单份原生文档拥有一幅完整图，可通过章节讲解多个阅读路径。
    views = manifest.get("views", [])
    if len(views) != 1 or views[0].get("role") != "primary":
        raise ValueError("原生图形文件须声明一个主要视图；多路径使用 meta.views 章节")
    view = views[0]
    # 原生图类必须与覆盖清单声明一致。
    if diagram is not None and view["family"] != FAMILIES[diagram["diagram_type"]]:
        raise ValueError("源图类型与覆盖清单不一致")
    # 上游英文页面会自动追加 Diagram；所有图类统一使用作者声明的完整标题。
    head, remainder = document.split("</head>", 1)
    head, title_count = re.subn(r"<title>[^<]*</title>", lambda _match: "<title>" + html.escape(manifest["title"]) + "</title>", head)
    if title_count != 1:
        raise ValueError("原生页面必须有且只有一个文档标题")
    document = head + "</head>" + remainder
    # 只替换那幅实际 SVG，完整原生脚本与控件继续沿用。
    svg_match = re.search(r"<svg\b.*?</svg>", document, re.S)
    if not svg_match:
        raise ValueError("绘图引擎没有输出 SVG")
    svg = bind_svg(svg_match.group(), view["family"], manifest, diagram)
    document = document[:svg_match.start()] + svg + document[svg_match.end():]
    # 当前主题变量保持与 HTML 公共外壳相同，不从预览文件读取。
    tokens = re.search(r":root\s*\{.*?\n\}", (CORE / "assets/shell/v1.css").read_text(), re.S).group()
    natural_width = parse_svg(svg).get("viewBox", "").split()
    if len(natural_width) != 4 or not all(math.isfinite(float(value)) for value in natural_width) or float(natural_width[2]) <= 0 or float(natural_width[3]) <= 0:
        raise ValueError("图形必须有有效的 viewBox")
    tokens += f"\n:root {{ /* 图形自然宽度用于窄屏横向阅读。 */ --vibe-diagram-natural-width: {float(natural_width[2])}px; }}"
    # 在初始化前载入覆盖清单及公共检查，下载的 HTML 才能完整重开。
    license_data = {"license": (ENGINE / "LICENSE").read_text(), "source": provenance["upstream"] + "@" + provenance["revision"]}
    def data_script(identity, value):
        """JSON 数据中的标签字符不能终止所在脚本。"""
        return '<script id="' + identity + '" type="application/json">' + json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c") + '</script>\n'
    document = document.replace("<html ", '<html data-vd-runtime="archify" ', 1)
    document = re.sub(r'  <!-- Async font load:.*?</noscript>\n', '', document, count=1, flags=re.S)
    document = document.replace("archify-theme", "vibe-diagram-theme").replace("archify-motion", "vibe-diagram-motion")
    document = document.replace("window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'", "'light'")
    # 标题与关键事实归属于同一主要视图，内部说明保持原有折叠层次。
    document = replace_once(document, '<div class="container">', '<div class="container" data-vd-artifact="1" id="' + html.escape(view["elementId"], quote=True) + '" data-vd-view="' + html.escape(view["id"], quote=True) + '" data-vd-family="' + html.escape(view["family"], quote=True) + '" data-vd-view-role="primary">')
    document = replace_once(document, '<div class="header">', '<div class="header" data-vd-title-region>')
    document = replace_once(document, '<h1>', '<h1 id="diagram-title" data-vd-view-title data-vd-critical>')
    document = replace_once(document, '<p class="subtitle">', '<p class="subtitle" id="diagram-summary" data-vd-summary data-vd-critical>')
    document = replace_once(document, '<div class="diagram-container"', '<div class="diagram-container" data-vd-content data-vd-viewport')
    document = replace_once(document, '<div class="diagram-nav', '<div data-vd-controls class="diagram-nav')
    # 所有适配脚本随 HTML 内嵌，不再依赖技能安装目录。
    assets = data_script("vibe-upstream-license", license_data) + data_script("vibe-diagram-manifest", manifest)
    assets += '<style data-vd-native-canvas>\n' + tokens + '\n' + (CANVAS / 'canvas.css').read_text() + '\n</style>\n'
    assets += '<script data-vd-native-canvas>\n' + (CANVAS / 'canvas.js').read_text() + '\n</script>\n'
    assets += '<script data-vd-shell="1">\n' + (CORE / 'assets/shell/v1.js').read_text() + '\n</script>\n'
    document = replace_once(document, '</head>', assets + '</head>')
    # 上游点击热区和动效克隆不是新的业务关系，不应继承检查身份。
    if document.count('var clone = shape.cloneNode(false);') != 7:
        raise ValueError('原生装饰几何接入点发生变化')
    document = document.replace('var clone = shape.cloneNode(false);', 'var clone = VibeDiagramCanvas.cloneDecoration(shape);')
    # 普通图片在上游完成临时状态清理后加入原背景和完整标题。
    document = replace_once(document, '        return {\n          svgString: new XMLSerializer().serializeToString(clone),\n          width: vb.width * scale,\n          height: vb.height * scale,', '        // 用公共主题装饰已清理的图形，不改变关系或原生几何。\n        var vibeSize = VibeDiagramCanvas.decorateExport(clone, vb, scale, opts);\n        return {\n          svgString: new XMLSerializer().serializeToString(clone),\n          width: vibeSize.width,\n          height: vibeSize.height,')
    document = replace_once(document, 'serializeSvg(sourceScale, { routeSnapshot: routeSnapshot, reachSnapshot: reachSnapshot })', 'serializeSvg(sourceScale, { routeSnapshot: routeSnapshot, reachSnapshot: reachSnapshot, diagramOnly: true })')
    document = replace_once(document, 'var scale = Math.min(1, 1280 / vb.width);\n        var data = serializeSvg(scale);', 'var scale = Math.min(1, 1280 / vb.width);\n        var data = serializeSvg(scale, { diagramOnly: true });')
    document = replace_once(document, '              ctx.fillStyle = bg;\n              ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);', '              // 分享图与页面使用同一主题背景。\n              VibeDiagramCanvas.paintShareBackground(ctx, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);')
    document = document.replace('var family = "\'JetBrains Mono\', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";', 'var family = getComputedStyle(document.body).fontFamily;')
    document = document.replace('ctx.font = "600 12px \'JetBrains Mono\', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";', 'ctx.font = "600 12px " + getComputedStyle(document.body).fontFamily;')
    document = replace_once(document, r"return title.replace(/[^a-z0-9_\-]+/gi, '-')", r"return title.replace(/[^\p{L}\p{N}_\-]+/gu, '-')")
    # HTML 快照在原生初始化之前保存，清单和公共检查已经在 head 中。
    document = replace_once(document, '    var Archify = {};', "    // 保存完整初始化前文档，防止下载时混入临时界面。\n    var vibeAuthoredHtml = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;\n    var Archify = {};")
    # 下载 HTML 是公共交付能力，原生图片、路径和视频入口保持完整。
    label = '交互 HTML' if manifest['language'].startswith('zh') else 'Interactive HTML'
    hint = '离线打开，保留完整交互' if manifest['language'].startswith('zh') else 'Offline, with full interaction'
    document = replace_once(document, '<button data-format="svg" type="button"', '<button data-action="vibe-html" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>' + label + '</strong><small class="hint">' + hint + '</small></span></button>\n          <button data-format="svg" type="button"')
    document = replace_once(document, "      menu.addEventListener('click', function (e) {\n        var routeShareCardBtn", "      menu.addEventListener('click', function (e) {\n        // 交互 HTML 与图片入口分开，保留原生导出语义。\n        if (e.target.closest('button[data-action=\"vibe-html\"]')) { close(true); download(new Blob([vibeAuthoredHtml], { type: 'text/html;charset=utf-8' }), diagramFilename() + '.html'); return; }\n        var routeShareCardBtn")
    return document


def build(source: Path, manifest: dict, *, svg_mode: bool = False, summary: str = "") -> str:
    """先完成引擎与静态检查，再由命令入口写入独立文件。"""
    # 第三方源被篡改时，不能拿不明版本继续生成。
    provenance = verify_engine()
    with tempfile.TemporaryDirectory(prefix="vibe-diagram-engine-") as directory:
        # 原生编译的中间结果位于独立临时目录。
        work = Path(directory)
        output = work / "rendered.html"
        diagram = None
        if svg_mode:
            if not summary.strip():
                raise ValueError("作者 SVG 需要 --summary 说明业务结论或规则")
            # 只传当前 SVG 与页面文字，不重复构造节点和关系。
            payload = {"svg": source.read_text(), "title": manifest["title"], "subtitle": summary, "locale": manifest["language"], "visualPreset": "signal-flow", "guidedViews": manifest.get("extensions", {}).get("guidedViews", [])}
            parse_svg(payload["svg"])
            request = work / "request.json"
            request.write_text(json.dumps(payload, ensure_ascii=False))
            node_command([str(CORE / "scripts/vibe_diagram_svg.mjs"), str(request), str(output)], work)
        else:
            diagram = read_json(source)
            kind = diagram.get("diagram_type")
            if kind not in FAMILIES:
                raise ValueError("不支持的原生图类；实体数量关系使用作者 SVG，不使用 dataflow 冒充")
            meta = diagram.get("meta", {})
            if meta.get("title") != manifest.get("title") or meta.get("locale") != manifest.get("language"):
                raise ValueError("图形标题、语言须与覆盖清单一致")
            if not meta.get("subtitle", "").strip():
                raise ValueError("meta.subtitle 须说明业务结论或规则")
            # 绘图不自动访问 Git 或网络；证据引用由已有覆盖清单保留。
            if meta.get("repository"):
                raise ValueError("绘图命令不执行仓库校验；请把已核实来源写入覆盖清单 evidence")
            for name in COLLECTIONS[kind]:
                identities = [item.get("id") for item in diagram.get(name, [])]
                if any(not isinstance(item, str) or not item for item in identities) or len(set(identities)) != len(identities):
                    raise ValueError(f"{name} 必须使用稳定且唯一的编号")
            # URL 品牌图标需要外部读取，当前离线生成入口只使用内置或内嵌图标。
            for item in diagram.get(COLLECTIONS[kind][0], []):
                if re.search(r'https?://', json.dumps(item.get('brand', {}))):
                    raise ValueError("离线生成不抓取远程品牌图标，请使用内置品牌或内嵌图形")
            meta.setdefault("animation", "trace"); meta.setdefault("visual_preset", "signal-flow")
            # 不允许通过 advisory 绕过上游布局检查。
            if meta.get("quality_gates") == "advisory":
                raise ValueError("交付图不能关闭布局质量门禁")
            request = work / "diagram.json"
            request.write_text(json.dumps(diagram, ensure_ascii=False, allow_nan=False))
            node_command([str(ENGINE / f"renderers/{kind}/render-{kind}.mjs"), str(request), str(output)], work)
            node_command([str(ENGINE / "scripts/check-render-output.mjs"), str(output)], work)
        return compose(output.read_text(), manifest, diagram, provenance)
