# 商品宣传图工作台

本地、可迁移的 GPT 商品宣传图工作流。它不依赖固定模板，也不把关键知识只留在某个聊天账号中。

## 工作方式

1. 用户向 GPT 提供 Demo、最新产品图、参考图和简短要求。
2. GPT 读取本地品牌资料与历史素材目录，先输出简洁的人话对齐说明，再生成结构化设计意图。
3. 用户确认方向后，GPT 直接生成/编辑图片，或由能读取本工作区的执行端处理。
4. 所有值得长期复用的素材、描述、规则、草稿、修改记录和成品回写本项目。
5. 换电脑或 GPT 账号时，复制整个目录即可恢复项目上下文。

## 默认值

- 未指定尺寸：1080 × 1920，9:16 竖版。
- 常用字体：阿里巴巴普惠体；最终字体按实际设计效果决定。
- Demo：Excel 文案为真值，单元格位置主要表示信息层级和大致关系。
- 图片修改：每轮明确“改什么”和“什么保持不变”。

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

解析 Excel Demo：

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

`data/brands/yaohei/` 已归档钥黑首批五张产品 PNG 和一张 Logo，并保存 2026-07 黑金新品案例的设计师反馈与规则。

## 对话附件说明

ChatGPT 对话附件不会自动成为 CodexPro 本地文件。对话里看过但本地没有原文件的参考图、Demo 截图和成品图，目前只保存了结构化案例描述。长期二进制归档时，把原图放到本地后执行 `import-assets`。
