#!/usr/bin/env python3
"""
新视频一键处理管道
用法：python3 add_video.py <视频文件路径> [--topic 主题名称]

步骤：
  1. 转录视频（whisper medium模型）
  2. 按动作段落切片
  3. 转为GIF
  4. 交互式标注每个切片（动作名/类型/组数/次数/要领）
  5. 写入 exercise_db.json
"""
import subprocess
import sys
import json
import re
import hashlib
import tempfile
from pathlib import Path

from config import PLUGIN_DIR, PLANS_DIR, SLICES_DIR, DB_PATH, WHISPER_MODEL, EXERCISE_TYPES
from utils import parse_segments, group_into_actions, sanitize


def transcribe(video_path: Path, output_dir: Path, topic: str) -> Path:
    plan_path = output_dir / f"plan_{video_path.stem}.md"
    suffix = hashlib.md5(str(video_path).encode()).hexdigest()[:8]

    print("🎙  提取音频...")
    with tempfile.NamedTemporaryFile(suffix=f'_{suffix}.wav', delete=False) as tmp:
        audio_path = Path(tmp.name)
    try:
        subprocess.run(
            ['ffmpeg', '-i', str(video_path), '-ar', '16000', '-ac', '1',
             '-c:a', 'pcm_s16le', str(audio_path), '-y', '-loglevel', 'error'],
            check=True
        )
        print("📝  转录中（medium模型，约 20-40 分钟）...")
        result = subprocess.run(
            ['whisper-cli', '-m', WHISPER_MODEL, '-l', 'zh', '-d', '600000', '-f', str(audio_path)],
            capture_output=True, text=True
        )
    finally:
        audio_path.unlink(missing_ok=True)

    plan_path.write_text(
        f"# 健身训练计划\n## 主题：{topic}\n\n## 转录文本\n{result.stdout}",
        encoding='utf-8'
    )
    print(f"✅  转录完成 → {plan_path.name}")
    return plan_path


def slice_and_gif(video_path: Path, plan_path: Path, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    transcription = plan_path.read_text(encoding='utf-8')
    segments = parse_segments(transcription)
    actions = group_into_actions(segments)
    print(f"✂️   识别到 {len(actions)} 个动作段落")

    from utils import time_to_seconds
    clips = []
    for i, action in enumerate(actions):
        label = action['texts'][0]
        name = sanitize(label)
        mp4_path = out_dir / f"{i+1:02d}_{name}.mp4"
        gif_path = out_dir / f"{i+1:02d}_{name}.gif"
        desc = ' / '.join(action['texts'][:3])

        start_sec = max(0, time_to_seconds(action['start']) - 0.5)
        r = subprocess.run(
            ['ffmpeg', '-i', str(video_path), '-ss', str(start_sec), '-to', action['end'],
             '-c', 'copy', str(mp4_path), '-y', '-loglevel', 'error'],
            capture_output=True
        )
        if r.returncode != 0 or not mp4_path.exists() or mp4_path.stat().st_size < 1000:
            print(f"  [{i+1}] ✗ 切片失败: {desc[:40]}")
            continue

        subprocess.run(
            ['ffmpeg', '-i', str(mp4_path), '-vf', 'fps=8,scale=480:-1:flags=lanczos',
             '-t', '12', str(gif_path), '-y', '-loglevel', 'error'],
            capture_output=True
        )
        ok = gif_path.exists() and gif_path.stat().st_size > 1000
        print(f"  [{i+1}] {'✅' if ok else '⚠️ 无GIF'} {desc[:50]}")
        if ok:
            clips.append({
                'index': i + 1,
                'mp4': mp4_path.name,
                'gif': gif_path.name,
                'desc': desc,
                'start': action['start'],
                'end': action['end'],
            })
    return clips


def annotate_clips(clips: list[dict], gif_dir_name: str) -> list[dict]:
    exercises = []
    print(f"\n{'='*60}")
    print("📋  为每个切片标注动作信息（直接回车跳过该切片）")
    print(f"{'='*60}\n")

    type_prompt = " / ".join(f"{i+1}.{t}" for i, t in enumerate(EXERCISE_TYPES))

    for clip in clips:
        print(f"[{clip['index']}] {clip['desc'][:60]}")
        print(f"    时间: {clip['start']} → {clip['end']}")

        name = input("    动作名称（回车跳过）: ").strip()
        if not name:
            print("    ↳ 已跳过\n")
            continue

        print(f"    类型: {type_prompt}")
        type_input = input("    选择类型编号（默认7.其他）: ").strip()
        try:
            ex_type = EXERCISE_TYPES[int(type_input) - 1]
        except (ValueError, IndexError):
            ex_type = "其他"

        sets = input("    组数（如：4 组）: ").strip() or "4 组"
        reps = input("    次数/时长（如：20 次/组）: ").strip() or "20 次/组"
        tips = input("    动作要领（可留空）: ").strip()

        exercises.append({
            "name": name,
            "type": ex_type,
            "sets": sets,
            "reps": reps,
            "tips": tips,
            "gif_dir": gif_dir_name,
            "gif_name": clip['gif'].replace('.gif', ''),
        })
        print(f"    ✅ 已记录: {name} [{ex_type}]\n")

    return exercises


def update_db(new_exercises: list[dict]):
    db = json.loads(DB_PATH.read_text(encoding='utf-8')) if DB_PATH.exists() else {"exercises": []}
    existing_names = {e['name'] for e in db['exercises']}
    added = 0
    for ex in new_exercises:
        if ex['name'] not in existing_names:
            db['exercises'].append(ex)
            existing_names.add(ex['name'])
            added += 1
        else:
            print(f"  ⚠️  动作「{ex['name']}」已存在，跳过")
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅  动作库已更新：新增 {added} 个动作，共 {len(db['exercises'])} 个")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 add_video.py <视频文件> [--topic 主题名称]")
        sys.exit(1)

    video_path = Path(sys.argv[1])
    if not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)

    if not Path(WHISPER_MODEL).exists():
        print(f"❌ Whisper 模型不存在: {WHISPER_MODEL}")
        print("   请先下载: https://huggingface.co/ggerganov/whisper.cpp")
        sys.exit(1)

    topic = "新视频"
    if '--topic' in sys.argv:
        idx = sys.argv.index('--topic')
        if idx + 1 < len(sys.argv):
            topic = sys.argv[idx + 1]

    # 生成不冲突的目录名
    existing = [d.name for d in SLICES_DIR.iterdir() if d.is_dir()] if SLICES_DIR.exists() else []
    vid_nums = [int(m.group(1)) for d in existing if (m := re.match(r'video(\d+)', d))]
    next_num = max(vid_nums, default=0) + 1
    gif_dir_name = f"video{next_num}_{sanitize(topic, 20)}"
    out_dir = SLICES_DIR / gif_dir_name

    print(f"\n🎬  处理视频: {video_path.name}")
    print(f"📁  输出目录: {gif_dir_name}\n")

    plan_path = transcribe(video_path, PLANS_DIR, topic)
    clips = slice_and_gif(video_path, plan_path, out_dir)

    if not clips:
        print("⚠️  没有有效切片，退出")
        sys.exit(0)

    new_exercises = annotate_clips(clips, gif_dir_name)
    if not new_exercises:
        print("没有标注任何动作，退出")
        sys.exit(0)

    update_db(new_exercises)
    print(f"\n🎉  完成！现在可以运行 python3 gen_plan.py 生成新计划")


if __name__ == '__main__':
    main()
