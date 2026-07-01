#!/bin/bash
set -e
BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/workspace-$(date +%Y%m%d).tar.gz"

cd /Users/chat/claude

tar czf "$BACKUP_FILE" \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='_sandbox' \
  --exclude='_exports' \
  --exclude='backups' \
  --exclude='*.tar.gz' \
  --exclude='product-detect/datasets' \
  --exclude='product-detect/runs' \
  --exclude='product-detect/weights' \
  --exclude='douyin-workout/videos' \
  --exclude='douyin-workout/output' \
  .

SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "[backup] $(date '+%Y-%m-%d %H:%M'): $BACKUP_FILE ($SIZE)"

# 只保留最新
find "$BACKUP_DIR" -name 'workspace-*.tar.gz' ! -name "workspace-$(date +%Y%m%d).tar.gz" -delete 2>/dev/null

echo "[backup] done, kept only latest"
