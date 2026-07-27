#!/bin/bash
set -euo pipefail

BACKUP_SOURCE_DIR="${WORKSPACE_BACKUP_SOURCE_DIR:-/Users/chat/claude}"
BACKUP_DIR="${WORKSPACE_BACKUP_DIR:-/Users/chat/backups}"
BACKUP_KEEP="${WORKSPACE_BACKUP_KEEP:-8}"
CASE_FILE="${ORDER_REVIEW_CASE_FILE:-/Users/chat/Library/Application Support/Order Review/cases.json}"
EVENT_FILE="${ORDER_REVIEW_EVENT_FILE:-/Users/chat/Library/Application Support/Order Review/recommendation-events.jsonl}"
CASE_BACKUP_DIR="${ORDER_REVIEW_CASE_BACKUP_DIR:-/Users/chat/Library/Application Support/Order Review/backups}"
CASE_BACKUP_INCLUDE="${ORDER_REVIEW_CASE_BACKUP_INCLUDE:-3}"
ORDER_REVIEW_SOURCE_DIR="${ORDER_REVIEW_SOURCE_DIR:-/Users/chat/claude/order-review/src}"
ORDER_REVIEW_PYTHON="${ORDER_REVIEW_PYTHON:-/Users/chat/miniconda3/bin/python3.13}"
HEALTH_FILE="${ORDER_REVIEW_HEALTH_FILE:-$BACKUP_DIR/order-review-health.txt}"
DEGRADED=0

if ! [[ "$BACKUP_KEEP" =~ ^[1-9][0-9]*$ ]]; then
  echo "[backup] invalid WORKSPACE_BACKUP_KEEP: $BACKUP_KEEP" >&2
  exit 2
fi
if ! [[ "$CASE_BACKUP_INCLUDE" =~ ^[1-9][0-9]*$ ]]; then
  echo "[backup] invalid ORDER_REVIEW_CASE_BACKUP_INCLUDE: $CASE_BACKUP_INCLUDE" >&2
  exit 2
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/workspace-$(date +%Y%m%d-%H%M%S)-$$.tar.gz"
ARCHIVE_TEMP=$(mktemp "$BACKUP_DIR/.workspace-backup.XXXXXX")
STAGING_DIR=$(mktemp -d "${TMPDIR:-/tmp}/workspace-backup.XXXXXX")
HEALTH_TEMP=""

