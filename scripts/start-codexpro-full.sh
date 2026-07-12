#!/usr/bin/env bash
set -euo pipefail

cd /Users/chat/claude

# This launcher fixes the primary root and the only additional worktree root.
# Do not let caller environment leftovers expand CodexPro file-tool access.
unset CODEXPRO_ROOT
unset CODEBASE_BRIDGE_REPO_ROOT
unset CODEXPRO_ALLOW_HOME
unset CODEBASE_BRIDGE_ALLOWED_ROOTS

# Search-heavy monorepo default. CodexPro clamps this to 2000 internally.
export CODEXPRO_MAX_SEARCH_RESULTS="${CODEXPRO_MAX_SEARCH_RESULTS:-1000}"

# Keep full env inheritance opt-in because it can expose local tokens and proxy/env
# values to ChatGPT-triggered bash commands.
export CODEXPRO_INHERIT_ENV="${CODEXPRO_INHERIT_ENV:-0}"

# Keep every Claude/Codex isolated project worktree available to the ChatGPT MCP app.
# CodexPro profiles do not persist --allow-root, so this belongs in the launcher.
readonly SUPERPOWERS_WORKTREE_ROOT="/Users/chat/.config/superpowers/worktrees"

exec codexpro start \
  --allow-root "$SUPERPOWERS_WORKTREE_ROOT"
