# Handoff

更新时间：2026-05-29 22:11
当前负责人：Claude Code
当前分支：data-model-restructure
当前焦点项目：product-mapping（商品匹配）

## 正在做
- 工作区处于脏状态，187 个文件变更未提交
- product-mapping 品牌数据重构（图片迁移 jpg→png，品牌目录整理）
- transfer 项目已独立出去

## 未提交改动说明
- aftersales-automation: SKILL.md + lib/ 逻辑改动 + data/ 运行时数据更新
- product-mapping: 大量图片删除（旧 jpg）+ 新增 png，CLAUDE.md/SKILL.md 同步
- product-detect: 训练脚本改动，新增 assets/ 和模型文件
- sku-calculator: CLAUDE.md/SKILL.md/docs 同步
- lkwj: 待采集数据 + annotations + review.html
- 根目录新增 AGENTS.md

## 已验证
- transfer 项目独立：cli.js collect/pack 可用
- zip 编码修复：Python zipfile UTF-8 flag 已确认
- product-mapping SKILL.md 已清除 transfer 残留引用

## 未验证 / 风险
- 187 个未提交变更需要分类整理后分批 commit
- data/ 下运行时文件不应提交

## 下一步
- 分批整理并 commit 当前变更
- 继续 product-mapping 品牌数据整理
- 拉通 Codex 做一次 stop-review gate 试运行
