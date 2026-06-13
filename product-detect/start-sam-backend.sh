#!/bin/bash
# SAM ML Backend 启动脚本（供 Label Studio 自动标注使用）
# 端口：9090
# 用法：bash start-sam-backend.sh

export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="/Users/chat/claude/product-detect/datasets"
export LABEL_STUDIO_ML_BACKEND_V2=true   # V2协议：避免每次/setup重载模型

echo "SAM ML Backend 启动中..."
echo "端口：http://localhost:9090"
echo "（模型在第一次标注时才加载，约 10 秒）"
echo ""

exec /Users/chat/miniconda3/envs/yolov8/bin/python \
  /Users/chat/claude/product-detect/scripts/sam_ml_backend.py
