(() => {
  "use strict";

  // 单元素和批量选择只操作当前文档。
  const $ = (selector, root = document) => root.querySelector(selector);
  // 批量结果转成数组以便按视图过滤。
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  // 检查记录与用户阅读层分开保存。
  const auditOutput = () => $("[data-vd-audit-output]");
  // 公共交付数据损坏时不能被几何检查覆盖。
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

  // 绑定详情打开关闭与焦点返回。
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

  // 把路径位置转换为真实屏幕坐标。
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
    const shape = element.matches("[data-vd-lifeline-for], [data-vd-activation-for]") ? element : $('[data-vd-shape]', element);
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

  // 读取作者内容的完整边界，保留宽图横滚空间。
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

  // 检查真实节点、关系、标签和端点几何。
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
      if (!(node instanceof SVGGraphicsElement) && (node.scrollWidth > node.clientWidth + 2 || node.scrollHeight > node.clientHeight + 2)) {
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
      // SVG 文本平移后的滚动尺寸与实际文本框不一致，应检查真实绘制范围。
      const overflow = label instanceof SVGGraphicsElement ? !contains(authoredBounds(label, viewRect), box, 1)
        : label.scrollWidth > label.clientWidth + 2 || label.scrollHeight > label.clientHeight + 2;
      if (overflow) {
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
        const anchor = (node, point) => {
          if (view.dataset.vdFamily !== "code-sequence") return node;
          // 作者明确绘制执行区间时，消息锚定执行条，否则接到生命线。
          const activation = $$('[data-vd-activation-for]', view).find(bar => bar.dataset.vdActivationFor === node.id && point && point.y >= rect(bar).top && point.y <= rect(bar).bottom);
          return activation || $$('[data-vd-lifeline-for]', view).find(line => line.dataset.vdLifelineFor === node.id) || node;
        };
        const startDistance = boundaryDistance(start, anchor(from, start)), endDistance = boundaryDistance(end, anchor(to, end));
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

  // 汇总当前视图、事实覆盖与页面布局检查。
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
    if (!controls || $$('[data-view]', controls).length !== 3) issues.push(issue("zoom-controls-incomplete", controls));

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

  // 公共调用入口与读者点击使用同一组真实关系。
  function highlight(view, id) {
    // 比较定位复用查看器的真实节点与关系身份。
    const target = id ? document.getElementById(id) : null;
    if (!target) { globalThis.Archify?.focus.clear(); return; }
    if (target.dataset.nodeId) globalThis.Archify?.focus.set(target.dataset.nodeId);
    else globalThis.Archify?.focus.inspectRelationshipById(target.closest('[data-edge-id]')?.dataset.edgeId || target.dataset.edgeId);
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

  // 技术来源按需展开，读者可在离线文件中追溯清单中的事实与证据。
  function bindEvidence() {
    // 数据始终作为文字渲染，不执行来源字符串或创建外部请求。
    const data = JSON.parse(document.getElementById("vibe-diagram-manifest").textContent);
    if (!data.evidence.length) return;
    // 原状态保留含义，不能把分析判断标成已验证。
    const statuses = zh ? { observed: "已确认事实", inferred: "分析判断", proposed: "拟议方案", unresolved: "待确认", verified: "已验证" } : {};
    // 一级正文继续保持图形，完整来源位于可访问的折叠内容中。
    const panel = document.createElement("details"), summary = document.createElement("summary"), list = document.createElement("ul");
    panel.dataset.vdEvidence = ""; summary.textContent = zh ? "事实与依据" : "Facts and evidence";
    data.criticalFacts.forEach(fact => {
      // 从当前清单关联精确来源，不另存一份业务事实。
      const item = document.createElement("li"), sources = document.createElement("p");
      item.textContent = (statuses[fact.status] || fact.status) + " · " + fact.statement;
      sources.textContent = data.evidence.filter(evidence => fact.evidenceIds.includes(evidence.id)).map(evidence => evidence.source).join("；");
      item.append(sources); list.append(item);
    });
    panel.append(summary, list); $('[data-vd-content]').after(panel);
  }

  // 浏览器记录以候选标识绑定独立磁盘文件；最终 SHA-256 由交付命令核对。
  function receipt() {
    const candidate = $('meta[name="vibe-diagram-candidate"]')?.content;
    if (!candidate) throw new Error("请先使用 prepare 生成独立候选文件。");
    return { candidate, url: location.href, ...auditAll() };
  }

  // 对外提供当前画面的检查和图片生成，供真实浏览器验收使用。
  globalThis.VibeDiagramQuality = { auditAll, receipt, highlight };

  // 等待整个 HTML 解析，确保文末的差异数据也已存在。
  const ready = Promise.all([document.fonts?.ready || Promise.resolve(), document.readyState === "loading" ? new Promise(resolve => document.addEventListener("DOMContentLoaded", resolve, { once: true })) : Promise.resolve()]);
  ready.then(() => {
    bindDetails();
    bindEvidence();
    try { bindComparison(); }
    catch (error) { layoutIssues.push(issue("comparison-data-invalid", document.getElementById("vibe-diagram-comparison"), error.message)); }
    requestAnimationFrame(() => requestAnimationFrame(auditAll));
  });
})();
