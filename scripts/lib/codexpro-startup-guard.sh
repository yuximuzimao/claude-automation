#!/usr/bin/env bash

codexpro_port_owner_pid() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

codexpro_process_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null
}

codexpro_is_managed_server() {
  local pid="$1" owner_uid command_line
  owner_uid="$(ps -p "$pid" -o uid= 2>/dev/null | tr -d ' ')"
  [ "$owner_uid" = "$(id -u)" ] || return 1
  command_line="$(codexpro_process_command "$pid")"
  [[ "$command_line" == "node "* || "$command_line" == *"/node "* ]] || return 1
  [[ "$command_line" == *"/lib/node_modules/codexpro/dist/http.js"* ]]
}

codexpro_stop_stale_server() {
  local port="${1:-8787}" pid command_line attempt=0
  pid="$(codexpro_port_owner_pid "$port")"
  [ -n "$pid" ] || return 0

  if ! codexpro_is_managed_server "$pid"; then
    command_line="$(codexpro_process_command "$pid")"
    printf '端口 %s 已被非 CodexPro 进程占用（PID %s）：%s\n' "$port" "$pid" "$command_line" >&2
    printf '为避免误杀，启动已停止。请先确认并处理该进程。\n' >&2
    return 1
  fi

  printf '检测到残留的 CodexPro 本地服务（PID %s），正在安全停止...\n' "$pid"
  kill -TERM "$pid"
  while codexpro_port_owner_pid "$port" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 20 ]; then
      printf 'CodexPro 进程收到 TERM 后仍未释放端口 %s；未使用强制终止。\n' "$port" >&2
      return 1
    fi
    sleep 0.25
  done
}
