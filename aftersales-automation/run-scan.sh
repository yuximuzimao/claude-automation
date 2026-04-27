#!/bin/bash
# 工单巡检包装脚本 - 由 launchd 调用
# 确保 node 和 PATH 正确

export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.nvm/versions/node/v22.22.1/bin:$PATH"
LOG_FILE="$HOME/claude/aftersales-automation/scan.log"
MAX_LINES=500

cd "$HOME/claude/aftersales-automation"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 开始巡检 =====" >> "$LOG_FILE"
node scan-all.js 2>> "$LOG_FILE" >> "$LOG_FILE"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 巡检完成 =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 保持日志不超过 MAX_LINES 行
total=$(wc -l < "$LOG_FILE")
if [ "$total" -gt "$MAX_LINES" ]; then
  tail -n "$MAX_LINES" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
