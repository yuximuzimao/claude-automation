#!/usr/bin/env python3
"""
批量导入 Photos Library 中的全部视频
自动转录 → 切片 → GIF → 自动标注 → 更新动作库 → 生成训练计划

用法：python3 batch_import.py [--dry-run] [--regen-plan]
"""
import subprocess
import sys
import json
import re
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import PLUGIN_DIR, PLANS_DIR, SLICES_DIR, DB_PATH, WHISPER_MODEL
from utils import parse_segments, group_into_actions, sanitize, time_to_seconds

PHOTOS_ORIGINALS = Path("/Users/chat/Pictures/Photos Library.photoslibrary/originals")

# 关键词 → 动作类型映射
TYPE_KEYWORDS = {
    "腿部": ["腿", "臀", "大腿", "深蹲", "跪", "臀桥", "侧卧"],
    "小腿": ["小腿", "勾脚", "脚踝", "脚尖", "脚背"],
    "腰腹": ["腰", "腹", "平板", "核心", "侧撑", "卷腹"],
    "拉伸": ["拉伸", "拉长", "拉筋", "柔韧", "拉开"],
    "体态": ["颈", "肩", "体态", "脊椎", "天鹅颈", "驼背"],
    "有氧": ["跳", "波比", "燃脂", "有氧", "开合", "台阶", "击脚"],
}

# 最小切片时长（秒）和最大时长（过长则取中间段）
MIN_CLIP_SEC = 3
MAX_CLIP_SEC = 90


def find_videos() -> list[Path]:
    if not PHOTOS_ORIGINALS.exists():
        print(f"❌ 找不到 Photos Library: {PHOTOS_ORIGINALS}")
        sys.exit(1)
    videos = list(PHOTOS_ORIGINALS.rglob("*.mp4")) + list(PHOTOS_ORIGINALS.rglob("*.mov"))
    videos.sort(key=lambda p: p.stat().st_size, reverse=True)  # 大文件优先（通常内容更丰富）
    return videos


def video_hash(video_path: Path) -> str:
    """用文件大小+修改时间作为轻量 hash，避免读整个视频文件"""
    stat = video_path.stat()
    return hashlib.md5(f"{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()[:12]


def load_processed_hashes() -> set[str]:
    cache_path = PLUGIN_DIR / ".processed_hashes.json"
    if cache_path.exists():
        return set(json.loads(cache_path.read_text()))
    return set()


def save_processed_hashes(hashes: set[str]):
    cache_path = PLUGIN_DIR / ".processed_hashes.json"
    cache_path.write_text(json.dumps(list(hashes)), encoding='utf-8')


def load_db() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding='utf-8'))
    return {"exercises": []}


def save_db(db: dict):
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')


def transcribe(video_path: Path, topic: str) -> Optional[str]:
    """转录视频，返回转录文本"""
    plan_path = PLANS_DIR / f"plan_{video_path.stem}.md"
    if plan_path.exists():
        print(f"    📋 复用已有转录: {plan_path.name}")
        return plan_path.read_text(encoding='utf-8')

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_path = Path(tmp.name)
    try:
        r = subprocess.run(
            ['ffmpeg', '-i', str(video_path), '-ar', '16000', '-ac', '1',
             '-c:a', 'pcm_s16le', str(audio_path), '-y', '-loglevel', 'error'],
            capture_output=True
        )
        if r.returncode != 0:
            print(f"    ⚠️  音频提取失败，跳过")
            return None

        result = subprocess.run(
            ['whisper-cli', '-m', WHISPER_MODEL, '-l', 'zh', '-d', '600000', '-f', str(audio_path)],
            capture_output=True, text=True, timeout=3600
        )
    finally:
        audio_path.unlink(missing_ok=True)

    transcription = result.stdout
    if not transcription.strip():
        print(f"    ⚠️  转录为空，跳过")
        return None

    plan_path.write_text(
        f"# 健身训练计划\n## 主题：{topic}\n\n## 转录文本\n{transcription}",
        encoding='utf-8'
    )
    return plan_path.read_text(encoding='utf-8')


def guess_type(texts: list[str]) -> str:
    """从文本猜测动作类型"""
    combined = " ".join(texts)
    for ex_type, keywords in TYPE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return ex_type
    return "其他"


