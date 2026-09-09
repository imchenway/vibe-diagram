# 运行步骤

## 编写

1. 读取请求和真实证据，形成私有 Diagram Brief：产品问题、结论、业务影响、规则、关键事实、证据状态和验收含义。
2. 按关系选择五种基础图法中的必要部分，读取 at most two 指导。Diagram Brief 不是第二套渲染输入。
3. 图形先读取 [原生生成入口](native-engine.md) 及对应包内 schema。事实与关系只写入一份图形源，覆盖清单只映射问题、事实与证据。生成命令调用包内固定引擎及完整查看器，不从 docs、研究 checkout、CDN 或另一技能目录取得运行代码。

```sh
python3 <skill-root>/scripts/vibe_diagram_build.py --input <diagram.json> --manifest <coverage.json> --output <draft.html>
```

实体数量关系以及原生图类不能准确表达的复杂组合，编写有语义标记的独立 SVG，使用同一个查看器：

```sh
python3 <skill-root>/scripts/vibe_diagram_build.py --svg <diagram.svg> --manifest <coverage.json> --summary '<业务结论与规则>' --output <draft.html>
```

命令拒绝覆盖已有输出；源或布局失败时先修输入，不能删关系、关闭质量门禁或拼另一套简化运行代码。

## 检查独立候选

```sh
python3 <skill-root>/scripts/vibe_diagram_lint.py <draft.html> --json
python3 <skill-root>/scripts/vibe_diagram_artifact.py prepare --input <draft.html> --output <candidate.html>
```

修改已有图时加 `--previous <previous.html>`，候选内显示按稳定编号得出的新增、删除、内容变化和手工几何变化。两份图必须有相同 artifactId；不能根据文字相似程度猜身份。自动排版的位置变化不计作内容变化。历史 HTML 只解析，不执行脚本。原生内容若需要元素级对比，可在有稳定编号的元素上标记 `data-vd-compare`。

保存 prepare 返回的完整文件 SHA-256 和字节数；它只证明静态检查和文件一致性。候选修改后必须重新 prepare，不能沿用旧浏览器记录。候选不能覆盖草稿或上一份交付图。

在当前宿主提供的真实浏览器中打开该候选，等待字体与原生查看器初始化完成，分别以 1440×900、1280×800、390×844 检查。运行 `VibeDiagramQuality.receipt()`，把三次真实返回值原样保存到一个 JSON 数组文件。每次必须 status=passed、issues=[]，页面上的错误提示可定位具体元素。没有可用浏览器时保留为未验候选，不能模拟记录。

检查缩放、窄屏视图内横滚、节点点击/Enter/空格高亮与 Esc 恢复；存在详情时检查开关和焦点返回；存在对比时检查新增、删除及变化。检查名称查找、上下游和两点路径，反向不可达时不能留着旧路径。播放时核对真实线段、时间推进、暂停与章节停止，减少动效与后台应保留完整静态内容。实际生成图片，核对背景、网格、标题字号和图注完整且没有临时高亮或描线；重新打开下载的 HTML，不能重复初始化工具条。复制图片需记录真实权限结果，不能将失败算作成功。打印保留完整阅读内容。默认阅读使用清晰的自然比例，窄屏在图内横滚；主动缩放和地图总览由原生镜头控制。页面只使用页面级纵向滚动。

关闭详情完成产品阅读：每个关键问题能否从摘要和主要视图得到答案，业务结论、影响、规则、决策、验收及待确认事项是否清楚，精确证据是否仍可追溯。将实际阅读结论写入交付参数，不能用静态通过代替阅读。

失败后只修候选或草稿，保留原交付文件。最多修复三轮仍失败时说明具体问题与未验层，不删关系、藏事实、缩字或放宽检查器来通过。

## 安全交付

```sh
python3 <skill-root>/scripts/vibe_diagram_artifact.py accept --input <candidate.html> --output <final.html> --sha256 <prepare返回的指纹> --report <browser-checks.json> --reading-review '<实际产品阅读结论>'
```

已有 final.html 时必须加 `--previous-sha256 <旧文件完整指纹>`，防止覆盖其他修改。命令检查同一份冻结字节、候选标识、浏览器视口和阅读声明后原子替换；失败不替换最终文件。只返回成功后才提供 final.html 的可点击绝对路径。保留命令返回的最终指纹及字节数，文件一变原凭据即失效。

浏览器记录和阅读声明来自实际观察者，交付命令只能检查绑定与记录内容，不能证明观察者做过这些操作。不得伪造 passed。若浏览器暂不可用，只可交付明确标注未验的 candidate，不能声称 accepted。

证据分别表述：artifact-static-valid 是静态结构通过；browser-layout-verified 是指定视口真实检查通过；product-reading-reviewed 是实际产品阅读通过；client-runtime-verified 还需要真实客户端安装、发现、调用、输出、交付、升级与卸载。它们互不替代。
