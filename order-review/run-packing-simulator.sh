#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST="127.0.0.1"
PORT="3466"
URL="http://${HOST}:${PORT}/"
CATALOG_URL="${URL}api/catalog"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/order-review-packing-simulator.log"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"

is_simulator_running() {
  curl -fsS --max-time 1 "$CATALOG_URL" 2>/dev/null | grep -q '"apiVersion"'
}

if is_simulator_running; then
  echo "装箱实验已运行：$URL"
  open "$URL"
  exit 0
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "无法启动：固定端口 $PORT 已被其他程序占用。" >&2
  echo "装箱实验固定地址不会自动改端口，请先释放 $PORT。" >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "无法启动：找不到 $PYTHON_BIN。可通过 PYTHON_BIN 指定 Python 解释器。" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR"

PYTHONPATH=src nohup "$PYTHON_BIN" -m order_review.packing_simulator_web \
  --host "$HOST" \
  --port "$PORT" \
  >"$LOG_FILE" 2>&1 &

for _ in {1..40}; do
  if is_simulator_running; then
    echo "装箱实验已启动：$URL"
    echo "日志：$LOG_FILE"
    open "$URL"
    exit 0
  fi
  sleep 0.25
done

echo "装箱实验启动失败，请查看日志：$LOG_FILE" >&2
exit 1
