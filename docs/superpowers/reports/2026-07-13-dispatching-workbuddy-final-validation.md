# dispatching-workbuddy 最终验证记录

日期：2026-07-13

## 实机验证

- 本机 WorkBuddy CLI 使用 `--model hy3` 启动成功；流式初始化事件报告模型为 `hy3`。
- 初始化事件的工作目录是 `/private/tmp/codex-workbuddy/<run-id>/projection/workspace` 的物理路径，MCP 服务器为空，实际工具清单只包含文件读写工具的子集。
- 初次实测发现 CLI 仍会暴露 PowerShell、任务和微信类工具；已将观察到的非文件工具加入显式拒绝清单后复测，模型确认未拥有 Shell / Bash / PowerShell。
- 投影外 `hidden.txt` 的实际读取探针被权限层拒绝，探针内容未出现在输出中；投影外写入目标保持原值。
- 使用 `sandbox-exec` 拒绝当前用户 `HOME` 的候选配置会破坏已安装 WorkBuddy 的认证路径，因此没有将其伪装成可工作的操作系统隔离方案。
- 当前账户的派工器要求 `dataClassification: "non_sensitive"`，缺失或标记敏感即在投影前拒绝；选中文本和生成补丁均做疑似凭据扫描。该扫描是防御加层，不替代独立用户/虚拟机。
- 生产 CLI 已忽略 `WORKBUDDY_CLI_PATH` / `WORKBUDDY_TEST_MODE` 环境变量；测试只能通过进程内显式依赖注入使用假二进制。退出码为 0 但没有成功流式结果时，状态会记为失败。

## 自动化验证

执行：

```sh
node --test /Users/chat/.codex/skills/dispatching-workbuddy/tests/*.test.mjs
python3 /Users/chat/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/chat/.codex/skills/dispatching-workbuddy
```

结果：33/33 Node 测试通过；Skill 结构校验通过。

覆盖点包括：路径穿越、敏感文件名与疑似凭据内容、强制非敏感分类、符号链接、可执行模式、新文件白名单、源基线变化、运行时异常工具/MCP/模型/权限/CWD、环境变量 CLI 覆盖、导入绑定、零退出但无成功结果、投影外补丁、长队列和看门狗终止条件。

## 最终安全结论

| 场景 | 是否可用 | 边界 |
| --- | --- | --- |
| 普通、无敏感数据的受限代码任务 | 可以 | 最小投影 + 文件工具白名单 + Codex 审查/测试/合并 |
| 包含密钥、客户原始数据、生产或业务系统风险的任务 | 当前账户不可以 | 必须转到独立 macOS 用户或虚拟机，并在其中单独登录 WorkBuddy |
| 免费模型长时间排队 | 可以等待 | 中型 T+120、大型 T+180 分钟才标记 `slow_or_queued`；不自动终止、不自动重试 |

WorkBuddy 仍永远不直接提交、合并、推送或操作浏览器；只有 Codex 可把已验证补丁导入隔离集成分支并完成本地合并。
