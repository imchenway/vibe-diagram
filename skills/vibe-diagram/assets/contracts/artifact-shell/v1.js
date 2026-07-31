(() => {
  "use strict";
  document.documentElement.classList.add("vibe-js");

  const unresolvedCanvasText = /^\s*\{\{canvas-text-\d{3}\}\}\s*$/;
  const detailTriggerSelector = "[data-diagram-detail-trigger]";
  const declaredRelationSelector = "[data-diagram-relation-id]";
  const geometricCarrierSelector = [
    "svg path[data-diagram-visible-relation-id]",
    "svg line[data-diagram-visible-relation-id]",
    "svg polyline[data-diagram-visible-relation-id]",
    "svg polygon[data-diagram-visible-relation-id]"
  ].join(", ");
  const fallbackCarrierSelector = [
    "[data-fallback-relation-id]",
    '[data-visible-relation-kind="edge"][data-diagram-visible-relation-id]'
  ].join(", ");
  const auditRoots = "[data-diagram-canvas], [data-sequence-canvas]";
  const epsilon = 1;
  const permitsOverflow = (element, axis) => {
    const owner = element.closest?.("[data-diagram-overflow-intent]");
    const intent = owner?.dataset.diagramOverflowIntent || "";
    return intent === "both-scroll" || intent === `${axis}-scroll`;
  };

  const localizeShell = () => {
    const language = (document.documentElement.lang || "").toLowerCase();
    const isChinese = language === "zh" || language.startsWith("zh-");
    const groupLabels = {
      relations: isChinese ? "\u5173\u7cfb\u7c7b\u578b" : "Line types",
      evidence: isChinese ? "\u8bc1\u636e\u72b6\u6001" : "Evidence states"
    };
    document.querySelectorAll("[data-reading-guide-group]").forEach((group) => {
      const label = group.querySelector(":scope > [data-reading-guide-group-title]");
      const text = groupLabels[group.dataset.readingGuideGroup];
      if (label && text) label.textContent = text;
    });
    const evidenceLabels = {
      "evidence-observed": isChinese ? "\u7528\u6237\u63d0\u4f9b\u4e8b\u5b9e" : "Observed implementation",
      "evidence-check": isChinese ? "\u5df2\u5b8c\u6210\u68c0\u67e5" : "Completed check",
      "evidence-unresolved": isChinese ? "\u5c1a\u672a\u9a8c\u8bc1" : "Not yet verified"
    };
    document.querySelectorAll("[data-evidence-id] > b").forEach((label) => {
      const text = evidenceLabels[label.parentElement?.dataset.evidenceId];
      if (text) label.textContent = text;
    });
    document.querySelectorAll(
      "[data-diagram-zoom-control='fit'], [data-sequence-scale='fit']"
    ).forEach((button) => {
      button.textContent = "\u81ea\u9002\u5e94";
    });
  };

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

  const isRendered = (element) => {
    const style = getComputedStyle(element);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number.parseFloat(style.opacity || "1") > 0 &&
      element.getClientRects().length > 0
    );
  };

  const localNameOf = (element) => (
    element.localName || element.tagName || ""
  ).toLowerCase();

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

  const escapesBounds = (outer, inner, tolerance = epsilon) => (
    inner.left < outer.left - tolerance ||
    inner.right > outer.right + tolerance ||
    inner.top < outer.top - tolerance ||
    inner.bottom > outer.bottom + tolerance
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
    const normalized = (value || "").trim();
    if (normalized === "transparent" || normalized === "none") {
      return { red: 0, green: 0, blue: 0, alpha: 0 };
    }
    const hex = normalized.match(/^#([\da-f]{3,8})$/i);
    if (hex) {
      let payload = hex[1];
      if (payload.length === 3 || payload.length === 4) {
        payload = Array.from(payload, (part) => part + part).join("");
      }
      if (payload.length === 6 || payload.length === 8) {
        return {
          red: Number.parseInt(payload.slice(0, 2), 16) / 255,
          green: Number.parseInt(payload.slice(2, 4), 16) / 255,
          blue: Number.parseInt(payload.slice(4, 6), 16) / 255,
          alpha: payload.length === 8
            ? Number.parseInt(payload.slice(6, 8), 16) / 255
            : 1
        };
      }
    }
    const match = normalized.match(
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
      const detailId = (trigger.dataset.detailFor || "").trim();
      const triggerIdentity = (
        trigger.getAttribute("aria-label") ||
        trigger.getAttribute("data-node-primary-label") ||
        trigger.textContent ||
        ""
      ).trim();
      if (!detailId) {
        addIssue(
          "detail-trigger-target-empty",
          triggerIdentity || trigger.dataset.diagramDetailTrigger || "unnamed-trigger"
        );
        return;
      }
      if (!triggerIdentity) {
        addIssue("detail-trigger-empty", detailId);
      }
      const detail = documentRoot.getElementById(detailId);
      if (!detail) {
        addIssue("detail-target-missing", detailId);
        return;
      }
      if (localNameOf(trigger) !== "a" || trigger.getAttribute("href") !== `#${detailId}`) {
        addIssue("detail-trigger-not-native-link", detailId);
      }
      if (
        localNameOf(detail) !== "details" ||
        detail.id !== detailId ||
        detail.dataset.diagramDetail !== detailId
      ) {
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

    nodes.forEach((node) => {
      const nodeId = node.dataset.diagramNodeId || "unnamed-node";
      if (
        "scrollWidth" in node &&
        "clientWidth" in node &&
        (
          (
            node.scrollWidth > node.clientWidth + epsilon &&
            !permitsOverflow(node, "horizontal")
          ) ||
          (
            node.scrollHeight > node.clientHeight + epsilon &&
            !permitsOverflow(node, "vertical")
          )
        )
      ) {
        addIssue("node-content-overflow", nodeId);
      }

      node.querySelectorAll("*").forEach((content) => {
        if (!isRendered(content)) return;
        if (
          "scrollWidth" in content &&
          "clientWidth" in content &&
          (
            (
              content.scrollWidth > content.clientWidth + epsilon &&
              !permitsOverflow(content, "horizontal")
            ) ||
            (
              content.scrollHeight > content.clientHeight + epsilon &&
              !permitsOverflow(content, "vertical")
            )
          )
        ) {
          addIssue("node-content-overflow", nodeId);
        }
      });

      const svgSurface = Array.from(node.children).find(
        (child) => localNameOf(child) === "rect" && isRendered(child)
      );
      if (!svgSurface) return;
      const surfaceRect = svgSurface.getBoundingClientRect();
      node.querySelectorAll("text, foreignObject").forEach((content) => {
        if (!isRendered(content)) return;
        const contentRect = content.getBoundingClientRect();
        if (escapesBounds(surfaceRect, contentRect, 2)) {
          addIssue("node-content-overflow", nodeId);
        }
      });
    });

    canvas.querySelectorAll("[data-architecture-landmark-for]").forEach((landmark) => {
      if (!isRendered(landmark)) return;
      const nodeId = (landmark.dataset.architectureLandmarkFor || "").trim();
      const surface = Array.from(landmark.children).find(
        (child) => localNameOf(child) === "rect" && isRendered(child)
      );
      if (!surface) return;
      const surfaceRect = surface.getBoundingClientRect();
      landmark.querySelectorAll("text, foreignObject").forEach((content) => {
        if (!isRendered(content)) return;
        if (escapesBounds(surfaceRect, content.getBoundingClientRect(), 2)) {
          addIssue("node-content-overflow", nodeId || "unnamed-landmark");
        }
      });
    });

    canvas.querySelectorAll("foreignObject > *").forEach((content) => {
      if (!isRendered(content)) return;
      if (
        "scrollWidth" in content &&
        "clientWidth" in content &&
        "scrollHeight" in content &&
        "clientHeight" in content &&
        (
          (
            content.scrollWidth > content.clientWidth + epsilon &&
            !permitsOverflow(content, "horizontal")
          ) ||
          (
            content.scrollHeight > content.clientHeight + epsilon &&
            !permitsOverflow(content, "vertical")
          )
        )
      ) {
        addIssue(
          "node-content-overflow",
          content.closest("[data-diagram-node-id]")?.dataset.diagramNodeId || localNameOf(content)
        );
      }
    });

    canvas.querySelectorAll("[data-diagram-detail-trigger='auxiliary']").forEach((trigger) => {
      if (!isRendered(trigger)) return;
      const svgSurface = trigger.querySelector("rect, path, polygon, circle, ellipse");
      const surface = svgSurface || trigger;
      const surfaceStyle = getComputedStyle(surface);
      const color = parseColor(
        svgSurface
          ? surfaceStyle.fill || svgSurface.getAttribute("fill") || ""
          : surfaceStyle.backgroundColor
      );
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
    canvas.querySelectorAll("[data-architecture-landmark-for]").forEach((landmark) => {
      if (!isRendered(landmark)) return;
      const nodeId = (landmark.dataset.architectureLandmarkFor || "").trim();
      if (!nodeId) return;
      const surface = Array.from(landmark.children).find(
        (child) => localNameOf(child) === "rect" && isRendered(child)
      );
      nodeRects.set(nodeId, (surface || landmark).getBoundingClientRect());
    });
    const labels = Array.from(canvas.querySelectorAll("svg text")).filter(isVisible);
    const declaredRelations = Array.from(canvas.querySelectorAll(declaredRelationSelector));
    const declaredById = new Map(
      declaredRelations
        .map((relation) => [(relation.dataset.diagramRelationId || "").trim(), relation])
        .filter(([relationId]) => Boolean(relationId))
    );
    const declaredRelationIds = new Set(declaredById.keys());
    const primaryStage = canvas.querySelector(":scope > [data-diagram-stage]") || canvas;
    if (!isRendered(primaryStage)) {
      const canvasId = canvas.dataset.diagramId || canvas.dataset.sequenceId || "";
      const fallbackRoot = canvasId
        ? canvas.ownerDocument.querySelector(
          `[data-fallback-for="${CSS.escape(canvasId)}"]`
        )
        : null;
      const fallbackByRelation = new Map();
      if (fallbackRoot && isRendered(fallbackRoot)) {
        fallbackRoot.querySelectorAll(fallbackCarrierSelector).forEach((carrier) => {
          const relationId = (
            carrier.dataset.fallbackRelationId ||
            carrier.dataset.diagramVisibleRelationId ||
            ""
          ).trim();
          if (!relationId) {
            addIssue("fallback-relation-id-missing", canvasId || "unnamed-canvas");
            return;
          }
          const values = fallbackByRelation.get(relationId) || [];
          values.push(carrier);
          fallbackByRelation.set(relationId, values);
          if (!declaredById.has(relationId)) {
            addIssue("fallback-relation-not-declared", relationId);
          }
        });
      }
      declaredById.forEach((declaration, relationId) => {
        const fallbackCarriers = fallbackByRelation.get(relationId) || [];
        if (!fallbackCarriers.length) {
          addIssue("missing-geometric-carrier", relationId);
          addIssue("declared-route-not-audited", relationId);
          return;
        }
        if (fallbackCarriers.length !== 1) {
          addIssue("fallback-relation-duplicate", relationId);
          addIssue("declared-route-not-audited", relationId);
          return;
        }
        const fallback = fallbackCarriers[0];
        if (
          (fallback.dataset.from || "") !== (declaration.dataset.from || "") ||
          (fallback.dataset.to || "") !== (declaration.dataset.to || "") ||
          (fallback.dataset.relationKind || "") !== (declaration.dataset.relationKind || "")
        ) {
          addIssue("fallback-relation-not-equivalent", relationId);
          addIssue("declared-route-not-audited", relationId);
        }
      });
      return;
    }

    const carriers = Array.from(primaryStage.querySelectorAll(geometricCarrierSelector))
      .filter(isRendered);
    const carriersByRelation = new Map();
    carriers.forEach((carrier) => {
      const relationId = (carrier.dataset.diagramVisibleRelationId || "").trim();
      if (!relationId) return;
      const values = carriersByRelation.get(relationId) || [];
      values.push(carrier);
      carriersByRelation.set(relationId, values);
    });

    declaredRelationIds.forEach((relationId) => {
      if (!carriersByRelation.has(relationId)) {
        addIssue("missing-geometric-carrier", relationId);
      }
    });

    const auditedRelationIds = new Set();
    carriers
      .filter((carrier) => localNameOf(carrier) === "path")
      .forEach((path) => {
        const relationId = path.dataset.diagramVisibleRelationId || "unknown";
        if (typeof path.getTotalLength !== "function") return;
        let length = Number.NaN;
        try {
          length = path.getTotalLength();
        } catch (_error) {
          return;
        }
        auditedRelationIds.add(relationId);
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

    declaredRelationIds.forEach((relationId) => {
      if (!auditedRelationIds.has(relationId)) {
        addIssue("declared-route-not-audited", relationId);
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

  const controlsAreAvailable = (controls) => {
    if (!controls) return false;
    if (controls.hasAttribute("data-diagram-controls")) {
      return controls.dataset.diagramControlsVisible === "true";
    }
    return !controls.hidden;
  };

  const reflectTitleControlState = (controls) => {
    const controlRegion = controls?.closest("[data-artifact-shell-controls]");
    if (!controlRegion) return;
    const hasVisibleControl = Array.from(
      controlRegion.querySelectorAll("[data-diagram-controls], [data-sequence-toolbar]")
    ).some(controlsAreAvailable);
    controlRegion.dataset.controlsState = hasVisibleControl ? "active" : "empty";
  };

  const auditControls = (canvas, addIssue) => {
    const controlScope = (canvas.dataset.diagramControlScope || "").trim();
    if (controlScope === "embedded") {
      const composition = canvas.closest("[data-diagram-composition-root]");
      const primary = composition?.querySelector(
        '[data-diagram-control-scope="primary"]'
      );
      const primaryId = primary?.dataset.diagramId || primary?.dataset.sequenceId || "";
      const primaryControls = primaryId
        ? document.querySelector(
            `[data-diagram-controls="${CSS.escape(primaryId)}"], [data-sequence-controls="${CSS.escape(primaryId)}"]`
          )
        : null;
      if (!composition || !primary || !primaryControls) {
        addIssue(
          "embedded-control-scope-invalid",
          canvas.dataset.diagramId || canvas.dataset.sequenceId || "unnamed-canvas"
        );
      }
      return;
    }
    const canvasId = canvas.dataset.diagramId || canvas.dataset.sequenceId || "";
    const controls = document.querySelector(
      `[data-diagram-controls="${CSS.escape(canvasId)}"], [data-sequence-controls="${CSS.escape(canvasId)}"]`
    );
    if (!controls) {
      addIssue("zoom-controls-missing", canvasId || "unnamed-canvas");
      return;
    }
    reflectTitleControlState(controls);
    const controlRegion = controls.closest("[data-artifact-shell-controls]");
    const titleRegion = controlRegion?.closest("[data-artifact-shell-title='1']");
    if (!controlRegion || !titleRegion) {
      addIssue("title-control-region-missing", canvasId || "unnamed-canvas");
      return;
    }
    const scaleAttribute = controls.hasAttribute("data-sequence-toolbar")
      ? "sequenceScale"
      : "diagramZoomControl";
    const scaleSelector = controls.hasAttribute("data-sequence-toolbar")
      ? "[data-sequence-scale]"
      : "[data-diagram-zoom-control]";
    const scaleOrder = Array.from(controls.querySelectorAll(scaleSelector))
      .map((button) => button.dataset[scaleAttribute]);
    if (scaleOrder.join("|") !== "0.75|0.9|1|fit") {
      addIssue("zoom-control-order", scaleOrder.join("|") || "empty");
    }
    const guide = canvas.querySelector(
      `:scope > [data-diagram-reading-guide='1'][data-reading-guide-for="${CSS.escape(canvasId)}"]`
    );
    if (!guide) {
      addIssue("local-reading-guide-missing", canvasId || "unnamed-canvas");
      return;
    }
    if (isRendered(guide) && isRendered(canvas)) {
      const guideRect = guide.getBoundingClientRect();
      const canvasRect = canvas.getBoundingClientRect();
      if (
        guideRect.left < canvasRect.left - epsilon ||
        guideRect.top < canvasRect.top - epsilon ||
        guideRect.right > canvasRect.right + epsilon ||
        guideRect.bottom > canvasRect.bottom + epsilon
      ) {
        addIssue(
          "local-guide-outside-canvas",
          `${Math.round(guideRect.left - canvasRect.left)}:${Math.round(guideRect.top - canvasRect.top)}`
        );
      }
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
    const disclosure = globalThis.VibeDiagramDisclosure?.auditLifecycle?.(root);
    const disclosureIssues = Array.isArray(disclosure?.issues)
      ? disclosure.issues
      : [];
    const failures = Array.from(results.values()).reduce(
      (total, issues) => total + issues.length,
      0
    ) + disclosureIssues.length;
    document.documentElement.dataset.computedLayoutAudit = failures ? "failed" : "passed";
    document.documentElement.dataset.computedLayoutIssueCount = String(failures);
    if (disclosureIssues.length) {
      document.documentElement.dataset.computedLayoutIssues =
        disclosureIssues.map((issue) => `detail-lifecycle:${issue}`).join("|").slice(0, 2048);
    } else {
      delete document.documentElement.dataset.computedLayoutIssues;
    }
    return results;
  };

  const reflectDetailState = (detail) => {
    if (!detail?.id) return;
    document.querySelectorAll(
      `${detailTriggerSelector}[data-detail-for="${CSS.escape(detail.id)}"]`
    ).forEach((trigger) => {
      trigger.setAttribute("aria-expanded", detail.open ? "true" : "false");
    });
  };

  const openDetailTarget = (trigger, { focus = true } = {}) => {
    const detailId = (trigger?.dataset.detailFor || "").trim();
    const detail = detailId ? document.getElementById(detailId) : null;
    if (
      !detail ||
      localNameOf(detail) !== "details" ||
      detail.dataset.diagramDetail !== detailId
    ) {
      return false;
    }
    detail.open = true;
    reflectDetailState(detail);
    if (focus) {
      requestAnimationFrame(() => {
        detail.querySelector("summary")?.focus({ preventScroll: true });
      });
    }
    return true;
  };

  const enhanceDetailLinks = () => {
    document.querySelectorAll("details[data-diagram-detail]").forEach((detail) => {
      reflectDetailState(detail);
      detail.addEventListener("toggle", () => reflectDetailState(detail));
    });
    document.addEventListener("click", (event) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const trigger = event.target.closest?.(detailTriggerSelector);
      if (trigger) openDetailTarget(trigger);
    }, { capture: true });
    const openHashTarget = () => {
      const detailId = decodeURIComponent(location.hash.slice(1));
      if (!detailId) return;
      const trigger = document.querySelector(
        `${detailTriggerSelector}[data-detail-for="${CSS.escape(detailId)}"]`
      );
      if (trigger) openDetailTarget(trigger, { focus: false });
    };
    addEventListener("hashchange", openHashTarget);
    openHashTarget();
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
    localizeShell();
    document
      .querySelectorAll(auditRoots)
      .forEach(suppressUnfilledCanvasText);
    if (!globalThis.VibeDiagramDisclosure) enhanceDetailLinks();
    globalThis.VibeDiagramQuality = Object.freeze({ audit, auditAll, scheduleAudit });
    scheduleAudit();
    document.fonts?.ready.then(scheduleAudit, scheduleAudit);
    if ("ResizeObserver" in globalThis) {
      const observer = new ResizeObserver(scheduleAudit);
      document.querySelectorAll(
        `${auditRoots}, [data-diagram-reading-guide="1"], [data-artifact-shell-controls]`
      ).forEach(
        (element) => observer.observe(element)
      );
    } else {
      addEventListener("resize", scheduleAudit);
    }
    if ("MutationObserver" in globalThis) {
      const observer = new MutationObserver(scheduleAudit);
      document.querySelectorAll("[data-diagram-controls], [data-sequence-toolbar]").forEach(
        (controls) => observer.observe(controls, {
          attributes: true,
          attributeFilter: ["hidden", "data-diagram-controls-visible"]
        })
      );
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhance, { once: true });
  } else {
    enhance();
  }
})();
