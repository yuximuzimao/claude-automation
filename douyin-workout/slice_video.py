#!/usr/bin/env python3
"""
视频动作切片工具
根据转录文本中的动作关键词，把视频切割成独立动作片段
用法：python3 slice_video.py <视频文件> <转录md文件> <输出目录>
"""
import subprocess
import sys
from pathlib import Path

from utils import parse_segments, group_into_actions, time_to_seconds, sanitize


def slice_video(video_path, start_time, end_time, output_path):
    start_sec = max(0, time_to_seconds(start_time) - 0.5)
    result = subprocess.run([
        'ffmpeg', '-i', video_path,
        '-ss', str(start_sec), '-to', end_time,
        '-c', 'copy', output_path, '-y'
    ], capture_output=True)
    return result.returncode == 0


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("用法：python3 slice_video.py <视频文件> <转录md文件> <输出目录>")
        sys.exit(1)

    video_path = sys.argv[1]
    transcription_file = sys.argv[2]
    output_dir = sys.argv[3]

    transcription = Path(transcription_file).read_text(encoding='utf-8')
    segments = parse_segments(transcription)
    actions = group_into_actions(segments)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"识别到 {len(actions)} 个动作段落")
    for i, action in enumerate(actions):
        label = action['texts'][0]
        name = sanitize(label)
        output_file = f"{output_dir}/{i+1:02d}_{name}.mp4"
        desc = ' / '.join(action['texts'][:3])
        print(f"  [{i+1}] {action['start']} → {action['end']}  {desc[:50]}")
        ok = slice_video(video_path, action['start'], action['end'], output_file)
        print(f"       → {'已保存: ' + output_file if ok else '切片失败'}")

    print(f"\n完成！共生成 {len(actions)} 个片段，保存至：{output_dir}")
