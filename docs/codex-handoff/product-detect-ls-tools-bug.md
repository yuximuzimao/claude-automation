# Label Studio 标注工具未渲染问题

**发起方**: Claude Code  
**时间**: 2026-06-12  
**优先级**: 高（阻塞用户标注工作）

## 问题描述

Label Studio 1.23.0 配置了 BrushLabels + RectangleLabels + KeyPointLabels 三种标注类型，但标注界面只渲染了 BrushLabels 的工具（brush-tool, eraser），RectangleLabels（矩形框）和 KeyPointLabels（SAM 提示点）的工具完全不出现在 DOM 中。

## 已验证事实

1. **配置正确**：DB 里 project 4 的 label_config 有 4139 字节，包含完整的 BrushLabels（name="mask"）+ RectangleLabels（name="bbox"）+ KeyPointLabels（name="prompt_point" smart="true"）
2. **工具完全不渲染**：通过 `document.querySelectorAll('button[title]')` 检查，只找到 `brush-tool, eraser, move-tool, pan, zoom-in, zoom-out`，没有任何 rectangle/bbox/keypoint 相关元素
3. **两种界面都一样**：分屏列表模式和全屏标注编辑器模式均只显示 brush 工具
4. **配置验证**：Label Studio 设置页面的 Preview 也只显示 brush 工具，说明配置本身未能触发 rectangle 工具渲染
5. **Label Studio 版本**：1.23.0（pip install 版）

## 当前配置结构

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <Header value="标注说明..."/>
  <BrushLabels name="mask" toName="image" showInline="true">
    <!-- 28 个 Label -->
  </BrushLabels>
  <RectangleLabels name="bbox" toName="image" showInline="true">
    <!-- 28 个 Label -->
  </RectangleLabels>
  <KeyPointLabels name="prompt_point" toName="image" smart="true" showInline="true">
    <Label value="object" background="#AAAAAA"/>
  </KeyPointLabels>
</View>
```

## 要求 Codex 调查的问题

1. **根因**：Label Studio 1.23.0 中 BrushLabels 是否存在"接管" canvas 导致其他工具不渲染的已知 bug？GitHub issues 里有没有相关报告？
2. **解决方案**：如何让同一个 Label Studio 项目同时显示 BrushLabels 和 RectangleLabels 两套工具？
3. **备选方案评估**：
   - 方案A：两个独立项目（一个专门标 mask，一个专门标 bbox）→ 如何确保标注对应同一批图？
   - 方案B：降级/升级 Label Studio 版本 → 哪个版本支持？
   - 方案C：修改配置结构（去掉 BrushLabels，改用其他方式做 SAM 辅助标注）

## 背景与目标

这是 KGOS Detect-vs-Seg Pilot 的标注环境（`product-detect/docs/detect-vs-seg-pilot-plan-v2.md`）。目标：
- 用 SAM ML Backend 辅助画 mask（BrushLabels）
- 同时人工画 bbox（RectangleLabels）
- 同一张图的 mask 数量必须 == bbox 数量（作为一致性校验）

最终目标是 FAIR comparison：同一批真实图，两套人工独立标注，分别训 yolov8n-seg 和 yolov8n，对比业务指标。

## 关键文件

- `product-detect/datasets/kgos_real_all/label_studio_seg_pilot_config.xml` — 当前完整配置
- Label Studio DB: `~/Library/Application Support/label-studio/label_studio.sqlite3`
- Label Studio Project ID: 4（KGOS Detect-vs-Seg Pilot）

