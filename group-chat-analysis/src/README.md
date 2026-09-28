# 正式代码模块边界

本文件只定义正式代码职责，避免开发时把实验代码和现役实现混在一起。

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

阶段 1 已验证 macOS 原生 ScreenCaptureKit、Apple Vision 和 Accessibility 能覆盖当前 capture 所需能力，因此正式 capture 实现默认以 Swift 为主。Normalize/store 是否继续使用 Swift，等其数据接口和 batch/state 定型后再决定。

如果后续采用 Swift capture + 其它语言的数据处理，必须通过明确文件/进程接口隔离，不把两套运行时互相嵌死。

## 正式入口门禁

当前门禁状态：

1. QQ“聊天记录”独立窗口的窗口级捕获：已验证；
2. 聊天正文动态定位：已验证；
3. capture 输出数据结构：已由 `schemas/capture-page.schema.json` 固化；
4. runtime batch/state 最小格式：待确定；
5. 首个端到端 dry-run 成功标准：待和 batch/state 一起最终确认。

因此目前仍不创建正式 `src` 入口；bbox 重建等实验继续留在工作区根 `_sandbox/`。等 4/5 完成后再把已验证实验迁入唯一现役实现。
