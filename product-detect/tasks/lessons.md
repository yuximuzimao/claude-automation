# product-detect 教训台账

每条教训对应一次真实失败。格式：**现象 → 根因 → 堵死同类的规则**。

---

## L1 工具/平台行为先查文档定性，再动手在界面里试（2026-06-12）

**现象**：Label Studio 1.23.0 配置了 BrushLabels + RectangleLabels + KeyPointLabels，标注界面只渲染 brush/eraser，矩形工具完全不在 DOM 里。我连续七八次用 agent-browser snapshot / eval / 换 URL / 改视图模式去"在页面里找"矩形工具，全部无效，耗时极长仍未解决。隔壁 agent 同样问题一次解决。

**根因**：把"在页面里翻找症状"当成了"解决问题"。问题的源头是**"BrushLabels 和 RectangleLabels 能不能在同一个 Label Studio 项目共存"**——这是配置问题还是平台已知限制，官方文档/GitHub Issues 一句话就能定性。我跳过了"定性"直接进入"在现场试错"，方向错了还在原地打转，每次 eval 失败只当作"还没找对方法"，没当作"可能这条路本身不通"的信号。

附带浪费：试图用 API token 改配置，结果 legacy token 认证已被禁用（401），又白走两轮——动手前没先探认证方式。

**堵死同类的规则**：
1. **遇到"工具/平台不按预期行为"的问题，第一步是查官方文档 + GitHub Issues 定性**（这是 bug / 限制 / 还是我配置错了），而不是先在界面里 eval 试错。定性 = 选对第一步，比试一百次都值。
2. **连续 2 次同方式无改进 = 方向信号，不是"再试一次"信号**。立即升级到更根本的获取方式（读源码/文档/issue），对应工作区铁律「失败可能是安全/方向信号」。
3. **调 API 前先用最小请求探认证方式**（curl 探一下返回码/认证头），不假设 token 能用。
4. 对应 PUA 反套路：「我需要更多 context」的真相是「有工具，先搜索/读文档，而不是在现场反复试」。

**2026-06-13 Codex 复核修正**：

上面的「BrushLabels 和 RectangleLabels 是否能共存」不是最终根因。浏览器运行态确认：

- `BrushTool`、`RectangleTool`、`KeyPointTool` 实际都已注册到 `image` 的 tools manager。
- 页面只显示 brush/eraser 的直接原因是本地状态 `localStorage.autoAnnotation="false"` / `window.Htx.autoAnnotation=false`。
- 打开 `window.Htx.setAutoAnnotation(true)` 后，右侧竖向工具栏立即出现 `Rectangle`、`3 Point Rectangle`、`Key Point` 和 `Auto-Detect`。
- 当前 Label Studio 页面没有可见文案叫 `Auto-Annotation` 的开关；可见入口叫右侧工具栏底部的 `Auto-Detect`，底部出现的是另一个开关 `Auto-Accept Suggestions`。

补充规则：**不要把代码变量名当成用户可见 UI 文案**。遇到「找不到某个开关」时，必须同时核对 DOM 可见文本、运行态状态、localStorage 和截图；如果页面没有该文案，就直接说明「这个版本没有这个可见开关」，不要让用户去找不存在的按钮。

## L2 Auto-Detect 前端出现不等于自动标注链路可用（2026-06-13）

**现象**：右侧工具栏出现 `Auto-Detect` 和多个智能工具后，用户点击仍不能自动生成外轮廓 mask；第一个像画笔的工具看起来和普通画笔无区别，后面几个粉色工具也不能画框。

**根因**：
- Label Studio 本身不自带识物/分割智能模型，`Auto-Detect` 只是 interactive ML Backend 入口。
- 项目 4 的 ML Backend 虽然连接到 `http://localhost:9090`，但数据库 `ml_mlbackend.is_interactive=0`，前端不会按 interactive preannotation 流程转发用户点击。
- `scripts/sam_ml_backend.py` 的 `predict()` 只 `set_image()` 后固定返回空 `result: []`，没有读取 `kwargs["context"]`、没有把 KeyPoint/Rectangle prompt 转成 SAM 像素坐标、没有调用 `SamPredictor.predict()`、也没有返回 BrushLabels RLE。

