#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
GUARD="$ROOT_DIR/scripts/lib/codexpro-startup-guard.sh"
TMP_DIR="$(mktemp -d)"
PIDS=()

cleanup() {
  local pid
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

free_port() {
  node -e 'const s=require("net").createServer();s.listen(0,"127.0.0.1",()=>{console.log(s.address().port);s.close();});'
}

wait_for_listener() {
  local port="$1" attempt=0
  while ! lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 40 ]; then
      fail "listener did not start on port $port"
    fi
    sleep 0.1
  done
}

[ -f "$GUARD" ] || fail "startup guard is missing"
# shellcheck source=/dev/null
source "$GUARD"

EMPTY_PORT="$(free_port)"
if ! bash -euo pipefail -c 'source "$1"; codexpro_stop_stale_server "$2"' _ "$GUARD" "$EMPTY_PORT"; then
  fail "guard failed when the port was already free"
fi

UNRELATED_PORT="$(free_port)"
node -e 'require("http").createServer((_,res)=>res.end("ok")).listen(Number(process.argv[1]),"127.0.0.1")' "$UNRELATED_PORT" &
UNRELATED_PID=$!
PIDS+=("$UNRELATED_PID")
wait_for_listener "$UNRELATED_PORT"

if codexpro_stop_stale_server "$UNRELATED_PORT" 2>/dev/null; then
  fail "guard accepted a non-CodexPro listener"
fi
kill -0 "$UNRELATED_PID" 2>/dev/null || fail "guard killed a non-CodexPro listener"

MANAGED_PORT="$(free_port)"
mkdir -p "$TMP_DIR/workspace"
CODEXPRO_HTTP="$(npm root -g)/codexpro/dist/http.js"
[ -f "$CODEXPRO_HTTP" ] || fail "global CodexPro HTTP entrypoint was not found"
CODEXPRO_ROOT="$TMP_DIR/workspace" \
CODEXPRO_ALLOWED_ROOTS="$TMP_DIR/workspace" \
CODEXPRO_HOST=127.0.0.1 \
CODEXPRO_PORT="$MANAGED_PORT" \
CODEXPRO_BASH_MODE=off \
CODEXPRO_WRITE_MODE=off \
CODEXPRO_TOOL_MODE=minimal \
CODEXPRO_HTTP_TOKEN=test-only-token \
node "$CODEXPRO_HTTP" >/dev/null 2>&1 &
MANAGED_PID=$!
PIDS+=("$MANAGED_PID")
wait_for_listener "$MANAGED_PORT"

codexpro_stop_stale_server "$MANAGED_PORT"
if lsof -nP -iTCP:"$MANAGED_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
  fail "CodexPro listener still owns port $MANAGED_PORT"
fi

grep -Fq 'codexpro_stop_stale_server 8787' "$ROOT_DIR/scripts/start-codexpro-full.sh" || fail "launcher does not call the startup guard"
grep -Fq 'unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy' "$ROOT_DIR/scripts/start-codexpro-full.sh" || fail "launcher does not isolate ngrok from proxy variables"

printf 'PASS: CodexPro startup guard boundaries verified\n'
