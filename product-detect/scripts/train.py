#!/usr/bin/env python3
"""
本机 CPU 训练脚本（低优先级，不影响售后系统）

前置：conda activate yolov8
用法：python scripts/train.py --brand kgos [--model yolov8n]
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 降低进程优先级，保证售后系统不受影响
try:
    os.nice(10)
except AttributeError:
    pass  # Windows 不支持，忽略


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"])
    parser.add_argument("--model", default="yolov8n",
                        choices=["yolov8n", "yolov8s"],
                        help="yolov8n=快速验证(~6h)，yolov8s=更准确(~16h)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    data_yaml = project_root / "datasets" / args.brand / "data.yaml"

    if not data_yaml.exists():
        print(f"找不到数据集：{data_yaml}")
        print(f"请先运行: python scripts/generate.py --brand {args.brand}")
        sys.exit(1)

    from ultralytics import YOLO

    if args.resume:
        last_pt = project_root / "runs" / f"{args.brand}_{args.model}" / "weights" / "last.pt"
        if not last_pt.exists():
            print(f"找不到 {last_pt}，从头开始")
            model = YOLO(f"{args.model}.pt")
            args.resume = False
        else:
            print(f"从 {last_pt} 恢复训练")
            model = YOLO(str(last_pt))
    else:
        model = YOLO(f"{args.model}.pt")

    print(f"""
训练配置：
  品牌: {args.brand}
  模型: {args.model}
  数据: {data_yaml}
  轮次: {args.epochs}（patience=20 早停）
  设备: CPU
  进程优先级: nice +10（不影响售后系统）

预计时间（{args.model}）：
  yolov8n: 约 6-10 小时（推荐先用这个验证）
  yolov8s: 约 15-22 小时

可以 Ctrl+C 中断，下次用 --resume 继续
""")

    train_kwargs = dict(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=640,
        batch=4,        # CPU 适合的批大小
        workers=4,      # 限制 worker 避免抢占系统资源
        device="cpu",
        patience=20,    # 20轮无改善则早停
        project=str(project_root / "runs"),
        name=f"{args.brand}_{args.model}",
        exist_ok=True,
        verbose=True,
    )
    if args.resume:
        train_kwargs["resume"] = True
    model.train(**train_kwargs)

    # 训练完成后导出 ONNX（用于生产推理）
    best_pt = project_root / "runs" / "detect" / f"{args.brand}_{args.model}" / "weights" / "best.pt"
    if best_pt.exists():
        print(f"\n导出 ONNX 模型...")
        export_model = YOLO(str(best_pt))
        export_model.export(format="onnx", dynamic=True, simplify=True)
        onnx_path = best_pt.parent / "best.onnx"
        dest = project_root / "models" / f"{args.brand}_best.onnx"
        dest.parent.mkdir(exist_ok=True)
        import shutil
        shutil.copy(onnx_path, dest)
        print(f"模型已保存: {dest}")


if __name__ == "__main__":
    main()
