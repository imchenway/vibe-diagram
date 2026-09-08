(() => {
  "use strict";

  // 单元素和批量选择只操作当前文档。
  const $ = (selector, root = document) => root.querySelector(selector);
  // 批量结果转成数组以便按视图过滤。
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  // 检查记录与用户阅读层分开保存。
  const auditOutput = () => $("[data-vd-audit-output]");
  // 自动排版失败不能被后续几何通过覆盖。
  let layoutIssues = [];
  // 中英文控件沿用外壳语言；其他语言可由作者提供完整词条。
  const zh = document.documentElement.lang.toLowerCase().startsWith("zh");
  // 统一交互文案避免每种图重复维护按钮。
  const copy = {
    clear: zh ? "取消高亮" : "Clear highlight", print: zh ? "打印整页" : "Print page",
    png: zh ? "导出 PNG" : "Export PNG", svg: zh ? "导出 SVG" : "Export SVG",
    exported: zh ? "图片已生成" : "Image ready", failed: zh ? "操作未完成：" : "Could not complete: ",
    selected: zh ? "已突出当前图中直接相关的对象与连线。" : "Directly connected objects and relations highlighted.",
    compare: zh ? "修改前后对比" : "Before and after", added: zh ? "新增" : "Added", removed: zh ? "删除" : "Removed",
    changed: zh ? "内容变化" : "Content changed", moved: zh ? "手工位置或走线变化" : "Authored geometry changed",
    unchanged: zh ? "未发现内容或手工几何变化。" : "No content or authored geometry changes.",
    scope: zh ? "按稳定编号比较；自动排版不计作内容变化。" : "Matched by stable identity; automatic layout is not a content change.",
    imageScope: zh ? "图片包含本图、标题、摘要和图注；交互详情保留在 HTML 中。" : "Images include this view, title, summary and notes; interactive details remain in HTML.",
    unsupported: zh ? "此视图包含图片无法完整保留的内容，请使用打印整页或原 HTML。" : "This view contains content an image cannot preserve completely. Print the page or share the HTML.",
    diagnose: zh ? "当前图需要修正" : "This diagram needs repair", locate: zh ? "定位" : "Locate"
  };

  function zoomTargets() {
    const explicit = $$('[data-vd-zoom-target]');
    return explicit.length ? explicit : $$('[data-vd-view]');
  }

  function viewportFor(target) {
    return target.closest('[data-vd-viewport]') || target.parentElement;
  }

  function naturalWidth(target) {
    const previous = target.style.zoom;
    target.style.zoom = "1";
    const width = Math.max(target.scrollWidth, target.getBoundingClientRect().width, 1);
    target.style.zoom = previous;
    return width;
  }

  function applyZoom(request) {
    let allApplied = true;
    zoomTargets().forEach((target) => {
      const viewport = viewportFor(target);
      if (!viewport) return;
      const width = naturalWidth(target);
      const available = Math.max(viewport.clientWidth, 1);
      const requested = request === "fit" ? Math.min(1, available / width) : Number(request);
      const applied = Math.max(0.75, Math.min(1, requested || 1));
      // 所有缩放档位都应允许视图内横滚，不能把宽图撑出页面。
      const overflow = width * applied > available + 1;
      target.style.zoom = String(applied);
      target.dataset.vdAppliedZoom = String(applied);
      viewport.style.overflowX = overflow ? "auto" : "visible";
      viewport.dataset.vdHorizontalOverflow = String(overflow);
      if (request === "fit" && requested < 0.75) allApplied = false;
    });

    $$('[data-vd-zoom]').forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.vdZoom === request));
    });
    const controls = $('[data-vd-controls]');
    if (controls) {
      controls.dataset.vdZoomRequest = request;
      controls.dataset.vdZoomFullyApplied = String(allApplied);
    }
    return allApplied;
  }

  function bindZoom() {
    $$('[data-vd-zoom]').forEach((button) => {
      button.addEventListener("click", () => applyZoom(button.dataset.vdZoom || "fit"));
    });
    let frame = 0;
    window.addEventListener("resize", () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const request = $('[data-vd-controls]')?.dataset.vdZoomRequest || "fit";
        applyZoom(request);
      });
    });
    applyZoom("fit");
  }

  function bindDetails() {
    // HTML 和 SVG 触发器都应能在关闭后取回焦点。
    let returnFocus = null;
    $$('[data-vd-detail-trigger]').forEach((trigger) => {
      // SVG 详情节点没有原生按钮行为，补齐键盘入口。
      const native = trigger.matches("button, a[href], input");
      if (!native) { trigger.setAttribute("tabindex", "0"); trigger.setAttribute("role", "button"); }
      // 同一个打开函数接收鼠标与键盘，避免两条行为分叉。
      const open = (event) => {
        if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
        const targetId = trigger.getAttribute("data-vd-detail-trigger");
        const dialog = targetId ? document.getElementById(targetId) : null;
        if (!(dialog instanceof HTMLDialogElement)) return;
        event.preventDefault();
        returnFocus = trigger;
        dialog.showModal();
        $('[data-vd-detail-close]', dialog)?.focus();
      };
      trigger.addEventListener("click", open);
      if (!native) trigger.addEventListener("keydown", open);
    });
    $$('dialog[data-vd-detail-for]').forEach((dialog) => {
      $$('[data-vd-detail-close]', dialog).forEach((button) => button.addEventListener("click", () => dialog.close()));
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener("close", () => {
        if (returnFocus?.isConnected && typeof returnFocus.focus === "function") returnFocus.focus();
        returnFocus = null;
      });
    });
  }

  const rect = (element) => element.getBoundingClientRect();
  const visible = (element) => {
    const style = getComputedStyle(element);
    const box = rect(element);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    if ((box.width < 1 || box.height < 1) && !(element instanceof SVGGeometryElement && element.getTotalLength() > 0)) return false;
    if (element.closest('details:not([open]), dialog:not([open]), [hidden], [aria-hidden="true"]')) return false;
    return true;
  };
  const intersects = (a, b, pad = 1) =>
    a.left + pad < b.right && a.right - pad > b.left && a.top + pad < b.bottom && a.bottom - pad > b.top;
  const contains = (outer, inner, tolerance = 1) =>
    inner.left >= outer.left - tolerance && inner.right <= outer.right + tolerance &&
    inner.top >= outer.top - tolerance && inner.bottom <= outer.bottom + tolerance;

  function screenPoint(path, length) {
    if (!(path instanceof SVGGeometryElement) || typeof path.getPointAtLength !== "function") return null;
    const point = path.getPointAtLength(length);
    const matrix = path.getScreenCTM();
    if (!matrix) return null;
    return new DOMPoint(point.x, point.y).matrixTransform(matrix);
  }

  // 按真实 SVG 轮廓测量端点距离，避免把菱形和椭圆的包围框当成边界。
  function boundaryDistance(point, element) {
    if (!point) return Infinity;
    const shape = element.matches("[data-vd-lifeline-for]") ? element : $('[data-vd-shape]', element);
    if (shape instanceof SVGGeometryElement) {
      const length = shape.getTotalLength();
      let distance = Infinity;
      for (let offset = 0; offset <= length; offset += Math.min(4, length || 4)) {
        const sample = screenPoint(shape, offset);
        if (sample) distance = Math.min(distance, Math.hypot(point.x - sample.x, point.y - sample.y));
      }
      return distance;
    }
    const box = rect(element), outside = Math.hypot(Math.max(box.left - point.x, 0, point.x - box.right), Math.max(box.top - point.y, 0, point.y - box.bottom));
    return outside || Math.min(Math.abs(point.x - box.left), Math.abs(point.x - box.right), Math.abs(point.y - box.top), Math.abs(point.y - box.bottom));
  }

  // 诊断带真实测量值与修复方向，方向不等于保证修复成功。
  function issue(code, element, detail = "", measured = {}) {
    return {
      code,
      id: element?.id || element?.getAttribute?.("data-vd-view") || "",
      detail,
      measured,
      hint: /anchored/.test(code) ? (zh ? "让端点接触真实节点边界或生命线。" : "Anchor the endpoint to its node or lifeline.")
        : /collision|overlap|through/.test(code) ? (zh ? "增大留白、移动标签或重新走线，保留全部关系后复查。" : "Add space, move the label or reroute, then check again without removing relations.")
        : (zh ? "检查该元素的可见性、内容范围与归属。" : "Check this element's visibility, bounds and ownership.")
    };
  }

  // 面向读者解释错误，稳定错误码留在结构化检查记录中。
  function diagnosticName(code) {
    const names = { "node-overlap": "节点互相遮挡", "edge-through-node": "连线穿过其他节点", "edge-label-route-collision": "标签遮住其他连线", "edge-label-node-collision": "标签遮住节点", "edge-label-collision": "关系标签互相遮挡", "edge-start-not-anchored": "连线起点未接好", "edge-end-not-anchored": "连线终点未接好", "automatic-layout-failed": "自动排版未完成", "page-horizontal-overflow": "图形撑出了页面", "node-outside-view": "节点超出图形范围", "group-clips-node": "节点超出所属边界", "product-summary-not-visible": "业务摘要不可见", "critical-target-not-primary-visible": "关键事实未显示在主要视图" };
    return zh ? names[code] || "内容或排版需要检查" : code.replaceAll("-", " ");
  }

  function authoredBounds(element, fallback) {
    const svg = element.closest("svg");
    if (svg) return rect(svg);
    const target = element.closest("[data-vd-zoom-target]");
    if (!target) return fallback;
    const box = rect(target);
    const zoom = Number.parseFloat(getComputedStyle(target).zoom) || 1;
    return {
      left: box.left,
      top: box.top,
      right: box.left + Math.max(box.width, target.scrollWidth * zoom),
      bottom: box.top + Math.max(box.height, target.scrollHeight * zoom)
    };
  }

  function auditView(view) {
    const issues = [];
    // 零长度路径或隐藏标记不能因过滤不可见元素而漏过检查。
    $$('[data-vd-node], [data-vd-edge], [data-vd-edge-label]', view).forEach(element => {
      if (!visible(element)) issues.push(issue("semantic-element-not-visible", element));
    });
    const viewRect = rect(view);
    const nodes = $$('[data-vd-node]', view).filter(visible);
    const groups = $$('[data-vd-group]', view).filter(visible);
    const labels = $$('[data-vd-edge-label]', view).filter(visible);
    const edges = $$('[data-vd-edge]', view).filter(visible);

    nodes.forEach((node) => {
      const box = rect(node);
      if (!contains(authoredBounds(node, viewRect), box, 2)) issues.push(issue("node-outside-view", node));
      if (node.scrollWidth > node.clientWidth + 2 || node.scrollHeight > node.clientHeight + 2) {
        issues.push(issue("node-content-overflow", node));
      }
      // SVG 没有 HTML 的 scrollWidth 溢出信号，单独检查文字与主体范围。
      const shape = $('[data-vd-shape]', node);
      if (shape) $$('text', node).forEach(text => {
        if (!contains(rect(shape), rect(text), 1)) issues.push(issue("node-content-overflow", node, text.textContent, { shape: rect(shape).toJSON(), text: rect(text).toJSON(), tolerance: 1 }));
      });
    });

    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = rect(nodes[i]);
        const b = rect(nodes[j]);
        if (intersects(a, b, 2)) issues.push(issue("node-overlap", nodes[i], nodes[j].id || "anonymous", {
          overlapWidth: Math.min(a.right, b.right) - Math.max(a.left, b.left), overlapHeight: Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top), tolerance: 2
        }));
      }
    }

    groups.forEach((group) => {
      const box = rect(group);
      $$('[data-vd-node]', group).filter(visible).forEach((node) => {
        if (!contains(box, rect(node), 2)) issues.push(issue("group-clips-node", group, node.id || "anonymous"));
      });
      // 扁平 SVG 中的归属由稳定编号标记，不能因没有 DOM 嵌套而漏检。
      nodes.filter(node => node.dataset.vdMemberOf === group.id).forEach(node => {
        if (!contains(box, rect(node), 2)) issues.push(issue("group-clips-node", group, node.id));
      });
    });

    labels.forEach((label, index) => {
      const box = rect(label);
      if (label.scrollWidth > label.clientWidth + 2 || label.scrollHeight > label.clientHeight + 2) {
        issues.push(issue("edge-label-overflow", label));
      }
      nodes.forEach((node) => {
        if (intersects(box, rect(node), 1)) issues.push(issue("edge-label-node-collision", label, node.id || "anonymous"));
      });
      labels.slice(index + 1).forEach((other) => {
        if (intersects(box, rect(other), 1)) issues.push(issue("edge-label-collision", label, other.id || "anonymous"));
      });
    });

    edges.forEach((edge) => {
      const from = document.getElementById(edge.getAttribute("data-from") || "");
      const to = document.getElementById(edge.getAttribute("data-to") || "");
      if (!from || !to) return;
      if (edge instanceof SVGGeometryElement && typeof edge.getTotalLength === "function") {
        const length = edge.getTotalLength();
        const start = screenPoint(edge, 0);
        const end = screenPoint(edge, length);
        // 时序消息锚定到参与者生命线，而不是顶部标题框。
        const anchor = node => view.dataset.vdFamily === "code-sequence"
          ? $$('[data-vd-lifeline-for]', view).find(line => line.dataset.vdLifelineFor === node.id) || node : node;
        const startDistance = boundaryDistance(start, anchor(from)), endDistance = boundaryDistance(end, anchor(to));
        if (startDistance > 6) issues.push(issue("edge-start-not-anchored", edge, from.id, { distance: startDistance, tolerance: 6 }));
        if (endDistance > 6) issues.push(issue("edge-end-not-anchored", edge, to.id, { distance: endDistance, tolerance: 6 }));
        const excluded = new Set([from, to]);
        for (let sample = 10; sample < length - 10; sample += 8) {
          const point = screenPoint(edge, sample);
          if (!point) break;
          const hit = nodes.find((node) => !excluded.has(node) && contains(rect(node), {
            left: point.x, right: point.x, top: point.y, bottom: point.y
          }, -2));
          if (hit) {
            issues.push(issue("edge-through-node", edge, hit.id || "anonymous", { x: point.x, y: point.y, inset: 2 }));
            break;
          }
          // 标签只能靠近自己的关系；其他线路不能穿过标签正文。
          const label = labels.find(item => item.dataset.vdEdgeLabel !== edge.id && contains(rect(item), {
            left: point.x, right: point.x, top: point.y, bottom: point.y
          }, -1));
          if (label) {
            issues.push(issue("edge-label-route-collision", label, edge.id, { x: point.x, y: point.y, inset: 1 }));
            break;
          }
        }
      }
    });

    return issues;
  }

  function auditAll() {
    // 每次重测当前画面，并保留尚未修复的自动布局错误。
    const issues = [...layoutIssues];
    $$('[data-vd-view]').filter(visible).forEach((view) => issues.push(...auditView(view)));
    const summary = $('[data-vd-summary]');
    if (!summary || !visible(summary)) issues.push(issue("product-summary-not-visible", summary));
    $$('[data-vd-critical]').forEach((element) => {
      if (!visible(element) || !element.closest('[data-vd-view-role="primary"]')) {
        issues.push(issue("critical-target-not-primary-visible", element));
      }
    });
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth + 2) {
      issues.push(issue("page-horizontal-overflow", document.documentElement));
    }
    const controls = $('[data-vd-controls]');
    if (!controls || $$('[data-vd-zoom]', controls).length !== 4) issues.push(issue("zoom-controls-incomplete", controls));

    const report = {
      status: issues.length ? "failed" : "passed",
      viewport: { width: window.innerWidth, height: window.innerHeight },
      issues
    };
    const output = auditOutput();
    if (output) {
      output.setAttribute("data-vd-audit-status", report.status);
      output.textContent = JSON.stringify(report);
    }
    document.documentElement.setAttribute("data-vd-audit-status", report.status);
    showDiagnostics(issues);
    return report;
  }

  // 安全创建阅读控件，外部标签始终作为文字处理。
  function button(text, action) {
    const element = document.createElement("button");
    element.type = "button"; element.textContent = text; element.addEventListener("click", action);
    return element;
  }

  // 检查错误按需出现，不让内部记录占据正常图的主阅读层。
  function showDiagnostics(issues) {
    let panel = $('[data-vd-diagnostics]');
    if (!issues.length) { panel?.remove(); return; }
    if (!panel) { panel = document.createElement("details"); panel.dataset.vdDiagnostics = ""; $('[data-vd-content]').after(panel); }
    // 重测时保留用户的展开状态。
    const summary = document.createElement("summary"), list = document.createElement("ul");
    summary.textContent = copy.diagnose + " (" + issues.length + ")";
    issues.forEach(item => {
      const li = document.createElement("li");
      li.textContent = [diagnosticName(item.code), item.id, item.detail, item.hint].filter(Boolean).join(" · ");
      li.append(button(copy.locate, () => { const target = document.getElementById(item.id); target?.scrollIntoView({ block: "center", inline: "center" }); target?.focus(); }));
      list.append(li);
    });
    panel.replaceChildren(summary, list);
  }

  // 只高亮作者已画出的直接关联，不推断系统影响。
  function highlight(view, id) {
    const items = $$('[data-vd-node], [data-vd-edge], [data-vd-edge-label]', view);
    const edges = $$('[data-vd-edge]', view).filter(e => e.id === id || e.dataset.from === id || e.dataset.to === id);
    const related = new Set([id, ...edges.flatMap(e => [e.id, e.dataset.from, e.dataset.to])]);
    items.forEach(item => {
      if (!id) delete item.dataset.vdEmphasis;
      else item.dataset.vdEmphasis = related.has(item.id) || related.has(item.dataset.vdEdgeLabel) ? "related" : "quiet";
      if (item.hasAttribute("data-vd-node")) item.setAttribute("aria-pressed", String(item.id === id));
    });
    const status = $('[data-vd-view-status]', view);
    if (status) status.textContent = id ? copy.selected : "";
  }

  // 差异数据由本地命令从两份 HTML 解析而来，旧脚本不会载入页面。
  function bindComparison() {
    const source = document.getElementById("vibe-diagram-comparison");
    if (!source) return;
    const data = JSON.parse(source.textContent), panel = document.createElement("details"), summary = document.createElement("summary"), note = document.createElement("p"), list = document.createElement("ul");
    panel.dataset.vdComparison = ""; summary.textContent = copy.compare + " (" + data.changes.length + ")";
    note.textContent = copy.scope;
    data.changes.forEach(change => {
      const li = document.createElement("li");
      li.textContent = copy[change.kind] + " · " + change.label;
      if (change.beforeLabel && change.afterLabel && change.beforeLabel !== change.afterLabel) li.append(document.createTextNode(" · " + change.beforeLabel + " → " + change.afterLabel));
      // 完整字段差异放在二级详情，主阅读层不展示内部数据格式。
      const detail = document.createElement("details"), caption = document.createElement("summary"), content = document.createElement("pre");
      caption.textContent = zh ? "查看详细变化" : "Inspect the change";
      content.textContent = (change.before || "∅") + "\n→\n" + (change.after || "∅"); detail.append(caption, content); li.append(detail);
      const target = document.getElementById(change.id);
      if (target) li.append(button(copy.locate, () => { target.scrollIntoView({ block: "center", inline: "center" }); const view = target.closest("[data-vd-view]"); if (view && target.matches("[data-vd-node], [data-vd-edge]")) highlight(view, target.id); target.focus(); }));
      list.append(li);
    });
    if (!data.changes.length) note.textContent += " " + copy.unchanged;
    panel.append(summary, note, list); $('[data-vd-content]').before(panel);
  }

  // 图片范围必须完整；HTML 控件、多个 SVG 或未声明的外部图注不静默丢弃。
  function exportSource(view) {
    const svgs = $$('svg', view).filter(svg => !svg.parentElement.closest("svg"));
    if (svgs.length !== 1 || $('foreignObject, image, script', svgs[0])) throw new Error(copy.unsupported);
    const svg = svgs[0];
    const otherText = $$('*', view).some(element => !element.closest("svg, [data-vd-view-tools], [data-vd-view-title], [data-vd-export-note], dialog") &&
      Array.from(element.childNodes).some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()));
    if (otherText || $$('input, select, textarea, table, img', view).length) throw new Error(copy.unsupported);
    return svg;
  }

  // 导出时临时取消阅读状态，再内联计算样式；操作同步完成后立即恢复。
  function cleanSVG(svg) {
    const marked = $$('[data-vd-emphasis]', svg), saved = marked.map(element => element.dataset.vdEmphasis);
    marked.forEach(element => delete element.dataset.vdEmphasis);
    try {
      const clone = svg.cloneNode(true), originals = [svg, ...$$('*', svg)], copies = [clone, ...$$('*', clone)];
      // 仅导出 SVG 可绘制属性，避免把页面布局和交互效果带入图片。
      const properties = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity", "font-family", "font-size", "font-weight", "font-style", "font-stretch", "font-variant", "letter-spacing", "word-spacing", "text-decoration", "text-anchor", "dominant-baseline", "paint-order", "marker-start", "marker-mid", "marker-end"];
      // 公共箭头可能定义在另一幅 SVG，独立导出时带上其真实定义。
      const definitions = document.createElementNS("http://www.w3.org/2000/svg", "defs"), included = new Set();
      originals.forEach(element => properties.forEach(property => {
        const match = getComputedStyle(element).getPropertyValue(property).match(/url\(["']?[^)"']*#([^)'"\s]+)/);
        if (!match || included.has(match[1])) return;
        const reference = document.getElementById(match[1]);
        if (!reference || svg.contains(reference)) return;
        if (!reference.matches("marker, clipPath, linearGradient, radialGradient, pattern")) throw new Error(copy.unsupported);
        included.add(match[1]);
        const duplicated = reference.cloneNode(true);
        definitions.append(duplicated); originals.push(reference, ...$$('*', reference)); copies.push(duplicated, ...$$('*', duplicated));
      }));
      if (definitions.childNodes.length) clone.prepend(definitions);
      // 内嵌字体也随图片保存，避免独立 SVG 换字体后文字撑出节点。
      const fonts = Array.from(document.styleSheets).flatMap(sheet => Array.from(sheet.cssRules).filter(rule => rule.type === CSSRule.FONT_FACE_RULE).map(rule => rule.cssText));
      if (fonts.length) { const style = document.createElementNS("http://www.w3.org/2000/svg", "style"); style.textContent = fonts.join("\n"); clone.prepend(style); }
      originals.forEach((element, index) => {
        const style = getComputedStyle(element), target = copies[index];
        target.removeAttribute("style"); target.removeAttribute("tabindex"); target.removeAttribute("role"); target.removeAttribute("aria-pressed");
        Array.from(target.attributes).filter(a => a.name.startsWith("on") || a.name.startsWith("data-vd-")).forEach(a => target.removeAttribute(a.name));
        properties.forEach(property => target.style.setProperty(property, style.getPropertyValue(property).replace(/url\(["']?[^)"']*#([^)'"\s]+)["']?\)/g, "url(#$1)")));
      });
      return clone;
    } finally { marked.forEach((element, index) => { element.dataset.vdEmphasis = saved[index]; }); }
  }

  // 包含标题、摘要和明确图注的 SVG 图片；保持原始图形的字号。
  async function exportBlob(view, format) {
    await (document.fonts?.ready || Promise.resolve());
    if (!["svg", "png"].includes(format)) throw new Error("Unsupported image format");
    if (layoutIssues.length || auditView(view).length) throw new Error(zh ? "请先修正当前图的排版问题。" : "Repair the view before exporting.");
    const svg = exportSource(view), clone = cleanSVG(svg), bounds = svg.viewBox.baseVal;
    const width = Math.max(600, bounds.width || svg.getBBox().width), graphHeight = bounds.height || svg.getBBox().height;
    const canvas = document.createElement("canvas"), context = canvas.getContext("2d");
    if (!context) throw new Error(zh ? "浏览器无法创建图片画布。" : "Canvas is unavailable.");
    context.font = "16px sans-serif";
    // 按实际字宽换行，中文无空格文本同样适用。
    const lines = [];
    [$('[data-vd-view-title]', view)?.textContent, $('[data-vd-summary]')?.textContent, ...$$('[data-vd-export-note]', view).map(e => e.textContent)].filter(Boolean).forEach(text => {
      let line = "";
      for (const character of text.trim()) {
        if (context.measureText(line + character).width > width - 64) { lines.push(line); line = ""; }
        line += character;
      }
      if (line) lines.push(line);
    });
    const header = 32 + lines.length * 26, height = header + graphHeight + 32;
    // 外层 SVG 自带白底和说明；内层保留原始 viewBox，包括负坐标路线。
    const ns = "http://www.w3.org/2000/svg", image = document.createElementNS(ns, "svg"), background = document.createElementNS(ns, "rect");
    image.setAttribute("xmlns", ns); image.setAttribute("width", width); image.setAttribute("height", height); image.setAttribute("viewBox", "0 0 " + width + " " + height);
    Object.entries({ width: "100%", height: "100%", fill: "white" }).forEach(([key, value]) => background.setAttribute(key, value)); image.append(background);
    lines.forEach((line, index) => {
      const text = document.createElementNS(ns, "text");
      Object.entries({ x: 32, y: 30 + index * 26, "font-family": "sans-serif", "font-size": 16, fill: "#10243a" }).forEach(([key, value]) => text.setAttribute(key, value)); text.textContent = line; image.append(text);
    });
    clone.setAttribute("x", 0); clone.setAttribute("y", header); clone.setAttribute("width", width); clone.setAttribute("height", graphHeight); image.append(clone);
    const blob = new Blob([new XMLSerializer().serializeToString(image)], { type: "image/svg+xml;charset=utf-8" });
    if (format === "svg") return blob;
    // 限制总像素避免浏览器内存爆炸；大图通过分视图保留可读字号。
    const scale = Math.min(2, Math.sqrt(16000000 / (width * height)));
    if (scale < 0.75 || width * scale > 16000 || height * scale > 16000) throw new Error(zh ? "图片过大，请分图或导出 SVG。" : "Image too large; split the view or export SVG.");
    canvas.width = Math.ceil(width * scale); canvas.height = Math.ceil(height * scale);
    const url = URL.createObjectURL(blob), bitmap = new Image();
    try {
      await new Promise((resolve, reject) => { bitmap.onload = resolve; bitmap.onerror = () => reject(new Error(zh ? "图片解码失败。" : "Image decoding failed.")); bitmap.src = url; });
      context.scale(scale, scale); context.drawImage(bitmap, 0, 0);
      return await new Promise((resolve, reject) => canvas.toBlob(result => result ? resolve(result) : reject(new Error(zh ? "图片生成失败。" : "Image encoding failed.")), "image/png"));
    } finally { URL.revokeObjectURL(url); }
  }

  // 用户主动点击时下载本地图片，并在当前视图内反馈失败。
  async function download(view, format) {
    const status = $('[data-vd-view-status]', view);
    try {
      const blob = await exportBlob(view, format), url = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = url; link.download = (view.dataset.vdView || "diagram") + "." + format; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000); status.textContent = copy.exported;
    } catch (error) { status.textContent = copy.failed + error.message; }
  }

  // 为所有图复用关联阅读和导出；原型与比较表保留整页打印。
  function bindReading() {
    $$('[data-vd-view]').forEach(view => {
      const toolbar = document.createElement("div"), status = document.createElement("p");
      toolbar.dataset.vdViewTools = ""; status.dataset.vdViewStatus = ""; status.setAttribute("role", "status");
      if ($('[data-vd-node]', view)) toolbar.append(button(copy.clear, () => highlight(view, "")));
      try { exportSource(view); toolbar.append(button(copy.svg, () => download(view, "svg")), button(copy.png, () => download(view, "png"))); toolbar.title = copy.imageScope; }
      catch { toolbar.title = copy.unsupported; }
      toolbar.append(button(copy.print, () => window.print()), status); view.append(toolbar);
      $$('[data-vd-node]', view).forEach(node => {
        // 已有详情或原生控件维持其本来操作，不覆盖作者的点击语义。
        if (node.hasAttribute("data-vd-detail-trigger") || node.matches("button, input, a") || $("button, input, a", node)) return;
        node.setAttribute("tabindex", "0"); node.setAttribute("role", "button"); node.setAttribute("aria-pressed", "false"); node.setAttribute("aria-label", node.textContent.trim());
        const select = () => highlight(view, node.getAttribute("aria-pressed") === "true" ? "" : node.id);
        node.addEventListener("click", select);
        node.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(); } });
      });
      view.addEventListener("keydown", event => { if (event.key === "Escape") highlight(view, ""); });
    });
    try { bindComparison(); }
    catch (error) { layoutIssues.push(issue("comparison-data-invalid", document.getElementById("vibe-diagram-comparison"), error.message)); }
  }

  // 浏览器记录以候选标识绑定独立磁盘文件；最终 SHA-256 由交付命令核对。
  function receipt() {
    const candidate = $('meta[name="vibe-diagram-candidate"]')?.content;
    if (!candidate) throw new Error("请先使用 prepare 生成独立候选文件。");
    return { candidate, url: location.href, ...auditAll() };
  }

  // 对外提供当前画面的检查和图片生成，供真实浏览器验收使用。
  globalThis.VibeDiagramQuality = { auditAll, applyZoom, receipt, exportBlob, highlight };

  // 等待整个 HTML 解析，确保文末的差异数据也已存在。
  const ready = Promise.all([document.fonts?.ready || Promise.resolve(), document.readyState === "loading" ? new Promise(resolve => document.addEventListener("DOMContentLoaded", resolve, { once: true })) : Promise.resolve()]);
  ready.then(() => {
    layoutIssues = globalThis.VibeDiagramLayout?.run() || [];
    bindZoom();
    bindDetails();
    bindReading();
    requestAnimationFrame(() => requestAnimationFrame(auditAll));
  });
})();
