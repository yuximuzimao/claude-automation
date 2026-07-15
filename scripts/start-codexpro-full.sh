#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/codexpro-startup-guard.sh
source "$SCRIPT_DIR/lib/codexpro-startup-guard.sh"

codexpro_stop_stale_server 8787

cd /Users/chat/claude

# Search-heavy monorepo default. CodexPro clamps this to 2000 internally.
export CODEXPRO_MAX_SEARCH_RESULTS="${CODEXPRO_MAX_SEARCH_RESULTS:-1000}"

# Keep full env inheritance opt-in because it can expose local tokens and proxy/env
# values to ChatGPT-triggered bash commands.
export CODEXPRO_INHERIT_ENV="${CODEXPRO_INHERIT_ENV:-0}"

# ngrok's free agent rejects inherited HTTP/SOCKS proxy settings (ERR_NGROK_9009).
# Keep the shell shortcut's proxy behavior for other CodexPro subcommands, but let
# the local server and ngrok tunnel use the machine's direct network path.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

exec codexpro start \
  --allow-root /Users/chat/.config/superpowers/worktrees
