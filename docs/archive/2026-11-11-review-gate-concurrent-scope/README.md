# Review Gate 无关项目并发修改修复归档

日期：2026-11-11。范围：工作区共享 Review Gate 的并发范围判定与收尾。此处只保存已完成阶段和验证证据，不作为操作规则；现役唯一入口是 [Review Gate README](../../review-gate/README.md)。

## 原始问题与根因

QQ 农场首次无人监管运行的 `deliver` 因群聊项目两份文档发生并发修改而提前阻断。原始材料位于工作区 `_sandbox/farm-first-run-l54tq_yi/`，实际存在 request、签名 Work、claim 和仅含 `blocked` 的 prepared；未生成 Candidate、完整 Review 或 delivered。request / Work / claim 均登记 43 个文件，claim.runtime=true；Work V3 的完整性校验成功，dirty 清单有 64 项。

原调用链 `deliver → create_candidate → _current → _inventory` 在独立分类之前比较全仓 dirty 指纹；任何已登记范围外的变化一律拒绝。README 同时规定了这种拒绝行为，没有提供核实、记录无关并发的机制。因此根因同时涉及规则设计与实现能力，不代表工具发现了群聊文件与农场存在依赖。

## 本阶段完成内容

- 增加逐文件 `claim.outside_scope` 理由和依赖核实证据；其他项目目录只限制可声明边界，不自动证明无关。候选、必要依赖、当前项目、根规则、共享区域及策略不能借声明排除。
- 主体 Candidate/Review 与范围外核查分别绑定。分类器读取排除路径的最新 HEAD、索引和工作区内容；无关修改可继续，新增跨项目调用、共享资源关系或未知依赖仍阻断。
- 最终观测指纹必须匹配分类器实际核查的版本，避免最后扫描已看到新内容却仍使用旧的无关性结论。
- 根规则、工具、全局/项目策略及必要上下文继续绑定；HEAD 只在后代关系成立、树差异仅属已声明无关文件且最新范围核查通过时可前进。新增、删除、重命名、索引变化均保留检测。
- Work 格式升级为 V4，Candidate 为 V3。旧 Work 不改写、不自动迁移或重签；未来如需重新审查，应明确登记新的审查节点，不能冒充原任务开始。

完整现役语义、错误处理及使用方法只维护在现役 README，本档案不维护第二套制度。全局 `policy.json` 的风险触发规则未降低或关闭。

## 验证与独立审查

最终执行：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/review-gate -p 'test_*.py' -v`。

- **89/89 测试通过**，耗时 206.138 秒；新增 24 项并发范围测试。覆盖 Work 后及捕获期间的无关变化、Review 期间修改、候选未声明变化、共享/跨项目依赖、根规则/策略、混合变化、索引、HEAD、新增删除重命名、后续新增依赖及最终观测竞态。
- 独立审查使用本轮修改前保存的固定调用器，通过既有只读隔离 CLI；调用器 SHA-256 为 `99c4d9ac1de9046716c25f5abd96aa07f7634040f2e01066a0ab40b2d47289c6`。
- 第一轮 Important：同一路径后续新增依赖可能沿用旧声明。修复为读取最新内容并单独绑定范围核查。
- 第二轮 Important：最终观测可能已读到新版本，却沿用先前核查材料。修复为逐文件对照最终观测与核查材料指纹。
- 两项 finding 均已修复并增加回归；第三轮返回 `{"findings": []}`。第三轮以第二轮审查源码为差异基线，不是重置业务 Work。
- NEAT 收尾时重新核对下表三个文件与最终送审指纹一致；仅新增本历史记录与归档索引，未再次修改已验证实现或现役规则，因此未重复运行相同测试或重新启动业务 Review。

### 已验证文件 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `docs/review-gate/review_gate.py` | `c4437244e8c07acc17ce7092599308383ad9791c89f401cda391b6679b088c83` |
| `docs/review-gate/test_delivery.py` | `70029ffe32ceaf1ba27c4c2c6ade832ea986fc6248b80375e564c3cc611033f5` |
| `docs/review-gate/README.md` | `bdb2299a8f6cf066f3d301e45d83930dfbb0139a636e09cb61d059cede6d6c04` |

### 本地原始证据

以下原始材料保留在工作区 `_sandbox/review-gate-scope-fix-ads4o54v/`，不进入 Git；哈希用于核对，不能代替原始材料。包含请求、源码正文的审查材料及密钥没有复制入本档案。

| 证据文件 | SHA-256 |
| --- | --- |
| `final-tests-r3.txt` | `dafdf328889dfebb0cb31b28da2ddcd86fb85cc018b6c5b727f60b6b259e2cc5` |
| `independent-review-r3-result.json` | `0c54b7e283b24ef7991b013aeebef8a4d81bb93b6f4be6115a601c74ba708123` |
| `independent-review-r3-metadata.json` | `b050a96adda49aa6563ac58e60eeb0b32918f083eb8421e705419201af2dd034` |
| `independent-review-r3-material.json` | `4e8f17c8f99d0aa9e9835f8ba2e959bbefb079f60edcfed691a67c53d7ce5997` |

原农场 request/work/claim/prepared 的哈希在修复结束和 NEAT 收尾时均核对未变，摘要位于同一本地目录的 `original-evidence-summary.json`。

## NEAT 结构审查

- 全文核对本能力的现役 README、工作区根规则、Git 操作规则与相关全局约束；枚举共享 docs 历史目录，回溯 Review Gate 的两份 2026-11-06 历史档案。其他项目的未提交内容不属于本次归档范围。
- 根 AGENTS/CLAUDE 只保留触发边界与现役入口，未堆叠本次历史叙事；现役 README 负责单一审查流程，代码、策略和两个测试文件均有导航。
- 归档索引链接到本记录；从根规则可直接进入现役 README，再找到实现、策略和测试，不依赖本次聊天或历史档案恢复操作方式。
- Review Gate 是工作区共享能力，不新建独立业务项目骨架、并行 Todo、CURRENT 或跨 Agent 交接材料；没有新增个人记忆中的重复权威。
- 检查文档链接、Git 忽略边界与精确提交范围。提交仅包含本次三个修复文件、归档索引和本记录。

## 完成边界

“测试通过”“独立代码审查通过”与“业务 Delivery / 用户特定授权”互不替代。本轮没有生成农场 delivered，没有重开或重置农场 Work，也未扩展两次农场任务的特定授权。

未修改农场、群聊、售后业务逻辑或定时任务，未操作真实业务系统。原业务记录保持 blocked。工具没有完整静态调用图，也不提供原子文件系统冻结；依赖证据仍需人工/Agent 核实及独立分类，最终读取到实际运行之间仍须避免相关变化。

本次“按 neat 归档”授权用于提交本阶段代码与文档；不包含推送，其他会话的未提交修改继续保留。