cleanup() {
  rm -f "$ARCHIVE_TEMP"
  if [[ -n "$HEALTH_TEMP" ]]; then
    rm -f "$HEALTH_TEMP"
  fi
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$STAGING_DIR/order-review-data"

COPIED_CASE_BACKUPS=0
copy_valid_case_backups() {
  local listing_path
  local candidate
  listing_path="$STAGING_DIR/order-review-data/.valid-case-backups.list"
  COPIED_CASE_BACKUPS=0
  mkdir -p "$STAGING_DIR/order-review-data/valid-case-backups"
  if ! PYTHONPATH="$ORDER_REVIEW_SOURCE_DIR" \
    "$ORDER_REVIEW_PYTHON" -m order_review.case_restore \
    --list \
    --paths-only \
    --target "$CASE_FILE" \
    --backup-dir "$CASE_BACKUP_DIR" \
    --limit "$CASE_BACKUP_INCLUDE" > "$listing_path"; then
    rm -f "$listing_path"
    echo "[backup] warning: failed to enumerate valid order-review backups" >&2
    return 1
  fi
  while IFS= read -r candidate; do
    if [[ -z "$candidate" ]]; then
      continue
    fi
    if cp -p "$candidate" "$STAGING_DIR/order-review-data/valid-case-backups/"; then
      COPIED_CASE_BACKUPS=$((COPIED_CASE_BACKUPS + 1))
    else
      echo "[backup] warning: failed to copy order-review backup: $candidate" >&2
    fi
  done < "$listing_path"
  rm -f "$listing_path"
}

if [[ -f "$CASE_FILE" ]]; then
  cp -p "$CASE_FILE" "$STAGING_DIR/order-review-data/cases.json"
  if PYTHONPATH="$ORDER_REVIEW_SOURCE_DIR" \
    "$ORDER_REVIEW_PYTHON" -m order_review.case_audit \
    --path "$STAGING_DIR/order-review-data/cases.json" >/dev/null; then
    :
  else
    DEGRADED=1
    mv \
      "$STAGING_DIR/order-review-data/cases.json" \
      "$STAGING_DIR/order-review-data/cases.invalid.json"
    {
      echo "ORDER_REVIEW_CASES_INVALID"
      echo "正式 cases.json 未通过健康检查，未作为有效正式案例归档。"
      echo "原始故障文件：cases.invalid.json"
    } > "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_INVALID.txt"
    echo \
      "[backup] warning: order-review cases failed validation; archived as cases.invalid.json" \
      >&2

    if copy_valid_case_backups; then
      echo "附带有效应用内备份：$COPIED_CASE_BACKUPS" \
        >> "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_INVALID.txt"
    else
      echo "有效应用内备份枚举失败，请检查备份目录。" \
        >> "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_INVALID.txt"
    fi
  fi
else
  DEGRADED=1
  {
    echo "ORDER_REVIEW_CASES_MISSING"
    echo "正式 cases.json 不存在，本次归档不包含正式案例文件。"
    echo "缺失路径：$CASE_FILE"
  } > "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_MISSING.txt"
  if copy_valid_case_backups; then
    echo "附带有效应用内备份：$COPIED_CASE_BACKUPS" \
      >> "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_MISSING.txt"
  else
    echo "有效应用内备份枚举失败，请检查备份目录。" \
      >> "$STAGING_DIR/order-review-data/ORDER_REVIEW_CASES_MISSING.txt"
  fi
  echo \
    "[backup] warning: order-review cases not found; workspace archived with degraded status: $CASE_FILE" \
    >&2
fi

if [[ -f "$EVENT_FILE" ]]; then
  cp -p "$EVENT_FILE" "$STAGING_DIR/order-review-data/recommendation-events.jsonl"
  if ! PYTHONPATH="$ORDER_REVIEW_SOURCE_DIR" \
    "$ORDER_REVIEW_PYTHON" -m order_review.recommendation_event_audit \
    --path "$STAGING_DIR/order-review-data/recommendation-events.jsonl" >/dev/null; then
    sleep 0.1
    cp -p "$EVENT_FILE" "$STAGING_DIR/order-review-data/recommendation-events.jsonl"
  fi
  if ! PYTHONPATH="$ORDER_REVIEW_SOURCE_DIR" \
    "$ORDER_REVIEW_PYTHON" -m order_review.recommendation_event_audit \
    --path "$STAGING_DIR/order-review-data/recommendation-events.jsonl" >/dev/null; then
    DEGRADED=1
    mv \
      "$STAGING_DIR/order-review-data/recommendation-events.jsonl" \
      "$STAGING_DIR/order-review-data/recommendation-events.invalid.jsonl"
    {
      echo "ORDER_REVIEW_EVENTS_INVALID"
      echo "推荐事件 JSONL 未通过健康检查。"
      echo "原始故障文件：recommendation-events.invalid.jsonl"
    } > "$STAGING_DIR/order-review-data/ORDER_REVIEW_EVENTS_INVALID.txt"
    echo "[backup] warning: recommendation events failed validation" >&2
  fi
fi

cd "$BACKUP_SOURCE_DIR"

tar czf "$ARCHIVE_TEMP" \
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
  . \
  -C "$STAGING_DIR" order-review-data

mv "$ARCHIVE_TEMP" "$BACKUP_FILE"

SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "[backup] $(date '+%Y-%m-%d %H:%M'): $BACKUP_FILE ($SIZE)"

shopt -s nullglob
backups=("$BACKUP_DIR"/workspace-*.tar.gz)
while (( ${#backups[@]} > BACKUP_KEEP )); do
  stale="${backups[0]}"
  rm -f "$stale"
  backups=("${backups[@]:1}")
done

echo "[backup] done, kept latest $BACKUP_KEEP archives"

mkdir -p "$(dirname "$HEALTH_FILE")"
HEALTH_TEMP=$(mktemp "$(dirname "$HEALTH_FILE")/.order-review-health.XXXXXX")
if (( DEGRADED )); then
  HEALTH_STATUS="degraded"
else
  HEALTH_STATUS="healthy"
fi
{
  echo "status=$HEALTH_STATUS"
  echo "checkedAt=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "archive=$BACKUP_FILE"
} > "$HEALTH_TEMP"
mv "$HEALTH_TEMP" "$HEALTH_FILE"
HEALTH_TEMP=""

if (( DEGRADED )); then
  echo "[backup] completed with degraded order-review data; see $HEALTH_FILE" >&2
  exit 3
fi
