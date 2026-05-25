#!/bin/bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate yolov8
cd /Users/chat/claude/product-detect
exec python -u scripts/train.py --brand kgos