def extract_sets_reps(texts: list[str]) -> tuple[str, str]:
    """从转录文本提取组数和次数/时长"""
    combined = " ".join(texts)

    sets, reps = "4 组", "20 次/组"

    # 提取组数
    m = re.search(r'(\d+)\s*组', combined)
    if m:
        sets = f"{m.group(1)} 组"

    # 提取次数或时长
    m_times = re.search(r'(\d+)\s*(次|个|下)', combined)
    m_sec = re.search(r'(\d+)\s*秒', combined)
    m_min = re.search(r'(\d+)\s*分钟', combined)

    if m_min:
        reps = f"{m_min.group(1)} 分钟"
    elif m_sec:
        reps = f"{m_sec.group(1)} 秒/组"
    elif m_times:
        reps = f"{m_times.group(1)} {m_times.group(2)}/组"

    return sets, reps


def clean_name(text: str) -> str:
    """从转录文本提取简洁的动作名（去掉口语化词语）"""
    # 去掉语气词和口语
    text = re.sub(r'^(好|来|接下来|然后|首先|现在|第[一二三四五六七八九十\d]+[个动作是])\s*', '', text)
    text = re.sub(r'(啊|哦|嗯|呢|吧|了|的|就是|就|这个|那个)\s*', '', text)
    text = text.strip()
    # 截取前10个字
    return text[:15] if text else ""


def slice_and_gif(video_path: Path, transcription: str, out_dir: Path) -> list[dict]:
    """切片并生成GIF，返回动作信息列表"""
    out_dir.mkdir(parents=True, exist_ok=True)
    segments = parse_segments(transcription)
    actions = group_into_actions(segments)
    if not actions:
        return []

    clips = []
    for i, action in enumerate(actions):
        # 过滤过短的片段
        duration = time_to_seconds(action['end']) - time_to_seconds(action['start'])
        if duration < MIN_CLIP_SEC:
            continue

        name = sanitize(action['texts'][0])
        mp4_path = out_dir / f"{i+1:02d}_{name}.mp4"
        gif_path = out_dir / f"{i+1:02d}_{name}.gif"

        # 切片（过长则截取前MAX_CLIP_SEC秒）
        start_sec = max(0, time_to_seconds(action['start']) - 0.5)
        end_time = action['end']
        if duration > MAX_CLIP_SEC:
            end_sec = start_sec + MAX_CLIP_SEC
            end_time = f"{int(end_sec//3600):02d}:{int((end_sec%3600)//60):02d}:{end_sec%60:06.3f}"

        r = subprocess.run(
            ['ffmpeg', '-i', str(video_path), '-ss', str(start_sec), '-to', end_time,
             '-c', 'copy', str(mp4_path), '-y', '-loglevel', 'error'],
            capture_output=True
        )
        if r.returncode != 0 or not mp4_path.exists() or mp4_path.stat().st_size < 5000:
            continue

        # GIF（取前12秒核心动作）
        subprocess.run(
            ['ffmpeg', '-i', str(mp4_path), '-vf', 'fps=8,scale=480:-1:flags=lanczos',
             '-t', '12', str(gif_path), '-y', '-loglevel', 'error'],
            capture_output=True
        )
        if not gif_path.exists() or gif_path.stat().st_size < 1000:
            continue

        ex_type = guess_type(action['texts'])
        sets, reps = extract_sets_reps(action['texts'])
        auto_name = clean_name(action['texts'][0])

        clips.append({
            "auto_name": auto_name,
            "texts": action['texts'],
            "type": ex_type,
            "sets": sets,
            "reps": reps,
            "gif_dir": out_dir.name,
            "gif_name": gif_path.stem,
            "gif_size": gif_path.stat().st_size,
            "duration": min(duration, MAX_CLIP_SEC),
        })

    return clips


