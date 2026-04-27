#!/usr/bin/env python3
"""
随机生成5天健身训练计划 HTML

用法：
  python3 gen_plan.py                    # 标准5天计划（随机抽取）
  python3 gen_plan.py --days 3           # 3天计划
  python3 gen_plan.py --focus 腿部 腰腹  # 强调某些类型（多分配动作）
  python3 gen_plan.py --seed 42          # 固定随机种子（可复现）
"""
import json
import random
import html
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import PLANS_DIR, DB_PATH
from utils import gif_to_b64

# 每天主题：(中文名, 允许的类型, 颜色, 动作数量范围)
DAY_THEMES = [
    ("腿部塑形",  ["腿部", "小腿"],        "#4f8ef7", (3, 4)),
    ("腰腹核心",  ["腰腹"],                 "#f7774f", (2, 3)),
    ("拉伸修复",  ["拉伸", "体态", "小腿"], "#4fbf7f", (3, 5)),
    ("全身燃脂",  ["有氧"],                 "#f7c94f", (3, 4)),
    ("综合强化",  ["腿部", "腰腹", "体态"], "#c77ff7", (3, 4)),
]

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_db() -> list[dict]:
    if not DB_PATH.exists():
        print(f"❌ 找不到动作库: {DB_PATH}")
        sys.exit(1)
    return json.loads(DB_PATH.read_text(encoding='utf-8'))['exercises']


def build_plan(exercises: list[dict], num_days: int, focus: list[str], rng: random.Random) -> list[dict]:
    """按天主题随机分配动作，保证每个动作最多出现一次。
    候选按 day_allowed 中的类型顺序排列，保证高优先级类型优先被选中。
    """
    by_type: dict[str, list[dict]] = {}
    for ex in exercises:
        by_type.setdefault(ex.get('type', '其他'), []).append(ex)
    for lst in by_type.values():
        rng.shuffle(lst)

    used_names: set[str] = set()
    plan = []

    for i, (theme_name, allowed_types, color, (min_ex, max_ex)) in enumerate(DAY_THEMES[:num_days]):
        day_allowed = list(allowed_types)
        for f in focus:
            if f not in day_allowed:
                day_allowed.append(f)

        # 按 day_allowed 顺序收集，保证优先级
        candidates = [
            ex for t in day_allowed
            for ex in by_type.get(t, [])
            if ex['name'] not in used_names
        ]

        target = min(rng.randint(min_ex, max_ex), len(candidates))
        selected = candidates[:target]
        for ex in selected:
            used_names.add(ex['name'])

        plan.append({
            "day": DAY_NAMES[i],
            "theme": theme_name,
            "color": color,
            "exercises": selected,
        })

    return plan


def exercise_card_html(ex: dict) -> str:
    b64 = gif_to_b64(ex.get('gif_dir', ''), ex.get('gif_name', ''))
    img = (f'<img src="data:image/gif;base64,{b64}" alt="{html.escape(ex["name"])}">'
           if b64 else '<div class="no-gif">暂无动图</div>')
    return f'''
<div class="exercise-card">
  <div class="exercise-gif">{img}</div>
  <div class="exercise-info">
    <h3>{html.escape(ex["name"])}</h3>
    <span class="type-tag">{html.escape(ex.get("type", ""))}</span>
    <table>
      <tr><td class="label">组数</td><td>{html.escape(ex.get("sets", ""))}</td></tr>
      <tr><td class="label">次数/时长</td><td>{html.escape(ex.get("reps", ""))}</td></tr>
      <tr><td class="label">动作要领</td><td>{html.escape(ex.get("tips", ""))}</td></tr>
    </table>
  </div>
</div>'''


