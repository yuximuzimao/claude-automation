#!/bin/bash
# Label Studio 启动脚本
# 允许从 product-detect/datasets/ 目录加载本地图片
# 用法：bash start-label-studio.sh

export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="/Users/chat/claude/product-detect/datasets"

echo "Label Studio 启动中..."
echo "本地图片路径：$LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"
echo "浏览器访问：http://localhost:8080"
echo ""

label-studio start --port 8080