def merge_into_db(db: dict, clips: list[dict]) -> tuple[int, int]:
    """
    将切片合并入数据库，处理重名冲突：
    - 名字相同 → 比较 GIF 文件大小，保留更大的（内容更丰富）
    - 新名字 → 直接添加
    返回 (新增数量, 更新数量)
    """
    existing = {e['name']: e for e in db['exercises']}
    added, updated = 0, 0

    for clip in clips:
        name = clip['auto_name']
        if not name:
            continue

        ex_record = {
            "name": name,
            "type": clip['type'],
            "sets": clip['sets'],
            "reps": clip['reps'],
            "tips": " / ".join(clip['texts'][:2]),  # 用转录内容做初始要领描述
            "gif_dir": clip['gif_dir'],
            "gif_name": clip['gif_name'],
            "_gif_size": clip['gif_size'],
        }

        if name not in existing:
            db['exercises'].append(ex_record)
            existing[name] = ex_record
            added += 1
        else:
            # 择优：比较GIF大小（更大 = 内容更丰富）
            old_size = existing[name].get('_gif_size', 0)
            if clip['gif_size'] > old_size * 1.2:  # 新的要大20%以上才替换
                idx = next(i for i, e in enumerate(db['exercises']) if e['name'] == name)
                db['exercises'][idx].update({
                    "gif_dir": clip['gif_dir'],
                    "gif_name": clip['gif_name'],
                    "_gif_size": clip['gif_size'],
                    "type": clip['type'],
                })
                existing[name] = db['exercises'][idx]
                updated += 1

    return added, updated


def process_video(video_path: Path, index: int, total: int) -> tuple[str, list[dict]]:
    """处理单个视频，返回 (gif_dir_name, clips)"""
    print(f"\n[{index}/{total}] 🎬 {video_path.name} ({video_path.stat().st_size//1024//1024}MB)")

    topic = video_path.stem[:20]

    # 确定输出目录
    existing_dirs = [d.name for d in SLICES_DIR.iterdir() if d.is_dir()] if SLICES_DIR.exists() else []
    vid_nums = [int(m.group(1)) for d in existing_dirs if (m := re.match(r'video(\d+)', d))]
    next_num = max(vid_nums, default=0) + 1
    gif_dir_name = f"video{next_num}_{sanitize(topic, 20)}"
    out_dir = SLICES_DIR / gif_dir_name

    print(f"    📁 → {gif_dir_name}")

    transcription = transcribe(video_path, topic)
    if not transcription:
        return gif_dir_name, []

    clips = slice_and_gif(video_path, transcription, out_dir)
    print(f"    ✂️  切片 {len(clips)} 段")
    return gif_dir_name, clips


def regen_plan():
    """重新生成训练计划 HTML"""
    print("\n🔄 重新生成训练计划...")
    r = subprocess.run(
        ['python3', str(PLUGIN_DIR / 'gen_plan.py')],
        cwd=str(PLUGIN_DIR), capture_output=True, text=True
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print(f"⚠️  生成失败: {r.stderr[:200]}")


def main():
    dry_run = '--dry-run' in sys.argv
    do_regen = '--regen-plan' in sys.argv

    if not Path(WHISPER_MODEL).exists():
        print(f"❌ Whisper 模型不存在: {WHISPER_MODEL}")
        sys.exit(1)

    videos = find_videos()
    print(f"📹 发现 {len(videos)} 个视频")

    processed_hashes = load_processed_hashes()
    new_videos = [v for v in videos if video_hash(v) not in processed_hashes]
    print(f"🆕 其中 {len(new_videos)} 个未处理过")

    if not new_videos:
        print("✅ 全部已处理，无需更新")
        if do_regen:
            regen_plan()
        return

    if dry_run:
        print("\n[dry-run 模式，仅显示待处理视频]")
        for v in new_videos:
            print(f"  {v.name}")
        return

    db = load_db()
    total_added = total_updated = 0

    for i, video_path in enumerate(new_videos, 1):
        try:
            _, clips = process_video(video_path, i, len(new_videos))
            if clips:
                added, updated = merge_into_db(db, clips)
                total_added += added
                total_updated += updated
                print(f"    📚 新增 {added} 个动作，更新 {updated} 个")
            # 无论成功失败都记录为已处理（避免重复尝试失败的视频）
            processed_hashes.add(video_hash(video_path))
            save_processed_hashes(processed_hashes)
            save_db(db)
        except Exception as e:
            print(f"    ❌ 处理失败: {e}")
            processed_hashes.add(video_hash(video_path))  # 标记已尝试
            save_processed_hashes(processed_hashes)

    print(f"\n{'='*50}")
    print(f"✅ 完成！新增 {total_added} 个动作，更新 {total_updated} 个动作")
    print(f"   动作库共 {len(db['exercises'])} 个动作")

    if do_regen or total_added > 0:
        regen_plan()


if __name__ == '__main__':
    main()
