(() => {
  "use strict";
  const activeByRoot = new WeakMap();
  const returnFocusByRoot = new WeakMap();
  const boundRoots = new WeakSet();
  const lifecycleAuditByRoot = new WeakMap();
  const isNativeDetails = (detail) => detail.matches("details");
  const documentElementFor = (root) =>
    root.nodeType === Node.DOCUMENT_NODE ? root.documentElement : root.ownerDocument.documentElement;
  const viewFor = (root) =>
    root.nodeType === Node.DOCUMENT_NODE
      ? root.defaultView
      : root.ownerDocument.defaultView;
  const decodedHashFor = (view) => {
    try {
      return decodeURIComponent(view?.location.hash.slice(1) || "");
    } catch (_error) {
      return "";
    }
  };
  const detailTriggerSelector = "[data-diagram-detail-trigger][data-detail-for]";
  const triggersFor = (root, id) =>
    Array.from(root.querySelectorAll(detailTriggerSelector)).filter(
      (trigger) => trigger.dataset.detailFor === id
    );
  const reflect = (root, id, expanded) => {
    triggersFor(root, id).forEach((trigger) => {
      trigger.setAttribute("aria-expanded", String(expanded));
    });
  };
  const regionFor = (detail) => detail.closest("[data-node-detail-region]");
  const gridFor = (detail) => detail.closest("[data-node-detail-grid]");
  const portalRegions = (root) => {
    const documentRoot = root.nodeType === Node.DOCUMENT_NODE
      ? root
      : root.ownerDocument;
    const host = documentRoot?.body;
    if (!host) return;
    Array.from(root.querySelectorAll("[data-node-detail-region]")).forEach((region) => {
      if (region.parentElement === host) return;
      region.dataset.runtimeDetailPortal = "true";
      host.append(region);
    });
  };
  const syncDocumentState = (root) => {
    const documentElement = documentElementFor(root);
    documentElement.setAttribute("data-progressive-disclosure-enhanced", "true");
    documentElement.toggleAttribute(
      "data-progressive-disclosure-open",
      Boolean(root.querySelector("[data-node-detail-region][data-runtime-active='true']"))
    );
  };
  const ensureCloseButton = (root, detail) => {
    let button = detail.querySelector(":scope > [data-diagram-detail-close]");
    if (button) return button;
    const region = regionFor(detail);
    button = detail.ownerDocument.createElement("button");
    button.type = "button";
    button.dataset.diagramDetailClose = "true";
    button.setAttribute(
      "aria-label",
      region?.dataset.detailCloseLabel || "Close node details"
    );
    button.textContent = "×";
    button.addEventListener("click", () => close(root, true));
    detail.append(button);
    return button;
  };
  const clamp = (value, minimum, maximum) =>
    Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
  const place = (detail, trigger) => {
    const grid = gridFor(detail);
    const view = detail.ownerDocument.defaultView;
    if (!grid || !view) return;
    const margin = 12;
    const gap = 10;
    const viewportWidth = Math.max(0, view.innerWidth);
    const viewportHeight = Math.max(0, view.innerHeight);
    const width = Math.min(352, Math.max(240, viewportWidth - margin * 2));
    grid.style.setProperty("--detail-width", `${width}px`);
    grid.style.setProperty("--detail-left", `${margin}px`);
    grid.style.setProperty("--detail-top", `${margin}px`);
    const popupRect = grid.getBoundingClientRect();
    const popupWidth = width;
    const popupHeight = Math.min(
      popupRect.height || 240,
      Math.max(160, viewportHeight - margin * 2)
    );
    const triggerRect = trigger?.getBoundingClientRect();
    let left = clamp((viewportWidth - popupWidth) / 2, margin, viewportWidth - popupWidth - margin);
    let top = clamp((viewportHeight - popupHeight) / 2, margin, viewportHeight - popupHeight - margin);
    let side = "center";
    if (triggerRect) {
      if (
        viewportWidth >= 768
        && triggerRect.right + gap + popupWidth <= viewportWidth - margin
      ) {
        left = triggerRect.right + gap;
        side = "right";
      } else if (
        viewportWidth >= 768
        && triggerRect.left - gap - popupWidth >= margin
      ) {
        left = triggerRect.left - gap - popupWidth;
        side = "left";
      } else {
        left = clamp(
          triggerRect.left + triggerRect.width / 2 - popupWidth / 2,
          margin,
          viewportWidth - popupWidth - margin
        );
        side = "center";
      }
      top = clamp(
        triggerRect.top + triggerRect.height / 2 - popupHeight / 2,
        margin,
        viewportHeight - popupHeight - margin
      );
    }
    left = clamp(left, margin, viewportWidth - popupWidth - margin);
    top = clamp(top, margin, viewportHeight - popupHeight - margin);
    grid.style.setProperty("--detail-left", `${Math.round(left)}px`);
    grid.style.setProperty("--detail-top", `${Math.round(top)}px`);
    const renderedRect = grid.getBoundingClientRect();
    if (renderedRect.left < margin) left += margin - renderedRect.left;
    if (renderedRect.right > viewportWidth - margin) {
      left -= renderedRect.right - (viewportWidth - margin);
    }
    if (renderedRect.top < margin) top += margin - renderedRect.top;
    if (renderedRect.bottom > viewportHeight - margin) {
      top -= renderedRect.bottom - (viewportHeight - margin);
    }
    left = clamp(left, margin, viewportWidth - renderedRect.width - margin);
    top = clamp(top, margin, viewportHeight - renderedRect.height - margin);
    grid.style.setProperty("--detail-left", `${Math.round(left)}px`);
    grid.style.setProperty("--detail-top", `${Math.round(top)}px`);
    grid.dataset.popupSide = side;
  };
  const restoreDetail = (root, detail) => {
    const id = detail.dataset.diagramDetail;
    if (isNativeDetails(detail)) {
      const wasOpen = detail.getAttribute("data-runtime-was-open") === "true";
      detail.open = wasOpen;
      detail.removeAttribute("data-runtime-was-open");
    } else {
      const wasHidden = detail.getAttribute("data-runtime-was-hidden") === "true";
      detail.hidden = wasHidden;
      detail.removeAttribute("data-runtime-was-hidden");
    }
    detail.removeAttribute("data-runtime-open");
    detail.removeAttribute("role");
    detail.removeAttribute("aria-modal");
    const grid = gridFor(detail);
    if (grid) {
      grid.style.removeProperty("--detail-width");
      grid.style.removeProperty("--detail-left");
      grid.style.removeProperty("--detail-top");
      delete grid.dataset.popupSide;
    }
    regionFor(detail)?.removeAttribute("data-runtime-active");
    reflect(root, id, isNativeDetails(detail) && detail.open);
  };
  const close = (root = document, restoreFocus = true, clearHash = true) => {
    const detail = activeByRoot.get(root);
    if (!detail) return false;
    const id = detail.dataset.diagramDetail;
    restoreDetail(root, detail);
    activeByRoot.delete(root);
    syncDocumentState(root);
    const view = viewFor(root);
    if (
      clearHash
      && view
      && decodedHashFor(view) === id
    ) {
      view.history.replaceState(
        view.history.state,
        "",
        `${view.location.pathname}${view.location.search}`
      );
    }
    if (restoreFocus) {
      const trigger = returnFocusByRoot.get(root);
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
    }
    returnFocusByRoot.delete(root);
    return true;
  };
  const reset = (root = document) => {
    close(root, false);
    root.querySelectorAll("[data-diagram-detail][data-runtime-open]").forEach((detail) => {
      restoreDetail(root, detail);
    });
    root.querySelectorAll("[data-node-detail-region][data-runtime-active]").forEach((region) => {
      region.removeAttribute("data-runtime-active");
    });
    syncDocumentState(root);
  };
  const open = (root, id, trigger = null, updateHash = true) => {
    const detail = root.querySelector(`[data-diagram-detail="${CSS.escape(id)}"]`);
    if (!detail) return false;
    const previous = activeByRoot.get(root);
    if (previous && previous !== detail) restoreDetail(root, previous);
    if (!detail.hasAttribute("data-runtime-open")) {
      if (isNativeDetails(detail)) {
        detail.setAttribute("data-runtime-was-open", String(detail.open));
      } else {
        detail.setAttribute("data-runtime-was-hidden", String(detail.hidden));
      }
    }
    if (isNativeDetails(detail)) {
      detail.open = true;
    } else {
      detail.hidden = false;
    }
    detail.setAttribute("data-runtime-open", "true");
    detail.setAttribute("role", "dialog");
    detail.setAttribute("aria-modal", "false");
    regionFor(detail)?.setAttribute("data-runtime-active", "true");
    activeByRoot.set(root, detail);
    returnFocusByRoot.set(root, trigger || detail.ownerDocument.activeElement);
    ensureCloseButton(root, detail);
    reflect(root, id, true);
    syncDocumentState(root);
    place(detail, trigger);
    const view = viewFor(root);
    if (updateHash && view) {
      const nextHash = `#${encodeURIComponent(id)}`;
      if (view.location.hash !== nextHash) {
        view.history.pushState(view.history.state, "", nextHash);
      }
    }
    const focusTarget = detail.querySelector("summary") || detail;
    focusTarget.focus({ preventScroll: true });
    return true;
  };
  const bind = (root = document) => {
    const triggers = root.querySelectorAll(detailTriggerSelector);
    if (!triggers.length) return;
    portalRegions(root);
    syncDocumentState(root);
    triggers.forEach((trigger) => {
      const id = trigger.dataset.detailFor;
      const detail = id
        ? root.querySelector(`[data-diagram-detail="${CSS.escape(id)}"]`)
        : null;
      if (!detail || trigger.dataset.diagramDetailBound === "true") return;
      trigger.dataset.diagramDetailBound = "true";
      trigger.setAttribute("aria-controls", detail.id);
      reflect(root, id, false);
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        open(root, id, trigger);
      });
      if (isNativeDetails(detail) && detail.dataset.diagramToggleBound !== "true") {
        detail.dataset.diagramToggleBound = "true";
        detail.addEventListener("toggle", () => {
          const runtimeOpen = detail.getAttribute("data-runtime-open") === "true";
          if (runtimeOpen && !detail.open) close(root, true);
          else reflect(root, id, detail.open);
        });
      }
    });
    if (boundRoots.has(root)) return;
    boundRoots.add(root);
    root.addEventListener("pointerdown", (event) => {
      const detail = activeByRoot.get(root);
      if (!detail) return;
      const trigger = returnFocusByRoot.get(root);
      if (!detail.contains(event.target) && !trigger?.contains(event.target)) {
        close(root, false);
      }
    });
    root.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && close(root, true)) event.preventDefault();
    });
    const view = viewFor(root);
    const openFromHash = () => {
      if (!view?.location.hash) return false;
      const id = decodedHashFor(view);
      return open(root, id, null, false);
    };
    view?.addEventListener("hashchange", () => {
      if (!openFromHash()) close(root, false, false);
    });
    const reposition = () => {
      const detail = activeByRoot.get(root);
      if (detail) place(detail, returnFocusByRoot.get(root));
    };
    view?.addEventListener("resize", reposition);
    view?.addEventListener("scroll", reposition, true);
    openFromHash();
  };
  const auditLifecycle = (root = document) => {
    const view = viewFor(root);
    const documentElement = documentElementFor(root);
    const triggers = Array.from(root.querySelectorAll(detailTriggerSelector));
    const auditKey = `${view?.innerWidth || 0}x${view?.innerHeight || 0}:${triggers.length}`;
    const cached = lifecycleAuditByRoot.get(root);
    if (cached?.key === auditKey) return cached.result;
    const issues = new Set();
    const originalHash = view?.location.hash || "";
    const originalFocus = root.activeElement;
    const uniqueTriggers = new Map();
    triggers.forEach((trigger) => {
      const id = (trigger.dataset.detailFor || "").trim();
      if (id && !uniqueTriggers.has(id)) uniqueTriggers.set(id, trigger);
    });
    const viewportPlacement = (element) => {
      if (!element || !view) {
        return { fits: false, trace: "missing" };
      }
      const rect = element.getBoundingClientRect();
      const fits = (
        rect.left >= -1
        && rect.top >= -1
        && rect.right <= view.innerWidth + 1
        && rect.bottom <= view.innerHeight + 1
      );
      return {
        fits,
        trace: [
          Math.round(rect.left),
          Math.round(rect.top),
          Math.round(rect.right),
          Math.round(rect.bottom),
          view.innerWidth,
          view.innerHeight
        ].join(",")
      };
    };
    uniqueTriggers.forEach((trigger, id) => {
      if (!open(root, id, trigger, false)) {
        issues.add(`open:${id}`);
        return;
      }
      const detail = activeByRoot.get(root);
      const grid = gridFor(detail);
      if (
        detail?.dataset.diagramDetail !== id
        || detail.getAttribute("role") !== "dialog"
        || !regionFor(detail)?.hasAttribute("data-runtime-active")
        || !detail.querySelector(":scope > [data-diagram-detail-close]")
      ) {
        issues.add(`dialog-state:${id}`);
      }
      place(detail, trigger);
      const placement = viewportPlacement(grid);
      if (!placement.fits) issues.add(`placement:${id}:${placement.trace}`);
      if (!close(root, true, false)) issues.add(`close:${id}`);
      if (root.activeElement !== trigger) issues.add(`focus-return:${id}`);
    });
    const first = uniqueTriggers.entries().next().value;
    if (first) {
      const [id, trigger] = first;
      open(root, id, trigger, false);
      root.dispatchEvent(
        new view.KeyboardEvent("keydown", { key: "Escape", bubbles: true })
      );
      if (activeByRoot.has(root) || root.activeElement !== trigger) {
        issues.add(`escape:${id}`);
        close(root, true, false);
      }
      open(root, id, trigger, false);
      const pointerTarget = root.body || documentElement;
      pointerTarget.dispatchEvent(
        new view.Event("pointerdown", { bubbles: true, cancelable: true })
      );
      if (activeByRoot.has(root)) {
        issues.add(`outside:${id}`);
        close(root, false, false);
      }
      if (view?.history) {
        view.history.replaceState(view.history.state, "", `#${encodeURIComponent(id)}`);
        view.dispatchEvent(new view.HashChangeEvent("hashchange"));
        if (activeByRoot.get(root)?.dataset.diagramDetail !== id) {
          issues.add(`deep-link:${id}`);
        }
        close(root, false, false);
        view.history.replaceState(
          view.history.state,
          "",
          `${view.location.pathname}${view.location.search}${originalHash}`
        );
      }
    }
    if (originalFocus?.isConnected && typeof originalFocus.focus === "function") {
      originalFocus.focus({ preventScroll: true });
    }
    const ordered = Array.from(issues).sort();
    const result = Object.freeze({
      count: uniqueTriggers.size,
      issues: Object.freeze(ordered),
      passed: ordered.length === 0
    });
    lifecycleAuditByRoot.set(root, { key: auditKey, result });
    documentElement.dataset.detailLifecycleAudit = result.passed ? "passed" : "failed";
    documentElement.dataset.detailLifecycleCount = String(result.count);
    if (ordered.length) {
      documentElement.dataset.detailLifecycleIssues = ordered.join("|").slice(0, 2048);
    } else {
      delete documentElement.dataset.detailLifecycleIssues;
    }
    return result;
  };
  const enhance = (root = document) => bind(root);
  globalThis.VibeDiagramDisclosure = Object.freeze({
    auditLifecycle,
    bind,
    close,
    enhance,
    open,
    reset
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhance(), { once: true });
  } else {
    enhance();
  }
})();
