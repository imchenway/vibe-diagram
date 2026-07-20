(() => {
  "use strict";
  const allowed = new Set(["fit", "0.75", "0.9", "1"]);
  const reset = (canvas) => {
    canvas.style.removeProperty("--diagram-scale");
    canvas.removeAttribute("data-diagram-scaled");
  };
  const apply = (canvas, requested = "fit") => {
    reset(canvas);
    if (!allowed.has(requested)) return false;
    const stage = canvas.querySelector(":scope > [data-diagram-stage]");
    if (!stage || !canvas.clientWidth || !stage.scrollWidth) return false;
    const scale = requested === "fit"
      ? Math.min(1, canvas.clientWidth / stage.scrollWidth)
      : Number(requested);
    if (!Number.isFinite(scale) || scale < 0.75 || scale > 1) return false;
    canvas.style.setProperty("--diagram-scale", String(scale));
    canvas.setAttribute("data-diagram-scaled", "true");
    return true;
  };
  const enhance = (root = document) => {
    root.querySelectorAll('[data-diagram-canvas][data-diagram-contract="1"]')
      .forEach((canvas) => {
        try {
          apply(canvas, canvas.dataset.diagramZoom || "fit");
        } catch (_error) {
          reset(canvas);
        }
      });
  };
  globalThis.VibeDiagramViewport = Object.freeze({ apply, enhance, reset });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhance(), { once: true });
  } else {
    enhance();
  }
})();
