#!/usr/bin/env python3
"""
生成固定5天健身训练计划 HTML（从 exercise_db.json 读取动作数据）
用法：python3 make_html.py
"""
import json
import html
import sys
from pathlib import Path

from config import PLUGIN_DIR, PLANS_DIR
from utils import gif_to_b64

OUTPUT_HTML = PLANS_DIR / "健身训练完整计划.html"

# 5天训练计划（动作名需存在于 exercise_db.json）
WEEKLY_PLAN = [
    {
        "day": "周一",
        "theme": "腿部塑形",
        "color": "#4f8ef7",
        "exercises": ["侧卧抬腿画圈", "侧卧腿开合", "单腿臀桥"],
    },
    {
        "day": "周二",
        "theme": "腰腹核心",
        "color": "#f7774f",
        "exercises": ["肋间式呼吸", "半程平板支撑", "侧撑抬腿"],
    },
    {
        "day": "周三",
        "theme": "拉伸修复",
        "color": "#4fbf7f",
        "exercises": ["大腿后侧动态拉伸", "大腿前侧拉伸", "臀部拉伸", "颈部侧向拉长", "侧屈低头"],
    },
    {
        "day": "周四",
        "theme": "小腿专项",
        "color": "#c77ff7",
        "exercises": ["反复勾脚", "抬腿勾脚", "坐姿压脚趾"],
    },
    {
        "day": "周五",
        "theme": "全身燃脂",
        "color": "#f7c94f",
        "exercises": ["开合跳", "胯下击脚", "台阶上下", "波比跳"],
    },
]


def load_exercises() -> dict[str, dict]:
    db_path = PLUGIN_DIR / "exercise_db.json"
    if not db_path.exists():
        print(f"❌ 找不到动作库: {db_path}")
        sys.exit(1)
    data = json.loads(db_path.read_text(encoding='utf-8'))
    return {e['name']: e for e in data['exercises']}


def exercise_card_html(ex: dict) -> str:
    b64 = gif_to_b64(ex.get('gif_dir', ''), ex.get('gif_name', ''))
    img = (f'<img src="data:image/gif;base64,{b64}" alt="{html.escape(ex["name"])}">'
           if b64 else '<div class="no-gif">暂无动图</div>')
    return f'''
<div class="exercise-card">
  <div class="exercise-gif">{img}</div>
  <div class="exercise-info">
    <h3>{html.escape(ex["name"])}</h3>
    <table>
      <tr><td class="label">组数</td><td>{html.escape(ex.get("sets", ""))}</td></tr>
      <tr><td class="label">次数/时长</td><td>{html.escape(ex.get("reps", ""))}</td></tr>
      <tr><td class="label">动作要领</td><td>{html.escape(ex.get("tips", ""))}</td></tr>
    </table>
  </div>
</div>'''


def make_html():
    db = load_exercises()

    overview = '<div class="week-overview">\n'
    for day in WEEKLY_PLAN:
        tags = "".join(f'<span class="ex-tag">{html.escape(n)}</span>' for n in day["exercises"])
        overview += f'''
  <div class="day-card" style="border-top:4px solid {day["color"]}">
    <div class="day-header">
      <span class="day-label" style="color:{day["color"]}">{html.escape(day["day"])}</span>
      <span class="day-theme">{html.escape(day["theme"])}</span>
    </div>
    <div class="day-exercises">{tags}</div>
  </div>'''
    overview += '\n</div>\n'

    days_html = ""
    for day in WEEKLY_PLAN:
        cards = ""
        for name in day["exercises"]:
            ex = db.get(name)
            if ex is None:
                print(f"⚠️  动作「{name}」不在数据库中，跳过")
                continue
            cards += exercise_card_html(ex)
        days_html += f'''
<section id="{day["day"]}">
  <h2 style="border-color:{day["color"]};color:{day["color"]}">{html.escape(day["day"])} · {html.escape(day["theme"])}</h2>
  {cards}
</section>'''

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>5天健身训练计划</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #1d1d1f; padding: 20px; }}
  header {{ text-align: center; padding: 36px 0 20px; }}
  header h1 {{ font-size: 2.2rem; font-weight: 700; margin-bottom: 6px; }}
  header p {{ color: #888; font-size: 0.95rem; }}
  .week-overview {{ display: flex; gap: 12px; max-width: 1100px; margin: 0 auto 40px; flex-wrap: wrap; }}
  .day-card {{ flex: 1; min-width: 160px; background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .day-header {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px; }}
  .day-label {{ font-size: 1.1rem; font-weight: 700; }}
  .day-theme {{ font-size: 0.85rem; color: #666; }}
  .day-exercises {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .ex-tag {{ background: #f0f2f5; border-radius: 4px; padding: 2px 7px; font-size: 0.78rem; color: #444; }}
  section {{ max-width: 1100px; margin: 0 auto 48px; }}
  h2 {{ font-size: 1.4rem; border-left: 5px solid; padding-left: 14px; margin-bottom: 22px; margin-top: 8px; }}
  .exercise-card {{ display: flex; gap: 24px; background: #fff; border-radius: 14px; padding: 22px; margin-bottom: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); align-items: flex-start; }}
  .exercise-gif {{ flex-shrink: 0; width: 360px; }}
  .exercise-gif img {{ width: 100%; border-radius: 10px; display: block; }}
  .no-gif {{ width: 360px; height: 220px; background: #f0f0f0; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #aaa; font-size: 0.85rem; }}
  .exercise-info {{ flex: 1; }}
  .exercise-info h3 {{ font-size: 1.2rem; font-weight: 700; color: #1d1d1f; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 8px 10px; font-size: 0.95rem; vertical-align: top; line-height: 1.6; }}
  td.label {{ font-weight: 600; color: #666; white-space: nowrap; width: 90px; }}
  tr:nth-child(odd) td {{ background: #fafafa; }}
  @media (max-width: 700px) {{ .exercise-card {{ flex-direction: column; }} .exercise-gif, .exercise-gif img, .no-gif {{ width: 100%; }} .week-overview {{ flex-direction: column; }} }}
</style>
</head>
<body>
<header>
  <h1>5天健身训练计划</h1>
  <p>来源：抖音健身视频精选 &nbsp;·&nbsp; 适合：女生塑形减脂</p>
</header>
{overview}
{days_html}
</body>
</html>'''

    OUTPUT_HTML.write_text(html_content, encoding='utf-8')
    size_mb = OUTPUT_HTML.stat().st_size / 1024 / 1024
    print(f"HTML 文档已生成: {OUTPUT_HTML}  ({size_mb:.1f}MB)")


if __name__ == "__main__":
    make_html()
