(() => {
  "use strict";

  const unresolvedCanvasText = /^\s*\{\{canvas-text-\d{3}\}\}\s*$/;
  const detailTriggerSelector = "[data-diagram-detail-trigger][data-detail-for]";
  const auditRoots = "[data-diagram-canvas], [data-sequence-canvas]";
  const epsilon = 1;

  const suppressUnfilledCanvasText = (root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const unresolvedNodes = [];
    while (walker.nextNode()) {
      if (unresolvedCanvasText.test(walker.currentNode.nodeValue || "")) {
        unresolvedNodes.push(walker.currentNode);
      }
    }
    unresolvedNodes.forEach((node) => {
      node.nodeValue = "";
    });
    if (unresolvedNodes.length) {
      root.setAttribute("data-template-preview", "unfilled");
    }
  };

  const isVisible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number.parseFloat(style.opacity || "1") > 0 &&
      rect.width > epsilon &&
      rect.height > epsilon
    );
  };

  const overlaps = (left, right, inset = epsilon) => (
    left.left + inset < right.right &&
    left.right - inset > right.left &&
    left.top + inset < right.bottom &&
    left.bottom - inset > right.top
  );

  const containsPoint = (rect, point, inset = 2) => (
    point.x > rect.left + inset &&
    point.x < rect.right - inset &&
    point.y > rect.top + inset &&
    point.y < rect.bottom - inset
  );

  const pointOnBoundary = (rect, point, tolerance = 6) => {
    const withinHorizontal = point.x >= rect.left - tolerance && point.x <= rect.right + tolerance;
    const withinVertical = point.y >= rect.top - tolerance && point.y <= rect.bottom + tolerance;
    return (
      (withinHorizontal && (
        Math.abs(point.y - rect.top) <= tolerance ||
        Math.abs(point.y - rect.bottom) <= tolerance
      )) ||
      (withinVertical && (
        Math.abs(point.x - rect.left) <= tolerance ||
        Math.abs(point.x - rect.right) <= tolerance
      ))
    );
  };

  const numericAttribute = (element, name) => {
    const value = Number.parseFloat(element.getAttribute(name) || "");
    return Number.isFinite(value) ? value : null;
  };

  const parseColor = (value) => {
    const match = value.match(
      /rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*(?:\.\d+)?))?\s*\)/
    );
    if (!match) return null;
    return {
      red: Number(match[1]) / 255,
      green: Number(match[2]) / 255,
      blue: Number(match[3]) / 255,
      alpha: match[4] === undefined || match[4] === "" ? 1 : Number(match[4])
    };
  };

  const pointOnScreen = (path, distance) => {
    const point = path.getPointAtLength(distance);
    const matrix = path.getScreenCTM();
    if (!matrix) return null;
    const transformed = new DOMPoint(point.x, point.y).matrixTransform(matrix);
    return { x: transformed.x, y: transformed.y };
  };

  const auditDetailLinks = (canvas, addIssue) => {
    const documentRoot = canvas.ownerDocument;
    canvas.querySelectorAll(detailTriggerSelector).forEach((trigger) => {
      const detailId = trigger.dataset.detailFor || "";
      const detail = detailId
        ? documentRoot.querySelector(`[data-diagram-detail="${CSS.escape(detailId)}"]`)
        : null;
      if (!detail) {
        addIssue("detail-target-missing", detailId || "unnamed-trigger");
        return;
      }
      if (trigger.tagName !== "A" || trigger.getAttribute("href") !== `#${detailId}`) {
        addIssue("detail-trigger-not-native-link", detailId);
      }
      if (detail.tagName !== "DETAILS" || detail.id !== detailId) {
        addIssue("detail-target-not-native-details", detailId);
      }
    });
  };

  const auditNodeGeometry = (canvas, addIssue) => {
    const nodes = Array.from(canvas.querySelectorAll("[data-diagram-node-id]")).filter(isVisible);
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      const left = nodes[leftIndex];
      const leftRect = left.getBoundingClientRect();
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const right = nodes[rightIndex];
        if (left.contains(right) || right.contains(left)) continue;
        if (overlaps(leftRect, right.getBoundingClientRect(), 2)) {
          addIssue(
            "node-overlap",
            `${left.dataset.diagramNodeId || leftIndex}:${right.dataset.diagramNodeId || rightIndex}`
          );
        }
      }
    }
    canvas.querySelectorAll("foreignObject > *, [data-node-title], [data-node-summary]").forEach(
      (content) => {
        if (!isVisible(content)) return;
        if (
          content.scrollWidth > content.clientWidth + epsilon ||
          content.scrollHeight > content.clientHeight + epsilon
        ) {
          addIssue(
            "node-content-overflow",
            content.closest("[data-diagram-node-id]")?.dataset.diagramNodeId || content.tagName
          );
        }
      }
    );
    canvas.querySelectorAll("[data-diagram-detail-trigger='auxiliary']").forEach((trigger) => {
      if (!isVisible(trigger)) return;
      const color = parseColor(getComputedStyle(trigger).backgroundColor);
      if (!color || color.alpha < 0.85) {
        addIssue("auxiliary-node-background-transparent", trigger.dataset.detailFor || "unknown");
        return;
      }
      const luminance = color.red * 0.2126 + color.green * 0.7152 + color.blue * 0.0722;
      if (luminance < 0.72) {
        addIssue("auxiliary-node-background-too-dark", trigger.dataset.detailFor || "unknown");
      }
    });
  };

  const auditRoutes = (canvas, addIssue) => {
    const nodeRects = new Map(
      Array.from(canvas.querySelectorAll("[data-diagram-node-id]"))
        .filter(isVisible)
        .map((node) => [node.dataset.diagramNodeId, node.getBoundingClientRect()])
    );
    const labels = Array.from(canvas.querySelectorAll("svg text")).filter(isVisible);
    canvas.querySelectorAll("path[data-diagram-visible-relation-id]").forEach((path) => {
      if (typeof path.getTotalLength !== "function") return;
      const relationId = path.dataset.diagramVisibleRelationId || "unknown";
      const length = path.getTotalLength();
      if (!Number.isFinite(length) || length < 24) {
        addIssue("route-too-short", relationId);
        return;
      }
      if (!path.getAttribute("marker-end")) {
        addIssue("route-arrowhead-missing", relationId);
      }
      const sourceId = path.dataset.from || "";
      const targetId = path.dataset.to || "";
      const sourceRect = nodeRects.get(sourceId);
      const targetRect = nodeRects.get(targetId);
      const startPoint = pointOnScreen(path, 0);
      const endPoint = pointOnScreen(path, length);
      if (!sourceRect || !startPoint || !pointOnBoundary(sourceRect, startPoint)) {
        addIssue("route-source-not-anchored", relationId);
      }
      if (!targetRect || !endPoint || !pointOnBoundary(targetRect, endPoint)) {
        addIssue("route-target-not-anchored", relationId);
      }
      const sampleCount = Math.max(8, Math.min(96, Math.ceil(length / 12)));
      for (let index = 1; index < sampleCount; index += 1) {
        const progress = index / sampleCount;
        const point = pointOnScreen(path, length * progress);
        if (!point) break;
        for (const [nodeId, rect] of nodeRects) {
          if (
            (nodeId === sourceId && progress < 0.08) ||
            (nodeId === targetId && progress > 0.92)
          ) {
            continue;
          }
          if (containsPoint(rect, point, 3)) {
            addIssue("route-crosses-node", `${relationId}:${nodeId}`);
          }
        }
        for (const label of labels) {
          if (label.dataset.routeLabelFor === relationId) continue;
          if (containsPoint(label.getBoundingClientRect(), point, 1)) {
            addIssue("route-crosses-label", relationId);
            break;
          }
        }
      }
    });
  };

  const auditUtilization = (canvas, addIssue) => {
    const svg = canvas.querySelector("svg[data-architecture-canvas]");
    if (!svg?.viewBox?.baseVal) return;
    const boundaries = Array.from(
      svg.querySelectorAll("rect[data-architecture-boundary]")
    ).map((rect) => ({
      x: numericAttribute(rect, "x"),
      y: numericAttribute(rect, "y"),
      width: numericAttribute(rect, "width"),
      height: numericAttribute(rect, "height")
    })).filter((item) => Object.values(item).every((value) => value !== null));
    if (!boundaries.length) return;
    const viewBox = svg.viewBox.baseVal;
    const left = Math.min(...boundaries.map((item) => item.x));
    const top = Math.min(...boundaries.map((item) => item.y));
    const right = Math.max(...boundaries.map((item) => item.x + item.width));
    const bottom = Math.max(...boundaries.map((item) => item.y + item.height));
    const ratios = {
      top: (top - viewBox.y) / viewBox.height,
      bottom: (viewBox.y + viewBox.height - bottom) / viewBox.height,
      horizontal: (right - left) / viewBox.width
    };
    const thresholds = {
      top: numericAttribute(canvas, "data-max-top-whitespace-ratio"),
      bottom: numericAttribute(canvas, "data-max-bottom-whitespace-ratio"),
      horizontal: numericAttribute(canvas, "data-min-horizontal-utilization-ratio")
    };
    if (thresholds.top !== null && ratios.top > thresholds.top + 0.0001) {
      addIssue("canvas-top-whitespace", ratios.top.toFixed(4));
    }
    if (thresholds.bottom !== null && ratios.bottom > thresholds.bottom + 0.0001) {
      addIssue("canvas-bottom-whitespace", ratios.bottom.toFixed(4));
    }
    if (thresholds.horizontal !== null && ratios.horizontal < thresholds.horizontal - 0.0001) {
      addIssue("canvas-horizontal-underuse", ratios.horizontal.toFixed(4));
    }
  };

  const auditControls = (canvas, addIssue) => {
    const canvasId = canvas.dataset.diagramId || canvas.dataset.sequenceId || "";
    const controls = document.querySelector(
      `[data-diagram-controls="${CSS.escape(canvasId)}"], [data-sequence-controls="${CSS.escape(canvasId)}"]`
    );
    if (!controls) {
      addIssue("zoom-controls-missing", canvasId || "unnamed-canvas");
      return;
    }
    const controlRegion = controls.closest("[data-reading-guide-controls]");
    const interaction = controlRegion?.querySelector("[data-reading-guide-group='interaction']");
    if (!controlRegion || !interaction) {
      addIssue("reading-guide-control-stack-missing", canvasId || "unnamed-canvas");
      return;
    }
    const interactionRect = interaction.getBoundingClientRect();
    const controlsRect = controls.getBoundingClientRect();
    if (
      isVisible(interaction) &&
      isVisible(controls) &&
      interactionRect.bottom > controlsRect.top + epsilon
    ) {
      addIssue("interaction-not-above-controls", canvasId || "unnamed-canvas");
    }
  };

  const audit = (canvas) => {
    const issues = new Set();
    const addIssue = (code, target) => issues.add(`${code}:${target}`);
    auditDetailLinks(canvas, addIssue);
    auditNodeGeometry(canvas, addIssue);
    auditRoutes(canvas, addIssue);
    auditUtilization(canvas, addIssue);
    auditControls(canvas, addIssue);
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth + epsilon) {
      addIssue("page-horizontal-overflow", document.documentElement.scrollWidth);
    }
    const ordered = Array.from(issues).sort();
    canvas.setAttribute(
      "data-computed-layout-audit",
      ordered.length ? "failed" : "passed"
    );
    canvas.setAttribute("data-computed-layout-issue-count", String(ordered.length));
    if (ordered.length) {
      canvas.dataset.computedLayoutIssues = ordered.join("|").slice(0, 2048);
    } else {
      delete canvas.dataset.computedLayoutIssues;
    }
    canvas.dispatchEvent(
      new CustomEvent("vibe-diagram:layout-audit", {
        bubbles: true,
        detail: { issues: ordered, passed: ordered.length === 0 }
      })
    );
    return ordered;
  };

  const auditAll = (root = document) => {
    const results = new Map();
    root.querySelectorAll(auditRoots).forEach((canvas) => {
      results.set(canvas.dataset.diagramId || canvas.dataset.sequenceId || "canvas", audit(canvas));
    });
    const failures = Array.from(results.values()).reduce(
      (total, issues) => total + issues.length,
      0
    );
    document.documentElement.dataset.computedLayoutAudit = failures ? "failed" : "passed";
    document.documentElement.dataset.computedLayoutIssueCount = String(failures);
    return results;
  };

  let auditQueued = false;
  const scheduleAudit = () => {
    if (auditQueued) return;
    auditQueued = true;
    requestAnimationFrame(() => {
      auditQueued = false;
      auditAll();
    });
  };

  const enhance = () => {
    document
      .querySelectorAll(auditRoots)
      .forEach(suppressUnfilledCanvasText);
    globalThis.VibeDiagramQuality = Object.freeze({ audit, auditAll, scheduleAudit });
    scheduleAudit();
    document.fonts?.ready.then(scheduleAudit, scheduleAudit);
    if ("ResizeObserver" in globalThis) {
      const observer = new ResizeObserver(scheduleAudit);
      document.querySelectorAll(`${auditRoots}, [data-diagram-reading-guide="1"]`).forEach(
        (element) => observer.observe(element)
      );
    } else {
      addEventListener("resize", scheduleAudit);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhance, { once: true });
  } else {
    enhance();
  }
})();
