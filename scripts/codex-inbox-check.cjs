#!/usr/bin/env node
/**
 * Codex Handoff Inbox Checker
 *
 * SessionStart hook: reads docs/codex-handoff/inbox.json (if exists),
 * injects notification into session context when Codex has pending requests.
 *
 * Zero-overhead when inbox is empty or missing — outputs nothing.
 * When pending items exist, outputs ~50 tokens of notification context.
 */
const fs = require("node:fs");
const path = require("node:path");

const INBOX_PATH = path.resolve(
  process.env.CLAUDE_PROJECT_DIR || process.cwd(),
  "docs/codex-handoff/inbox.json"
);

try {
  if (!fs.existsSync(INBOX_PATH)) {
    process.exit(0);
  }

  const inbox = JSON.parse(fs.readFileSync(INBOX_PATH, "utf8"));
  const pending = inbox?.pending;

  if (!Array.isArray(pending) || pending.length === 0) {
    process.exit(0);
  }

  const lines = pending.map(
    (item, i) =>
      `  #${i + 1} [${item.project || "?"}] ${item.action || "?"} — ${item.summary || "(无摘要)"} → ${item.file || "?"}`
  );
  const context = [
    "[Codex协作收件箱] 有 " + pending.length + " 条待处理协作请求:",
    ...lines,
    "请询问用户是否需要查看全文。",
  ].join("\n");

  const output = {
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: context,
    },
  };
  process.stdout.write(JSON.stringify(output) + "\n");
  process.exit(0);
} catch {
  // Inbox parse failed — fail silently, not worth blocking session start
  process.exit(0);
}
