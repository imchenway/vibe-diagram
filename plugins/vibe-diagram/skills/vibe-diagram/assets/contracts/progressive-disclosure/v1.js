(() => {
  "use strict";
  const activeByRoot = new WeakMap();
  const returnFocusByRoot = new WeakMap();
  const boundRoots = new WeakSet();
  const isNativeDetails = (detail) => detail.matches("details");
  const documentElementFor = (root) =>
    root.nodeType === Node.DOCUMENT_NODE ? root.documentElement : root.ownerDocument.documentElement;
  const triggersFor = (root, id) =>
    Array.from(root.querySelectorAll("[data-diagram-node-id][data-detail-for]")).filter(
      (trigger) => trigger.dataset.detailFor === id
    );
  const reflect = (root, id, expanded) => {
    triggersFor(root, id).forEach((trigger) => {
      trigger.setAttribute("aria-expanded", String(expanded));
    });
  };
  const regionFor = (detail) => detail.closest("[data-node-detail-region]");
  const gridFor = (detail) => detail.closest("[data-node-detail-grid]");
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
    const popupWidth = Math.min(width, popupRect.width || width);
    const popupHeight = Math.min(
      popupRect.height || 240,
      Math.max(160, viewportHeight - margin * 2)
    );
    const triggerRect = trigger?.getBoundingClientRect();
    let left = clamp((viewportWidth - popupWidth) / 2, margin, viewportWidth - popupWidth - margin);
    let top = clamp((viewportHeight - popupHeight) / 2, margin, viewportHeight - popupHeight - margin);
    let side = "center";
    if (triggerRect) {
      if (triggerRect.right + gap + popupWidth <= viewportWidth - margin) {
        left = triggerRect.right + gap;
        side = "right";
      } else if (triggerRect.left - gap - popupWidth >= margin) {
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
  const close = (root = document, restoreFocus = true) => {
    const detail = activeByRoot.get(root);
    if (!detail) return false;
    restoreDetail(root, detail);
    activeByRoot.delete(root);
    syncDocumentState(root);
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
  const open = (root, id, trigger = null) => {
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
    const focusTarget = detail.querySelector("summary") || detail;
    focusTarget.focus({ preventScroll: true });
    return true;
  };
  const bind = (root = document) => {
    const triggers = root.querySelectorAll("[data-diagram-node-id][data-detail-for]");
    if (!triggers.length) return;
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
    const view = root.nodeType === Node.DOCUMENT_NODE
      ? root.defaultView
      : root.ownerDocument.defaultView;
    const reposition = () => {
      const detail = activeByRoot.get(root);
      if (detail) place(detail, returnFocusByRoot.get(root));
    };
    view?.addEventListener("resize", reposition);
    view?.addEventListener("scroll", reposition, true);
  };
  const enhance = (root = document) => bind(root);
  globalThis.VibeDiagramDisclosure = Object.freeze({ bind, close, enhance, open, reset });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhance(), { once: true });
  } else {
    enhance();
  }
})();
