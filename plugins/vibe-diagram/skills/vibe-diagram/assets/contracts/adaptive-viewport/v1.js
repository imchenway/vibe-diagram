(() => {
  "use strict";
  const allowed = new Set(["fit", "0.75", "0.9", "1"]);
  const managed = new Set();
  const requestedByCanvas = new WeakMap();
  let resizeFrame = 0;

  const stageFor = (canvas) => canvas.querySelector(":scope > [data-diagram-stage]");
  const controlsFor = (canvas, root = document) =>
    Array.from(root.querySelectorAll("[data-diagram-controls]")).filter(
      (controls) => controls.dataset.diagramControls === canvas.dataset.diagramId
    );
  const reset = (canvas) => {
    canvas.style.removeProperty("--diagram-scale");
    canvas.removeAttribute("data-diagram-scaled");
  };
  const reflect = (controls, requested, applied, message) => {
    controls.querySelectorAll("[data-diagram-zoom-control]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.diagramZoomControl === requested && applied)
      );
    });
    const status = controls.querySelector("[data-diagram-zoom-status]");
    if (status) {
      status.textContent = message;
      if ("value" in status) status.value = message;
    }
  };
  const revealControls = (canvas, visible, overflow, root = document) => {
    controlsFor(canvas, root).forEach((controls) => {
      controls.hidden = !visible;
      controls.dataset.diagramControlsVisible = String(visible);
      controls.dataset.diagramOverflow = String(overflow);
    });
  };
  const retest = (canvas, requested = requestedByCanvas.get(canvas) || canvas.dataset.diagramZoom || "fit") => {
    reset(canvas);
    if (!allowed.has(requested)) requested = "fit";
    requestedByCanvas.set(canvas, requested);
    const stage = stageFor(canvas);
    if (!stage || !canvas.clientWidth || !stage.scrollWidth) {
      revealControls(canvas, false, false);
      return false;
    }
    const overflow = stage.scrollWidth > canvas.clientWidth + 1;
    const persistent = canvas.dataset.diagramControlsMode === "persistent";
    const controlsVisible = persistent || overflow;
    revealControls(canvas, controlsVisible, overflow);
    const controls = controlsFor(canvas);
    if (!controlsVisible) {
      controls.forEach((item) =>
        reflect(
          item,
          "fit",
          true,
          item.dataset.diagramStatusFits || "Fits at 100%"
        )
      );
      return true;
    }
    const scale = requested === "fit"
      ? Math.min(1, canvas.clientWidth / stage.scrollWidth)
      : Number(requested);
    const applied = Number.isFinite(scale) && scale >= 0.75 && scale <= 1;
    if (applied) {
      canvas.style.setProperty("--diagram-scale", String(scale));
      canvas.setAttribute("data-diagram-scaled", "true");
    }
    controls.forEach((item) => {
      const message = applied
        ? (
          requested === "fit"
            ? (
              overflow
                ? item.dataset.diagramStatusFit || "Fit width"
                : item.dataset.diagramStatusFits || "Fits at 100%"
            )
            : `${Number(requested) * 100}%`
        )
        : item.dataset.diagramStatusScroll || "Scroll";
      reflect(item, requested, applied, message);
    });
    return applied;
  };
  const apply = (canvas, requested = "fit") => {
    if (!allowed.has(requested)) return false;
    return retest(canvas, requested);
  };
  const scheduleRetest = () => {
    if (resizeFrame) return;
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0;
      managed.forEach((canvas) => retest(canvas));
    });
  };
  const bind = (root = document) => {
    root.querySelectorAll("[data-diagram-controls]").forEach((controls) => {
      const id = controls.dataset.diagramControls;
      const canvas = id
        ? Array.from(root.querySelectorAll("[data-diagram-id]")).find(
            (candidate) => candidate.dataset.diagramId === id
          )
        : null;
      if (!canvas || controls.dataset.diagramBound === "true") return;
      controls.dataset.diagramBound = "true";
      controls.hidden = true;
      controls.addEventListener("click", (event) => {
        const button = event.target.closest("[data-diagram-zoom-control]");
        if (!button || !controls.contains(button)) return;
        const requested = button.dataset.diagramZoomControl;
        apply(canvas, requested);
      });
    });
  };
  const resizeObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(scheduleRetest)
    : null;
  const enhance = (root = document) => {
    bind(root);
    root.querySelectorAll('[data-diagram-canvas][data-diagram-contract="1"]')
      .forEach((canvas) => {
        try {
          if (!managed.has(canvas)) {
            managed.add(canvas);
            if (resizeObserver) {
              resizeObserver.observe(canvas);
              const stage = stageFor(canvas);
              if (stage) resizeObserver.observe(stage);
            }
          }
          retest(canvas, canvas.dataset.diagramZoom || "fit");
        } catch (_error) {
          reset(canvas);
          revealControls(canvas, false, false, root);
        }
      });
  };
  if (!resizeObserver) globalThis.addEventListener("resize", scheduleRetest, { passive: true });
  globalThis.VibeDiagramViewport = Object.freeze({ apply, bind, enhance, reset, retest });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhance(), { once: true });
  } else {
    enhance();
  }
})();
