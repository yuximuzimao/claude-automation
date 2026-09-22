# 正式代码模块边界

当前尚未开始正式实现。本文件只冻结未来代码职责，避免开发时随手堆在一个脚本里。

## 预期模块

```text
src/
  app/          # 唯一正式入口/编排层
  capture/      # QQ窗口定位、滚动、捕获、Vision OCR
  normalize/    # bbox消息重建、排序、跨屏去重
  store/        # messages/state/batch 持久化
  inbox/        # 生成 runtime/inbox/current.md
```

目录在真正有代码时再创建，不用空目录或占位文件污染仓库。

## 依赖方向

`app → capture → normalize → store → inbox`

更准确地说，app 负责调用各模块；底层模块之间通过明确数据结构传递，不允许：

- capture 直接调用 GPT；
- normalize 操作 QQ；
- store 判断消息价值；
- inbox 修改 canonical messages；
- 任一模块直接写魔兽或其它项目。

## 语言边界

当前不在架构阶段锁死语言。

已知 Apple Vision / macOS 窗口捕获的原生能力使 Swift 成为 capture 的强候选；最终选择要等“QQ全屏窗口级捕获实验”完成后再定。

如果后续采用 Swift capture + 其它语言的数据处理，也必须通过明确文件/进程接口隔离，不把两套运行时互相嵌死。

## 正式入口门禁

创建现役入口前必须先确定：

1. 全屏下窗口级捕获是否稳定；
2. 聊天区动态定位方式；
3. capture 输出数据结构；
4. runtime batch/state 最小格式；
5. 首个端到端 dry-run 成功标准。

在此之前，实验代码只能留在工作区根 `_sandbox/`，不能假装是正式 src。
