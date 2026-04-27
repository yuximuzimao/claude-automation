---
name: douyin-workout
description: 抖音健身视频处理技能。扫描 Photos Library 批量转录、切片、生成GIF，自动识别动作类型，择优去重，生成5天训练计划HTML。触发词：处理健身视频、导入锻炼视频、生成训练计划、/douyin-workout。
skill_dir: /Users/chat/claude/douyin-workout
entry: bash /Users/chat/claude/douyin-workout/run.sh
---

# 健身视频处理技能

## 快速调用

```bash
bash /Users/chat/claude/douyin-workout/run.sh [命令]
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `import`（默认） | 扫描 Photos Library，处理所有新视频，生成训练计划 |
| `reset` | 清空处理记录，重新处理所有视频 |
| `plan` | 仅重新生成随机训练计划HTML |
| `plan --days 3` | 生成3天计划 |
| `plan --focus 腿部` | 强调腿部动作 |
| `plan --seed 42` | 固定种子，复现同一方案 |
| `status` | 查看动作库统计（动作数/类型分布） |
| `dry-run` | 预览待处理视频，不实际处理 |

## 工作流程

1. 扫描 `~/Pictures/Photos Library.photoslibrary/originals/` 所有视频
2. 哈希缓存跳过已处理，只处理新增
3. 每视频：提取音频 → whisper medium 转录（约20-40分钟/个）
4. 按动作段落切片 → 生成 GIF（480px，8fps）
5. 自动识别动作类型（腿部/腰腹/有氧等）、组数、次数
6. 重名动作择优：保留 GIF 文件更大的（内容更丰富）
7. 更新 `exercise_db.json` 动作库
8. 随机生成5天训练计划 HTML，浏览器打开

## 输出位置

- 训练计划 HTML：`/Users/chat/claude/douyin-workout/`
- 动作库：`/Users/chat/claude/douyin-workout/exercise_db.json`
- 切片/GIF：`/Users/chat/claude/douyin-workout/slices/`

## 文件结构

```
douyin-workout/
├── SKILL.md           ← 本文件（技能描述）
├── run.sh             ← 统一入口
├── batch_import.py    ← 批量导入主程序
├── gen_plan.py        ← 随机训练计划生成器
├── make_html.py       ← 固定计划HTML生成
├── add_video.py       ← 单个视频交互式处理
├── slice_video.py     ← 视频切片工具
├── config.py          ← 共享路径/常量配置
├── utils.py           ← 共享工具函数（含GIF缓存）
├── exercise_db.json   ← 动作库数据
└── slices/            ← 健身视频切片和GIF
```
