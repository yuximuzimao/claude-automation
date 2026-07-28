# 商品匹配

用于核查鲸灵活动商品与快麦 ERP 商品对应关系，并在用户确认识图结果后完成未匹配 SKU 的单品/套件匹配。

## 标准流程

```bash
node cli.js check --shop <店铺> --brand <品牌>
# 完成全量识图后：
node cli.js check --shop <店铺> --reuse-active --skip-download
node cli.js preview-match
# 用户确认核对页后：
node cli.js match --shop <店铺>
node cli.js check --shop <店铺> --reuse-active --skip-download
```

最后一次 `check` 必须满足：

- 活动范围与匹配前已确认范围完全一致；
- 不同活动链接即使复用同一 `platformCode`，也必须按 `productCode + platformCode` 分别计数和核对；
- `recognitionDone` 等于 SKU 总数；
- `comparisonMatch` 等于 SKU 总数；
- `comparisonMismatch`、`comparisonPending`、`pendingVisualReview` 都为 `0`。

只要有一项不满足，就不能把本轮商品匹配判为完成。

识图后的匹配前 `check` 使用同一个脚本，由 AI 按当前阶段判断：

- 已匹配 SKU 必须全部自动比对一致；
- 未匹配 SKU 记为 `unmatchedAwaitingMatch`，此时属于正常待处理；
- AI 只向用户报告异常 SKU，不要求用户人工复核 ERP 明细。

## 开始前必读

| 文档 | 用途 |
|---|---|
| `CLAUDE.md` | 项目红线、命令和 Git 规则 |
| `SKILL.md` | 代码入口和运行时导航 |
| `docs/INDEX.md` | 完整业务流程与数据契约 |
| `docs/matching-stability.md` | ERP 状态机、故障优先级和恢复方法 |
| `docs/chatgpt-codexpro-operations.md` | ChatGPT 通过 CodexPro 操作时的图片桥接、时间边界和本地 Codex 交接 |
| `docs/preflight-brand.md` | 新品牌建档门禁 |

## 安全边界

- ERP 写操作必须先获得用户对识图/匹配方案的明确确认。
- 品牌只在首次 `check --brand <品牌>` 指定一次，随后写入本轮记录并自动继承；缺失或冲突立即停止。
- 同一个 ERP 标签页只能有一个商品匹配进程操作，禁止并行调试。
- `match` 任一 SKU 失败必须立即停止；先判断 ERP 当前中间状态，再决定续跑。
- 默认不提交 `data/` 运行时产物；只提交代码、规则和文档。

## 历史归档

按日期保存的实战证据位于 `docs/archive/`。归档用于追溯，不覆盖当前规则；运行时以
`CLAUDE.md`、`SKILL.md`、`docs/INDEX.md` 和 `docs/matching-stability.md` 为准。
