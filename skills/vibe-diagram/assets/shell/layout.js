/* 自动排版只移动已编写的元素；不推断业务关系，也不缩小文字。 */
(() => {
  "use strict";
  // 节点外侧留白，兼顾箭头和文字。
  const gap = 64;
  // 统一读取当前 SVG 内的标记。
  const all = (selector, root) => Array.from(root.querySelectorAll(selector));
  // 判断线段是否进入矩形内部，贴边由调用方的安全边距控制。
  const hits = (a, b, r) => a.x === b.x
    ? a.x > r.x && a.x < r.x + r.w && Math.max(a.y, b.y) > r.y && Math.min(a.y, b.y) < r.y + r.h
    : a.y > r.y && a.y < r.y + r.h && Math.max(a.x, b.x) > r.x && Math.min(a.x, b.x) < r.x + r.w;
  // 保留完整端点，删除相邻共线点。
  function simplify(points) {
    return points.filter((point, index) => !index || index === points.length - 1 ||
      !((points[index - 1].x === point.x && point.x === points[index + 1].x) ||
        (points[index - 1].y === point.y && point.y === points[index + 1].y)));
  }
  // 在障碍边界组成的正交网格中搜索最短折线路径。
  function route(start, end, obstacles, used = []) {
    // ponytail: 网格随障碍数量平方增长；大图先分视图，确需百节点密图时再换稀疏可见性图。
    const xs = [...new Set([start.x, end.x, ...obstacles.flatMap(r => [r.x, r.x + r.w])])].sort((a, b) => a - b);
    // 横纵坐标只取可能绕行的边界。
    const ys = [...new Set([start.y, end.y, ...obstacles.flatMap(r => [r.y, r.y + r.h])])].sort((a, b) => a - b);
    // 搜索键使用网格下标，避免坐标字符串精度混淆。
    const key = (x, y) => y * xs.length + x;
    // 路径距离与前驱只保存已到达的点。
    const begin = key(xs.indexOf(start.x), ys.indexOf(start.y)), finish = key(xs.indexOf(end.x), ys.indexOf(end.y));
    // 优先队列按估算总路程排序；小型视图用数组即可。
    const queue = [{ id: begin, cost: 0, score: 0 }], costs = new Map([[begin, 0]]), previous = new Map();
    while (queue.length) {
      queue.sort((a, b) => b.score - a.score || b.id - a.id);
      // 跳过已被更短路径替代的队列项。
      const current = queue.pop();
      if (current.cost !== costs.get(current.id)) continue;
      if (current.id === finish) {
        // 从终点回溯，起终点都必须保留。
        const points = [];
        for (let id = finish; id !== undefined; id = previous.get(id)) points.push({ x: xs[id % xs.length], y: ys[Math.floor(id / xs.length)] });
        return simplify(points.reverse());
      }
      // 每个网格点只尝试上下左右四个相邻点。
      const x = current.id % xs.length, y = Math.floor(current.id / xs.length), a = { x: xs[x], y: ys[y] };
      for (const [nx, ny] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        if (nx < 0 || ny < 0 || nx >= xs.length || ny >= ys.length) continue;
        // 线段不得进入节点或已放置标签。
        const b = { x: xs[nx], y: ys[ny] }, id = key(nx, ny);
        if (obstacles.some(r => hits(a, b, r))) continue;
        // 曼哈顿距离作为可重复的搜索权重。
        const overlap = used.flatMap(path => path.slice(1).map((q, index) => {
          const p = path[index];
          if (a.x === b.x && p.x === q.x && a.x === p.x) return Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(p.y, q.y)) - Math.max(Math.min(a.y, b.y), Math.min(p.y, q.y)));
          if (a.y === b.y && p.y === q.y && a.y === p.y) return Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(p.x, q.x)) - Math.max(Math.min(a.x, b.x), Math.min(p.x, q.x)));
          return 0;
        })).reduce((sum, value) => sum + value, 0);
        const cost = current.cost + Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + overlap * 4;
        if (cost >= (costs.get(id) ?? Infinity)) continue;
        costs.set(id, cost); previous.set(id, current.id);
        queue.push({ id, cost, score: cost + Math.abs(b.x - end.x) + Math.abs(b.y - end.y) });
      }
    }
    throw new Error("没有可用的避障路线；请增加留白或拆分视图。");
  }
  // 根据有向关系分层；环内保持作者的节点顺序，避免无限追溯。
  function ranks(nodes, edges) {
    // 只忽略排序用的回边，实际关系从不删除。
    const visiting = new Set(), visited = new Set(), forward = [], order = [];
    // 深度优先识别回边，不将图中回路当作输入错误。
    function visit(id) {
      if (visited.has(id)) return;
      visiting.add(id);
      for (const edge of edges.filter(e => e.from === id)) {
        if (visiting.has(edge.to)) continue;
        forward.push(edge); visit(edge.to);
      }
      visiting.delete(id); visited.add(id); order.unshift(id);
    }
    nodes.forEach(node => visit(node.id));
    // 最长前向路径保证分支汇合出现在分支之后。
    const result = new Map(nodes.map(node => [node.id, 0]));
    order.forEach(id => forward.filter(e => e.from === id).forEach(e => result.set(e.to, Math.max(result.get(e.to), result.get(id) + 1))));
    return result;
  }
  // 测量文字并扩展作者选定的基础形状，保持字号与换行。
  function measure(element) {
    // 自动节点必须明确主体形状，复杂组合留给手工编排。
    const shape = element.querySelector("[data-vd-shape]"), texts = all("text", element);
    if (!shape || !["rect", "ellipse", "polygon"].includes(shape.localName) || !texts.length) throw new Error(element.id + "：自动节点需要主体形状和可见文字。");
    // 标签整体范围用于分配足够空间。
    const boxes = texts.map(text => text.getBBox()), left = Math.min(...boxes.map(b => b.x)), top = Math.min(...boxes.map(b => b.y));
    // 判定形状类型，菱形为决策文字额外留出四角。
    const diamond = shape.localName === "polygon", original = shape.getBBox();
    // 尺寸是测量值与作者最小尺寸中较大者。
    const w = Math.ceil(Math.max(original.width, (Math.max(...boxes.map(b => b.x + b.width)) - left + 32) * (diamond ? 2 : 1)));
    // 多行文本按真实高度计算，不假定固定字数。
    const h = Math.ceil(Math.max(original.height, (Math.max(...boxes.map(b => b.y + b.height)) - top + 28) * (diamond ? 2 : 1)));
    if (![w, h].every(value => Number.isFinite(value) && value > 0)) throw new Error(element.id + "：节点尺寸不可用。");
    if (shape.localName === "rect") Object.entries({ x: 0, y: 0, width: w, height: h }).forEach(([key, value]) => shape.setAttribute(key, value));
    else if (shape.localName === "ellipse") Object.entries({ cx: w / 2, cy: h / 2, rx: w / 2, ry: h / 2 }).forEach(([key, value]) => shape.setAttribute(key, value));
    else shape.setAttribute("points", [w / 2 + ",0", w + "," + h / 2, w / 2 + "," + h, "0," + h / 2].join(" "));
    // 平移所有标签而不重排 tspan，保留作者指定的行序。
    texts.forEach(text => {
      // 首次测量后保存标签原始位置，重复布局不累加平移。
      const originalTransform = text.dataset.vdTextTransform ?? text.getAttribute("transform") ?? "";
      text.dataset.vdTextTransform = originalTransform;
      text.setAttribute("transform", "translate(" + (w / 2 - (left + Math.max(...boxes.map(b => b.x + b.width))) / 2) + " " + (h / 2 - (top + Math.max(...boxes.map(b => b.y + b.height))) / 2) + ") " + originalTransform);
    });
    return { id: element.id, element, shape: shape.localName, w, h, x: 0, y: 0, group: element.dataset.vdMemberOf || "" };
  }
  // 锚点落在真实形状上；椭圆和菱形不能拿包围矩形代替边界。
  function port(node, side, fraction) {
    const vertical = side === "top" || side === "bottom", offset = fraction * (vertical ? node.w : node.h);
    const extent = node.shape === "polygon" ? 1 - Math.abs(fraction) * 2 : node.shape === "ellipse" ? Math.sqrt(1 - (fraction * 2) ** 2) : 1;
    return vertical ? { x: node.x + node.w / 2 + offset, y: node.y + node.h / 2 + (side === "bottom" ? 1 : -1) * node.h / 2 * extent }
      : { x: node.x + node.w / 2 + (side === "right" ? 1 : -1) * node.w / 2 * extent, y: node.y + node.h / 2 + offset };
  }
  // 将路径及其标签安排在节点之间；已放标签也成为后续连线的障碍。
  function connect(edges, nodes, svg) {
    // 障碍安全边距给箭头和文字留空，不改变实际端点。
    const obstacles = nodes.map(n => ({ x: n.x - 16, y: n.y - 16, w: n.w + 32, h: n.h + 32 }));
    // 记录已有线路，后续标签不能遮住它们。
    const drawn = [];
    for (const edge of edges) {
      // 选择面向目标的出入口，自环使用相邻的两个边。
      const a = nodes.find(n => n.id === edge.from), b = nodes.find(n => n.id === edge.to);
      // 自动分层默认向下；同层或回路改走左右通道。
      const down = b.y > a.y + a.h, up = a.y > b.y + b.h;
      // 平行边用不同端口；相同关系的多条线路保持独立。
      const outgoing = edges.filter(e => e.from === edge.from), incoming = edges.filter(e => e.to === edge.to);
      // 端口分布于边的中间一半，相同端点的多条关系仍各自可见。
      const fromFraction = ((outgoing.indexOf(edge) + 1) / (outgoing.length + 1) - 0.5) / 2;
      // 入边同样独立分配，合法汇合依然保留真实目标。
      const toFraction = ((incoming.indexOf(edge) + 1) / (incoming.length + 1) - 0.5) / 2;
      // 起终点的短接入段只穿过自身节点的安全边距。
      const start = port(a, down ? "bottom" : "right", fromFraction);
      // 自环从右侧绕回顶侧。
      const end = port(b, a === b || down ? "top" : up ? "right" : "left", toFraction);
      // 路由仅在节点外搜索，防止切入端点主体。
      const outsideStart = down ? { x: start.x, y: a.y + a.h + 16 } : { x: a.x + a.w + 16, y: start.y };
      // 目标外侧坐标与目标锚点同一法线。
      const outsideEnd = a === b || down ? { x: end.x, y: b.y - 16 } : up ? { x: b.x + b.w + 16, y: end.y } : { x: b.x - 16, y: end.y };
      // 标签先布置在线段旁，再接入后续障碍列表。
      const points = simplify([start, ...route(outsideStart, outsideEnd, obstacles, drawn), end]);
      edge.element.setAttribute("d", points.map((p, index) => (index ? "L" : "M") + p.x + " " + p.y).join(" "));
      // 同一关系可有多个标签，例如数量关系的两端。
      const labels = all("[data-vd-edge-label]", svg).filter(label => label.dataset.vdEdgeLabel === edge.element.id);
      for (const label of labels) {
        // 标签在水平/垂直段旁依次尝试；无法放置时明确失败。
        const box = label.getBBox();
        let placed = false;
        for (let index = 1; index < points.length && !placed; index += 1) {
          // 枚举段中间及四分点，避免多个标签抢同一位置。
          const p = points[index - 1], q = points[index];
          for (const fraction of [0.5, 0.25, 0.75]) {
            // 标签与线路之间留出可见空隙。
            const x = p.x + (q.x - p.x) * fraction, y = p.y + (q.y - p.y) * fraction;
            for (const side of [-1, 1]) {
              // 每个候选均检查所有节点、标签和既有线路。
              const r = p.y === q.y ? { x: x - box.width / 2, y: y + (side < 0 ? -box.height - 8 : 8), w: box.width, h: box.height }
                : { x: x + (side < 0 ? -box.width - 8 : 8), y: y - box.height / 2, w: box.width, h: box.height };
              if (obstacles.some(o => r.x < o.x + o.w && r.x + r.w > o.x && r.y < o.y + o.h && r.y + r.h > o.y)) continue;
              if ([...drawn, points].some(path => path.slice(1).some((point, i) => hits(path[i], point, r)))) continue;
              label.setAttribute("transform", "translate(" + (r.x - box.x) + " " + (r.y - box.y) + ")");
              obstacles.push({ x: r.x - 4, y: r.y - 4, w: r.w + 8, h: r.h + 8 });
              placed = true; break;
            }
            if (placed) break;
          }
        }
        if (!placed) throw new Error(label.id + "：关系标签没有足够留白，请拆行或增加布局间距。");
      }
      drawn.push(points);
    }
  }
  // 单个自动 SVG 的排版入口，失败时恢复整个 SVG，不留下半幅新图。
  function layout(svg) {
    // 元素副本仅用于出错回滚，成功路径保留原 DOM 身份。
    const saved = svg.innerHTML, attributes = Array.from(svg.attributes).map(a => [a.name, a.value]);
    try {
      // 自动布局只接受同一坐标系内的节点和线路。
      const nodeElements = all("[data-vd-node]", svg), edgeElements = all("[data-vd-edge]", svg);
      if (!nodeElements.length || nodeElements.some(n => n.localName !== "g" || n.parentElement !== svg) || edgeElements.some(e => e.localName !== "path" || e.parentElement !== svg)) throw new Error("自动布局要求节点 g 与连线 path 直接位于同一个 SVG；嵌套边界请手工编排。");
      // 节点身份必须唯一，连线只能引用当前 SVG 的节点。
      const ids = new Set(nodeElements.map(n => n.id));
      if (ids.size !== nodeElements.length || ids.has("")) throw new Error("自动布局存在重复或缺失的节点编号。");
      // 每条关系保留作者提供的方向和类型。
      const edges = edgeElements.map(element => ({ element, from: element.dataset.from, to: element.dataset.to }));
      if (edges.some(e => !ids.has(e.from) || !ids.has(e.to))) throw new Error("连线端点不存在于当前 SVG。");
      // 实测文字后再决定节点尺寸。
      const nodes = nodeElements.map(measure), sequence = svg.closest("[data-vd-family]")?.dataset.vdFamily === "code-sequence";
      // 行距随最长标签增长，避免长文案占用相邻步骤。
      const labels = all("[data-vd-edge-label]", svg), labelWidth = Math.max(0, ...labels.map(l => l.getBBox().width));
      // 作者可以增大而不能压缩默认安全间距。
      const spacing = Math.max(gap, Number(svg.dataset.vdGap) || gap, labelWidth + 40);
      // 真实边界独立占列，未归属节点也保持独立列。
      const groups = all("[data-vd-group]", svg), groupIds = groups.map(g => g.id);
      if (groups.some(g => g.parentElement !== svg || !g.id || !g.querySelector("rect")) || new Set(groupIds).size !== groups.length || nodes.some(n => n.group && !groupIds.includes(n.group))) throw new Error("自动边界需要独立编号和矩形；节点归属必须存在。");
      // 时序参与者按作者顺序横排，消息顺序保持 DOM 顺序。
      if (sequence) {
        if (groups.length) throw new Error("带片段边界的时序请手工编排，避免推断片段范围。");
        let cursor = gap;
        nodes.forEach(n => { n.x = cursor; n.y = gap; cursor += n.w + spacing; });
      } else {
        // 普通关系、流程、状态和数据关系共用分层与避障。
        const levels = ranks(nodes, edges), lanes = [...new Set(nodes.map(n => n.group))];
        let x = gap;
        for (const lane of lanes) {
          // 同层同归属的节点横向排列，分支不互相覆盖。
          const members = nodes.filter(n => n.group === lane), rows = [...new Set(members.map(n => levels.get(n.id)))].sort((a, b) => a - b);
          let width = 0;
          for (const row of rows) {
            let cursor = x;
            members.filter(n => levels.get(n.id) === row).forEach(n => { n.x = cursor; cursor += n.w + spacing; });
            width = Math.max(width, cursor - x - spacing);
          }
          x += width + spacing;
        }
        // 所有归属共享层高，跨归属交接不丢失阅读顺序。
        let y = gap + (groups.length ? 40 : 0);
        for (const row of [...new Set(levels.values())].sort((a, b) => a - b)) {
          const members = nodes.filter(n => levels.get(n.id) === row);
          members.forEach(n => { n.y = y; }); y += Math.max(...members.map(n => n.h)) + spacing;
        }
      }
      nodes.forEach(n => n.element.setAttribute("transform", "translate(" + n.x + " " + n.y + ")"));
      if (sequence) {
        // 生命周期线使用真实参与者编号，消息锚定到线而不是标题框。
        const height = gap + Math.max(...nodes.map(n => n.h)) + (edges.length + 1) * gap * 1.5;
        nodes.forEach(n => {
          const line = all("[data-vd-lifeline-for]", svg).find(l => l.dataset.vdLifelineFor === n.id);
          if (!line || line.localName !== "line") throw new Error(n.id + "：缺少独立生命线。");
          Object.entries({ x1: n.x + n.w / 2, x2: n.x + n.w / 2, y1: n.y + n.h, y2: height }).forEach(([key, value]) => line.setAttribute(key, value));
        });
        edges.forEach((edge, index) => {
          const a = nodes.find(n => n.id === edge.from), b = nodes.find(n => n.id === edge.to), y = gap + Math.max(...nodes.map(n => n.h)) + (index + 1) * gap * 1.5;
          const ax = a.x + a.w / 2, bx = b.x + b.w / 2;
          edge.element.setAttribute("d", a === b ? "M" + ax + " " + y + "h40v28h-40" : "M" + ax + " " + y + "H" + bx);
          labels.filter(l => l.dataset.vdEdgeLabel === edge.element.id).forEach((label, i) => {
            const box = label.getBBox();
            // 自调用标签放到回折线外侧，不能让生命线穿过正文。
            const x = a === b ? ax + 52 : (ax + bx) / 2 - box.width / 2;
            label.setAttribute("transform", "translate(" + (x - box.x) + " " + (y - box.y - box.height - 10 - i * (box.height + 6)) + ")");
          });
        });
      } else connect(edges, nodes, svg);
      groups.forEach(group => {
        const members = nodes.filter(n => n.group === group.id);
        if (!members.length) throw new Error(group.id + "：边界没有成员。");
        const x = Math.min(...members.map(n => n.x)) - 24, y = Math.min(...members.map(n => n.y)) - 56;
        Object.entries({ x, y, width: Math.max(...members.map(n => n.x + n.w)) - x + 24, height: Math.max(...members.map(n => n.y + n.h)) - y + 24 }).forEach(([key, value]) => group.querySelector("rect").setAttribute(key, value));
        const title = group.querySelector("text");
        if (title) { title.setAttribute("x", x + 16); title.setAttribute("y", y + 24); }
      });
      // 画布完整包住节点、路线、标签和边界，包括回路的负向留白。
      const box = svg.getBBox(), x = Math.min(0, box.x - 24), y = Math.min(0, box.y - 24), w = Math.ceil(box.x + box.width + gap - x), h = Math.ceil(box.y + box.height + gap - y);
      svg.setAttribute("viewBox", [x, y, w, h].join(" ")); svg.setAttribute("width", w); svg.setAttribute("height", h);
      return [];
    } catch (error) {
      svg.innerHTML = saved;
      Array.from(svg.attributes).forEach(a => svg.removeAttribute(a.name)); attributes.forEach(([key, value]) => svg.setAttribute(key, value));
      return [{ code: "automatic-layout-failed", id: svg.id, detail: String(error.message), hint: "修正该 SVG 的标记或改用手工编排；原内容已恢复。" }];
    }
  }
  // 对已选择自动布局的视图统一执行；其余 HTML 和 SVG 不变。
  globalThis.VibeDiagramLayout = { run: () => all('svg[data-vd-layout="auto"]', document).flatMap(layout), route, ranks };
})();
