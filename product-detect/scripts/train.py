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


def lower_process_priority():
    # 降低进程优先级，保证售后系统不受影响
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


def resolve_run_name(brand: str, model_name: str, name: str | None) -> str:
    return name or f"{brand}_{model_name}"


def build_train_kwargs(
    project_root: Path,
    data_yaml: Path,
    brand: str,
    model_name: str,
    run_name: str,
    epochs: int,
    resume: bool,
    finetune: Path | None,
) -> dict:
    train_kwargs = dict(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=640,
        batch=4,
        workers=4,
        device="cpu",
        patience=20,
        project=str(project_root / "runs"),
        name=run_name,
        exist_ok=True,
        verbose=True,
    )

    if finetune is not None:
        train_kwargs.update(
            lr0=0.002,
            optimizer="AdamW",
            patience=15,
            mosaic=0.8,
            close_mosaic=5,
        )
    elif resume:
        train_kwargs["resume"] = True

    return train_kwargs


def main():
    lower_process_priority()

    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"])
    parser.add_argument("--model", default="yolov8n",
                        choices=["yolov8n", "yolov8s"],
                        help="yolov8n=快速验证(~6h)，yolov8s=更准确(~16h)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    parser.add_argument("--finetune", type=Path, default=None,
                        help="从指定 .pt 权重初始化继续微调（不是 resume）")
    parser.add_argument("--name", default=None,
                        help="自定义 run name，避免覆盖旧训练目录")
    parser.add_argument("--export-production", action="store_true",
                        help="训练完成后导出并覆盖 models/<brand>_best.onnx；黄金验证集通过前不要使用")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    data_yaml = project_root / "datasets" / args.brand / "data.yaml"

    if not data_yaml.exists():
        print(f"找不到数据集：{data_yaml}")
        print(f"请先运行: python scripts/generate.py --brand {args.brand}")
        sys.exit(1)

    from ultralytics import YOLO

    run_name = resolve_run_name(args.brand, args.model, args.name)

    if args.finetune is not None:
        if not args.finetune.exists():
            print(f"找不到 finetune 权重：{args.finetune}")
            sys.exit(1)
        print(f"从 {args.finetune} 初始化微调")
        model = YOLO(str(args.finetune))
        args.resume = False
    elif args.resume:
        last_pt = project_root / "runs" / run_name / "weights" / "last.pt"
        if not last_pt.exists():
            print(f"找不到 {last_pt}，从头开始")
            model = YOLO(f"{args.model}.pt")
            args.resume = False
        else:
            print(f"从 {last_pt} 恢复训练")
            model = YOLO(str(last_pt))
    else:
        model = YOLO(f"{args.model}.pt")

    train_kwargs = build_train_kwargs(
        project_root=project_root,
        data_yaml=data_yaml,
        brand=args.brand,
        model_name=args.model,
        run_name=run_name,
        epochs=args.epochs,
        resume=args.resume,
        finetune=args.finetune,
    )

    print(f"""
训练配置：
  品牌: {args.brand}
  模型: {args.model}
  输出: runs/{run_name}
  数据: {data_yaml}
  轮次: {args.epochs}（patience={train_kwargs["patience"]} 早停）
  设备: CPU
  进程优先级: nice +10（不影响售后系统）

预计时间（{args.model}）：
  yolov8n: 约 6-10 小时（推荐先用这个验证）
  yolov8s: 约 15-22 小时

可以 Ctrl+C 中断，下次用 --resume 继续
""")

    model.train(**train_kwargs)

    if not args.export_production:
        print("\n训练已完成；未覆盖生产 ONNX。黄金验证集通过后再加 --export-production 导出。")
        return

    # 训练完成后导出 ONNX（用于生产推理）
    best_pt = project_root / "runs" / run_name / "weights" / "best.pt"
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
