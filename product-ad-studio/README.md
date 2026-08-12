# 商品宣传图工作台

本地、可迁移的 GPT 商品宣传图工作流。它不依赖固定模板，也不把关键知识只留在某个聊天账号中。

## 工作方式

1. 用户向 GPT 提供 Demo、最新产品图、参考图和简短要求。
2. GPT 读取本地品牌资料与历史素材目录，先输出简洁的人话对齐说明，再生成结构化设计意图。
3. 用户确认方向后仍保持讨论模式；只有当前消息明确写出“现在生成”或“现在修改”时，GPT 才调用一次内置生图工具，完成后立即恢复讨论模式。
4. 禁止切换到本机脚本、Images API 或其他 CLI/API 备用生图路径；内置通道不可用时只报告不可用。
5. 所有值得长期复用的素材、描述、规则、草稿、修改记录和成品回写本项目。
6. 换电脑或 GPT 账号时，复制整个目录即可恢复项目上下文。

## 默认值

- 未指定尺寸：1080 × 1920，9:16 竖版。
- 常用字体：阿里巴巴普惠体；最终字体按实际设计效果决定。
- Demo：默认使用截图理解人眼可见结构，使用你提供的可复制文字作为内容真值；共享或结构混乱的 Excel 仅作可选归档和辅助核对。
- 图片修改：每轮明确“改什么”和“什么保持不变”。
- 对话默认只讨论；“可以”“继续”“产品再大一点”等确认或反馈不构成执行授权。

## 安装

```bash
cd product-ad-studio
python3 -m pip install -r requirements.txt
python3 cli.py --help
```

## 常用命令

导入并去重素材：

```bash
python3 cli.py import-assets \
  --brand yaohei \
  --source /path/to/product.png \
  --asset-id yaohei-product-example \
  --role product_source \
  --description '产品正面透明素材' \
  --tags '产品,单品,透明底'
```

可选：辅助解析下载后的 Excel Demo。默认仍以截图理解结构、以可复制文字作为内容真值：

```bash
python3 cli.py parse-demo \
  --source /path/to/demo.xlsx \
  --output jobs/<job-id>/brief/demo-extracted.json
```

创建任务：

```bash
python3 cli.py new-job --brand yaohei --name '活动名称'
```

校验素材目录：

```bash
python3 cli.py verify --brand yaohei
```

## 素材去重

- SHA-256 完全相同：只保留一个文件，重复来源写入同一资产的 `source_aliases`。
- dHash 相近：只提示疑似重复，不自动删除，避免误删不同抠图、透明边缘或版本。
- 每张图片使用稳定的 `asset_id`、描述、标签和保护规则，不依赖聊天记忆或原始微信文件名。

## 当前品牌

`data/brands/yaohei/` 已归档钥黑首批五张产品 PNG、一张 Logo、四张 Demo 截图、四张其他品牌参考图和四张设计师成品，并保存 2026-07 黑金新品案例的设计师反馈与规则。

## 对话附件说明

ChatGPT 对话附件不会自动成为 CodexPro 本地文件。需要长期保留的图片必须先放入本地导入目录，再执行 `import-assets`；本案例的产品图、Logo、Demo 截图、参考图和设计师成品均已完成本地二进制归档。
