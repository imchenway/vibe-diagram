(() => {
  "use strict";
  const isNativeDetails = (detail) => detail.matches("details");
  const reset = (root = document) => {
    root.querySelectorAll("[data-diagram-detail][data-runtime-open]").forEach((detail) => {
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
    });
  };
  const open = (root, id) => {
    const detail = root.querySelector(`[data-diagram-detail="${CSS.escape(id)}"]`);
    if (!detail) return false;
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
    const focusTarget = isNativeDetails(detail)
      ? detail.querySelector("summary") || detail
      : detail;
    focusTarget.focus({ preventScroll: false });
    return true;
  };
  globalThis.VibeDiagramDisclosure = Object.freeze({ open, reset });
})();
