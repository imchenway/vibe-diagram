(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const auditOutput = () => $("[data-vd-audit-output]");

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
      const overflow = request === "fit" && available / width < 0.75;
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
    let returnFocus = null;
    $$('[data-vd-detail-trigger]').forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        const targetId = trigger.getAttribute("data-vd-detail-trigger");
        const dialog = targetId ? document.getElementById(targetId) : null;
        if (!(dialog instanceof HTMLDialogElement)) return;
        event.preventDefault();
        returnFocus = trigger;
        dialog.showModal();
        $('[data-vd-detail-close]', dialog)?.focus();
      });
    });
    $$('dialog[data-vd-detail-for]').forEach((dialog) => {
      $$('[data-vd-detail-close]', dialog).forEach((button) => button.addEventListener("click", () => dialog.close()));
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener("close", () => {
        if (returnFocus instanceof HTMLElement && returnFocus.isConnected) returnFocus.focus();
        returnFocus = null;
      });
    });
  }

  const rect = (element) => element.getBoundingClientRect();
  const visible = (element) => {
    const style = getComputedStyle(element);
    const box = rect(element);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    if (box.width < 1 || box.height < 1) return false;
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

  function nearBoundary(point, box, tolerance = 18) {
    if (!point) return false;
    const insideExpanded = point.x >= box.left - tolerance && point.x <= box.right + tolerance &&
      point.y >= box.top - tolerance && point.y <= box.bottom + tolerance;
    const distance = Math.min(
      Math.abs(point.x - box.left), Math.abs(point.x - box.right),
      Math.abs(point.y - box.top), Math.abs(point.y - box.bottom)
    );
    return insideExpanded && distance <= tolerance;
  }

  function issue(code, element, detail = "") {
    return {
      code,
      id: element?.id || element?.getAttribute?.("data-vd-view") || "",
      detail
    };
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
    });

    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = rect(nodes[i]);
        const b = rect(nodes[j]);
        if (intersects(a, b, 2)) issues.push(issue("node-overlap", nodes[i], nodes[j].id || "anonymous"));
      }
    }

    groups.forEach((group) => {
      const box = rect(group);
      $$('[data-vd-node]', group).filter(visible).forEach((node) => {
        if (!contains(box, rect(node), 2)) issues.push(issue("group-clips-node", group, node.id || "anonymous"));
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
        if (!nearBoundary(start, rect(from))) issues.push(issue("edge-start-not-anchored", edge, from.id));
        if (!nearBoundary(end, rect(to))) issues.push(issue("edge-end-not-anchored", edge, to.id));
        const excluded = new Set([from, to]);
        for (let sample = 10; sample < length - 10; sample += 8) {
          const point = screenPoint(edge, sample);
          if (!point) break;
          const hit = nodes.find((node) => !excluded.has(node) && contains(rect(node), {
            left: point.x, right: point.x, top: point.y, bottom: point.y
          }, -2));
          if (hit) {
            issues.push(issue("edge-through-node", edge, hit.id || "anonymous"));
            break;
          }
        }
      }
    });

    return issues;
  }

  function auditAll() {
    const issues = [];
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
    return report;
  }

  globalThis.VibeDiagramQuality = { auditAll, applyZoom };

  const ready = document.fonts?.ready || Promise.resolve();
  ready.then(() => {
    bindZoom();
    bindDetails();
    requestAnimationFrame(() => requestAnimationFrame(auditAll));
  });
})();