def generate_html(plan: list[dict], seed: Optional[int]) -> str:
    overview = '<div class="week-overview">\n'
    for day in plan:
        tags = "".join(f'<span class="ex-tag">{html.escape(e["name"])}</span>' for e in day["exercises"])
        overview += f'''
  <div class="day-card" style="border-top:4px solid {day["color"]}">
    <div class="day-header">
      <span class="day-label" style="color:{day["color"]}">{html.escape(day["day"])}</span>
      <span class="day-theme">{html.escape(day["theme"])}</span>
    </div>
    <div class="day-exercises">{tags}</div>
  </div>'''
    overview += '\n</div>\n'

    days_html = "".join(f'''
<section id="{day["day"]}">
  <h2 style="border-color:{day["color"]};color:{day["color"]}">{html.escape(day["day"])} · {html.escape(day["theme"])}</h2>
  {"".join(exercise_card_html(ex) for ex in day["exercises"])}
</section>''' for day in plan)

    seed_note = f"随机种子 {seed} &nbsp;·&nbsp; " if seed is not None else ""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{len(plan)}天健身训练计划</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #1d1d1f; padding: 20px; }}
  header {{ text-align: center; padding: 36px 0 20px; }}
  header h1 {{ font-size: 2.2rem; font-weight: 700; margin-bottom: 6px; }}
  header p {{ color: #888; font-size: 0.9rem; }}
  .week-overview {{ display: flex; gap: 12px; max-width: 1100px; margin: 0 auto 40px; flex-wrap: wrap; }}
  .day-card {{ flex: 1; min-width: 150px; background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .day-header {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px; }}
  .day-label {{ font-size: 1.1rem; font-weight: 700; }}
  .day-theme {{ font-size: 0.82rem; color: #666; }}
  .day-exercises {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .ex-tag {{ background: #f0f2f5; border-radius: 4px; padding: 2px 7px; font-size: 0.75rem; color: #444; }}
  section {{ max-width: 1100px; margin: 0 auto 48px; }}
  h2 {{ font-size: 1.4rem; border-left: 5px solid; padding-left: 14px; margin-bottom: 22px; margin-top: 8px; }}
  .exercise-card {{ display: flex; gap: 24px; background: #fff; border-radius: 14px; padding: 22px; margin-bottom: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); align-items: flex-start; }}
  .exercise-gif {{ flex-shrink: 0; width: 380px; }}
  .exercise-gif img {{ width: 100%; border-radius: 10px; display: block; }}
  .no-gif {{ width: 380px; height: 230px; background: #f0f0f0; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #aaa; font-size: 0.85rem; }}
  .exercise-info {{ flex: 1; }}
  .exercise-info h3 {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 4px; }}
  .type-tag {{ display: inline-block; background: #e8f0fe; color: #1a73e8; border-radius: 4px; padding: 1px 8px; font-size: 0.78rem; margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  td {{ padding: 8px 10px; font-size: 0.95rem; vertical-align: top; line-height: 1.6; }}
  td.label {{ font-weight: 600; color: #666; white-space: nowrap; width: 90px; }}
  tr:nth-child(odd) td {{ background: #fafafa; }}
  @media (max-width: 700px) {{ .exercise-card {{ flex-direction: column; }} .exercise-gif, .exercise-gif img, .no-gif {{ width: 100%; }} .week-overview {{ flex-direction: column; }} }}
</style>
</head>
<body>
<header>
  <h1>{len(plan)}天健身训练计划</h1>
  <p>{seed_note}生成时间: {date_str} &nbsp;·&nbsp; 适合：女生塑形减脂</p>
</header>
{overview}
{days_html}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='随机生成健身训练计划')
    parser.add_argument('--days', type=int, default=5, help='训练天数 (默认5)')
    parser.add_argument('--focus', nargs='+', help='重点训练类型 (如: 腿部 腰腹)')
    parser.add_argument('--seed', type=int, default=None, help='随机种子（固定可复现）')
    parser.add_argument('--output', type=str, default=None, help='输出文件名')
    args = parser.parse_args()

    if args.days > 7:
        print("❌ 最多支持7天")
        sys.exit(1)

    exercises = load_db()
    print(f"📚  动作库：{len(exercises)} 个动作")

    seed = args.seed if args.seed is not None else random.randint(0, 99999)
    rng = random.Random(seed)
    plan = build_plan(exercises, args.days, args.focus or [], rng)

    print(f"🎲  随机种子: {seed}")
    total = 0
    for day in plan:
        names = ", ".join(e["name"] for e in day["exercises"])
        print(f"   {day['day']} {day['theme']}: {names}")
        total += len(day["exercises"])

    html_content = generate_html(plan, args.seed)

    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = PLANS_DIR / f"训练计划_{ts}_seed{seed}.html"

    out_path.write_text(html_content, encoding='utf-8')
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n✅  已生成: {out_path}  ({size_mb:.1f}MB)")
    print(f"   共 {args.days} 天 {total} 个动作")

    import subprocess
    subprocess.run(['open', str(out_path)])


if __name__ == '__main__':
    main()
