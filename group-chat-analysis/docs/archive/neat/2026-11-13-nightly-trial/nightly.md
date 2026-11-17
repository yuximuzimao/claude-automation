> 历史材料 · 原夜间执行规则。2026-11-13 的预约已跳过并删除，本文件仅保留当时的方案。

# 一次性夜间处理 owner

当前仅实现2026-11-13（Asia/Shanghai）01:00—05:00这一轮，不是常驻调度。调度由Codex App一次性任务触发；业务唯一入口为 `python3 -m src.app.run_nightly --job runtime/nightly/night-20261113-20261020-22/job.json`。完整本轮指令见 `../nightly-20261113.md`。可预先预约一次性条件检查；实际无人监管业务必须在完整实际运行版本的Review Gate为delivered且代码仍匹配后才执行。无delivered仅报告跳过，不调用业务入口。

## 执行与截止

- 固定范围：`wow-infinite-time`的2026-10-20、21、22；前一天必须已analyzed，逐日执行，不能跳积压。未到01:00或达到05:00，CLI拒绝开始业务。`--validate-only`只检查配置和已有依赖，不采集、不调用模型。
- 一个supervisor用本轮独占文件锁防止同job双开；这不是跨项目桌面mutex。农场两份已核验排程处于窗口外，配置指纹变化就拒绝采集；启动及采集期间每秒检测已知实际桌面动作脚本，发现外部操作进程则杀停自身子进程组，不抢占。QQ进程存在本身不会被视为冲突。不得修改农场任务。
- `runtime_deadline.py`同时绑定绝对UTC截止与monotonic剩余时长，时钟回拨不能延长任务。capture、模型、应用与发布子进程独立进程组，截止或阶段超时立即SIGKILL整组。夜跑不使用`--background`，防止子采集脱离受控进程组。capture每页和Swift调用前也检查deadline；发布指针与阅读批次切换前再次检查。
- 截止可能留下`pending scroll`，必须保留，下次按capture/storage SOP恢复。没有“超时清pending”，没有未知失败自动重试；只有正常返回的页数预算incomplete且pending=null并确实前进，才允许同批下一分片。
- 每个模型调用最多900秒，受05:00剩余时间进一步压缩。模型无工具、只读sandbox、无Hook/记忆/插件/规则或网页访问，只接收冻结文本并输出JSON。沿用本机既有认证，不读取或打印凭据，不创建API Key。会使用现有Codex账户共享模型额度。
- 完整日包按行分块传入模型，覆盖范围、ID、原文quote与行号由代码复核。词面相似度只召回旧知识上下文；去向与新旧关系仍由模型完整语义判断。所有保留候选经过独立模型终审，有finding就停止于stage，不能勉强签收据。
- 应用前至少预留120秒；delta先构造和校验，再做原字节备份、journal和逐文件原子写。每次写前检查截止。未到期异常可回滚；到期不继续业务写，保留applying journal，后续必须先恢复并明确停止。只有真实完成语义与结构验证，才签review receipt并调用正式run_analysis。

## 阅读批次

每个日release完整发布后保留，但“本批新增”不会随单日切换。三天全部发布且lineage/hash验证通过，才生成一个 `reading-20261020-20261022` 阅读批次。新增QA来自每个release最终投影相对真实prepare-work基线的ID差集；重复支持或同ID修改不混入。系统knowledge/discard/archive/defer不决定是否属于新增。

任一天失败、截止、模型未通过或只完成stage，保留前一阅读批current；已完成日包不会被伪称为完整三日。未看旧批保留历史可回看。“本批已看完”独立于QA人工裁决和已阅，不覆盖用户标签。展示继承冻结Silver的topics/scope和原QA置信度/时效/依据，缺身份不从题目猜造。

## 记录与停止

- `runtime/nightly/night-20261113-20261020-22/status.json`：当前阶段、每日报告、失败与截止原因。
- 每日`*-capture.log`、`*-prepare.log`、`*-publish.log`，及day子目录下完整模型输入、schema、输出、call耗时和hash。
- 每日日报告记录pages/messages、capture_seconds、semantic_seconds、publish_seconds、release ID；这些是supervisor实际阶段墙钟时间，不是纯滚轮时间。
- 10/19旧基线只能从raw时间间隔估算：281页/1704消息，first-last约16.77分钟，<60秒间隔合计约11.95分钟，中位2.5秒，长间隔2次。包含准备/人工复核，不当同条件提速证明。
- 状态失败或截止后不再启动新阶段、不切阅读批current、不自行登录/改变QQ安全提示。保留全部源数据、日志和恢复点，次日如实报告哪些日完成、哪一步停止。