**堵死同类的规则**：
1. **看到 Auto-Detect 图标只说明前端工具可见，不说明智能链路可用**；必须同时验证：`ml_mlbackend.is_interactive=1`、`/setup` 成功、`/predict` 带 context 返回非空 `brushlabels`。
2. Label Studio interactive 请求路径是：前端 `POST /api/ml/:id/interactive-annotating` → Label Studio 后端 → ML Backend `/predict`；到 `predict()` 时 context 位于 `kwargs["context"]`。
3. KeyPoint 坐标是 0-100 百分比，SAM 需要像素 `(x, y)`；负点用 `is_positive=false` 转成 `point_labels=0`。
4. 返回给 BrushLabels 的 RLE 是 Label Studio brush RLE `list[int]`，不是 COCO RLE，也不是 base64 字符串。
5. 后端必须用持久方式运行。本机当前用 launchd 服务 `com.chat.product-detect-sam-backend`，日志 `/tmp/sam_backend.log`。

## L3 架构层的脆弱链路，换工具比修接点更值（2026-06-15）

**现象**：为让 Label Studio 自动出 mask，反复修 L1/L2 里的外挂 SAM backend（前端→LS→9090 backend 三段链路），每修好一段又断下一段（CoreML 崩、numpy 叉积崩、删除崩），耗了多轮仍不顺。

**根因**：问题不是某个具体 bug，是「Label Studio 自己不带分割模型、必须外挂 backend」这个架构本身脆——链路接点多，任一段不对齐整条断。在脆弱架构上逐个修接点是治标。

**堵死同类的规则**：
1. **同一个功能反复在不同接点崩，是架构信号不是 bug 信号**。该问的是「有没有把这条链路整个删掉的工具」，而不是「这个接点怎么修」。X-AnyLabeling 把 SAM 编进 GUI（单进程、无外挂链路），换过去后所有崩溃都变成可定位的具体 bug。
2. **换工具前先用一手来源核实候选**（官方仓库/文档），确认「内置 SAM + 本地 + 导出 YOLO」三个硬条件，再装。
3. **beta 工具 + numpy 2.x 在本机必踩兼容坑**：CoreML EP 跑不动 SAM（强制 CPU）、numpy 2.x 删了 2D `np.cross`（改标量公式）、删除回调空值崩。补丁都打在包源码里并备份 `.bak`，重装会覆盖需重打——记录在 `docs/annotation-tool-xanylabeling.md`。

## L4 标注前先问「能不能代码派生」，别让人手标两遍（2026-06-15）

**现象**：原 pilot 计划要求每个商品既标多边形（分割）又画矩形（检测），用户质疑「同一商品要标两遍吗」，戳中隐藏的双倍工作量。

**根因**：把「检测要框、分割要多边形」直接翻译成「手标两套」，没意识到多边形的外接矩形就是检测框，一行代码可派生。

**堵死同类的规则**：
1. **两种标注若存在数学派生关系（多边形→外接矩形），只标信息量大的那个，另一个用脚本派生**。`scripts/convert_xanylabeling.py` 一份多边形出 seg+det 两套。
2. 「系统承担复杂性」：区分给哪个模型、生成检测框是代码的事，不该压给标注的人。

## L5 用感知哈希去重要给 owner 复核，别自动删（2026-06-15）

**现象**：写了感知哈希去重，识别 270 张里 33 张「重复」准备删，用户要求谨慎。

**根因**：白底电商图天生相似（同模板），感知判定有把「同款不同规格/口味」误判成重复的风险，自动删会漏标真实 SKU。

**堵死同类的规则**：
1. **去重的代价不对称**：省 33 张标注 vs 漏一个 SKU 永远不被识别。决定全量标时，去重已无收益只剩风险——直接全量标。
2. 真要去重：只有**字节级 md5 相同**可闭眼删；感知相似的必须画并排对比图给数据 owner 复核，不自动删。工具 `scripts/dedup_images.py`（双哈希 AND + 彩色 MAE，避免同模板误判）。
