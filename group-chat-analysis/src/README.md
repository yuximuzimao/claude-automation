# 正式代码模块边界

本文件只定义正式代码职责，避免开发时把实验代码和现役实现混在一起。

## 当前入口

- `app/capture-once.swift`：正式单页 CLI；启动时校验并必要时放大聊天记录窗口，然后捕获一页并原子写 raw JSON。
- `app/capture-pages.swift`：当前最小连续多页 CLI；逐页执行“捕获并持久化 → 动态滚动 → 下一页”。
- `capture/QQHistoryCapture.swift`：QQ 聊天记录窗口识别、前台/群名校验、窗口自动放大、动态滚动、ScreenCaptureKit 捕获、Apple Vision OCR。
- `store/RawPageWriter.swift`：raw page 原子写入与拒绝覆盖。

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

ScreenCaptureKit 窗口捕获、系统滚轮事件和 Apple Vision OCR 已在当前 Mac/QQ 环境完成实测，因此 **capture 正式实现采用 Swift**。

normalize/store/inbox 是否继续使用 Swift，等数据契约定型后按最少复杂度决定；如果采用其它语言，必须通过明确文件/进程接口隔离，不把两套运行时互相嵌死。

## 已验证 capture v1

- 聊天记录独立窗口为主路径。
- 目标群通过 QQ window owner + 精确窗口标题校验。
- 窗口偏小时可在启动阶段拖动右下角自动恢复到约 `1562×978`；随后水平左移，使当前显示器右侧保留约 `726px` 空白。
- OCR bbox 使用 Vision 归一化坐标，不依赖窗口绝对尺寸。
- 滚轮锚点从当前页真实 OCR 正文块动态选择。
- 历史方向为负向 pixel wheel。
- 单次滚动距离为当前窗口高度约 61%。
- raw page 必须先成功持久化，之后才能滚到下一页。
- 进入抓取循环后不再自动激活 QQ；用户切走时应停止。
- 小窗口和自动放大后的大窗口均已完成真实连续 3 屏 capture。

下一阶段进入 `normalize/`。在消息重建和跨屏去重通过前，不直接扩展到首次全量历史抓取。
