/* 仅适配原生查看器的背景与导出画布；关系、镜头、动效和文件编码沿用原生实现。 */
(() => {
  "use strict";
  // 所有元素由浏览器本地生成，无远程图片或字体依赖。
  const namespace = "http://www.w3.org/2000/svg";

  // 创建原生 SVG 元素，避免位图导出依赖 foreignObject。
  function element(name, attributes = {}) {
    // 属性来自主题和真实图形边界。
    const node = document.createElementNS(namespace, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  // 读取页面主题，长度沿浏览器当前根字号解析。
  function theme() {
    // 浅色来自原公共主题；深色使用原生主题的现有色值。
    const style = getComputedStyle(document.documentElement);
    // 颜色允许 CSS 原生透明色，避免在背景层二次降低透明度。
    const color = name => style.getPropertyValue(name).trim();
    // 本次主题只使用像素和根字号长度。
    const length = name => parseFloat(color(name)) * (color(name).endsWith("rem") ? parseFloat(style.fontSize) : 1);
    return { color, length, light: document.documentElement.dataset.theme === "light" };
  }

  // 用与页面相同的绘制次序建立导出背景，可用于普通图、分享图和视频底图。
  function background(width, height) {
    // 背景编号使用独立前缀，不与原生箭头或图形编号混用。
    const prefix = "vibe-canvas-", settings = theme(), group = element("g", { "data-vibe-export-canvas": "" });
    if (!settings.light) {
      group.append(element("rect", { width, height, fill: settings.color("--bg") }));
      return group;
    }
    // 先铺纸张底色，再叠网格、绿色与蓝色渐变。
    const defs = element("defs"), paper = element("linearGradient", { id: prefix + "paper", x1: 0, y1: 0, x2: 0, y2: 1 });
    [[0, "--vd-page-top"], [0.55, "--vd-page-middle"], [1, "--vd-page-bottom"]].forEach(([offset, name]) => paper.append(element("stop", { offset, "stop-color": settings.color(name) })));
    defs.append(paper);
    group.append(defs, element("rect", { width, height, fill: "url(#" + paper.id + ")" }));
    // 方格间距与页面参数完全一致。
    const size = settings.length("--vd-grid"), grid = element("pattern", { id: prefix + "grid", width: size, height: size, patternUnits: "userSpaceOnUse" });
    grid.append(element("rect", { width: size, height: 1, fill: settings.color("--vd-grid-ink") }), element("rect", { width: 1, height: size, fill: settings.color("--vd-grid-ink") }));
    defs.append(grid);
    group.append(element("rect", { width, height, fill: "url(#" + grid.id + ")" }));
    for (const [name, x, y] of [["green", 0.88, 0.04], ["blue", 0.12, 0]]) {
      // 渐变半径与起点沿用原公共外壳。
      const wash = element("radialGradient", { id: prefix + name, cx: width * x, cy: height * y, r: settings.length("--vd-wash-" + name + "-radius"), gradientUnits: "userSpaceOnUse" });
      wash.append(element("stop", { offset: 0, "stop-color": settings.color("--vd-wash-" + name) }), element("stop", { offset: 1, "stop-color": settings.color("--vd-wash-" + name), "stop-opacity": 0 }));
      defs.append(wash);
      group.append(element("rect", { width, height, fill: "url(#" + wash.id + ")" }));
    }
    return group;
  }

  // 根据实际字体测量标题和摘要，换行保留所有业务条件。
  function textLines(source, maxWidth, startY, className) {
    // 独立画布只用于测量字宽，不参与图形或路线计算。
    const style = getComputedStyle(source), context = document.createElement("canvas").getContext("2d");
    // 文字字号与当前页面一致，字距同时参与测量。
    const size = parseFloat(style.fontSize), lineHeight = parseFloat(style.lineHeight) || size * 1.5, lines = [];
    context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    if ("letterSpacing" in context) context.letterSpacing = style.letterSpacing === "normal" ? "0px" : style.letterSpacing;
    // 当前行逐字推进，不能通过省略号截断规则。
    let line = "";
    for (const character of source.textContent.trim().replace(/\s+/g, " ")) {
      if (line && context.measureText(line + character).width > maxWidth) { lines.push(line); line = ""; }
      line += character;
    }
    if (line) lines.push(line);
    return {
      nodes: lines.map((content, index) => {
        // 每一行保留当前字体层级及可编辑文字。
        const node = element("text", { x: 32, y: startY + size + index * lineHeight, class: className, "font-size": size, "font-weight": style.fontWeight, "letter-spacing": style.letterSpacing });
        // SVG 作者的通用 text 样式不能覆盖页面标题的真实字号。
        node.style.fontSize = style.fontSize; node.style.fontFamily = style.fontFamily;
        node.style.fontWeight = style.fontWeight; node.style.fill = style.color;
        node.textContent = content;
        return node;
      }),
      height: lines.length * lineHeight + 12
    };
  }

  // 在上游已清理的完整 SVG 外扩画布，原连线坐标、身份和路径选择均不改变。
  function decorateExport(clone, bounds, scale, options) {
    // 分享图已有原生标题；视频逐帧坐标也保持原始范围。
    const diagramOnly = options.diagramOnly === true;
    // 显式平移支持任意原生 viewBox 起点。
    const width = bounds.width + (diagramOnly ? 0 : 64), texts = [];
    // 标题与摘要按真实行数推进，空标题不额外制造占位。
    let top = 24;
    if (!diagramOnly) {
      for (const [selector, className] of [[".header h1", "t-vibe-export-title"], [".header .subtitle", "t-vibe-export-summary"]]) {
        // 文案直接来自页面，不保留第二份业务文字。
        const source = document.querySelector(selector);
        if (source) { const block = textLines(source, width - 64, top, className); texts.push(...block.nodes); top += block.height; }
      }
    }
    // 只给普通图片增加标题；分享和视频继续使用原生画幅。
    const header = diagramOnly ? 0 : top, height = bounds.height + (diagramOnly ? 0 : header + 24);
    // 将原生图形整体平移，不重排、不缩放节点与路线。
    const graph = element("g", { transform: `translate(${(diagramOnly ? 0 : 32) - bounds.x} ${header - bounds.y})` });
    // 保留原生样式；移除单色背景，换成原主题背景。
    const style = clone.querySelector("style"), oldBackground = style && style.nextElementSibling;
    if (oldBackground?.tagName.toLowerCase() === "rect") oldBackground.remove();
    Array.from(clone.childNodes).forEach(node => { if (node !== style) graph.append(node); });
    clone.setAttribute("viewBox", `0 0 ${width} ${height}`);
    // 按含标题的最终画幅限制位图资源，避免原图小而摘要很长时越过像素上限。
    scale = Math.min(scale, 8192 / width, 8192 / height, Math.sqrt(16 * 1024 * 1024 / (width * height)));
    clone.setAttribute("width", width * scale);
    clone.setAttribute("height", height * scale);
    // 图片固定为读者当前主题，避免分享后自动切走原背景。
    clone.setAttribute("data-theme", document.documentElement.dataset.theme || "light");
    clone.append(background(width, height), ...texts, graph);
    // 独立 SVG 包含上游样式与图形代码，许可说明随文件保留。
    const license = JSON.parse(document.getElementById("vibe-upstream-license").textContent);
    clone.insertBefore(document.createComment(license.license + "\n来源：" + license.source), clone.firstChild);
    return { width: width * scale, height: height * scale };
  }

  // 原生分享图继续负责文字与路径范围，只把底色替换为相同纸张背景。
  function paintShareBackground(context, width, height) {
    // 画布颜色读取同一组原主题参数。
    const settings = theme();
    if (!settings.light) { context.fillStyle = settings.color("--bg"); context.fillRect(0, 0, width, height); return; }
    // 线性底色与方格保持和 SVG 一样的顺序。
    const paper = context.createLinearGradient(0, 0, 0, height), spacing = settings.length("--vd-grid");
    [[0, "--vd-page-top"], [0.55, "--vd-page-middle"], [1, "--vd-page-bottom"]].forEach(([offset, name]) => paper.addColorStop(offset, settings.color(name)));
    context.fillStyle = paper; context.fillRect(0, 0, width, height);
    context.fillStyle = settings.color("--vd-grid-ink");
    for (let x = 0; x < width; x += spacing) context.fillRect(x, 0, 1, height);
    for (let y = 0; y < height; y += spacing) context.fillRect(0, y, width, 1);
    for (const [name, x, y] of [["green", 0.88, 0.04], ["blue", 0.12, 0]]) {
      // 透明终点保留原色通道，避免渐变尾部发灰。
      const color = settings.color("--vd-wash-" + name), channels = color.match(/[\d.]+/g), wash = context.createRadialGradient(width * x, height * y, 0, width * x, height * y, settings.length("--vd-wash-" + name + "-radius"));
      wash.addColorStop(0, color); wash.addColorStop(1, `rgba(${channels[0]},${channels[1]},${channels[2]},0)`);
      context.fillStyle = wash; context.fillRect(0, 0, width, height);
    }
  }

  // 热区和动效沿用原路径，只去掉业务检查身份，避免重复关系和假阳性。
  function cloneDecoration(shape) {
    // 不处理完整 SVG 导出，导出原图仍保留真实标记。
    const clone = shape.cloneNode(false);
    Array.from(clone.attributes).filter(attribute => attribute.name.startsWith("data-vd-") || ["data-from", "data-to"].includes(attribute.name)).forEach(attribute => clone.removeAttribute(attribute.name));
    return clone;
  }

  // 仅暴露主题与业务标记适配点，原生功能模块保持完整。
  globalThis.VibeDiagramCanvas = { decorateExport, paintShareBackground, cloneDecoration };
})();
