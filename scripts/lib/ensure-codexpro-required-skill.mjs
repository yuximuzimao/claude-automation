#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const packageRoot = process.argv[2];
const skillName = process.argv[3] || "chinese-polish";

if (!packageRoot) {
  throw new Error("CodexPro package root is required.");
}

if (!/^[a-z0-9-]+$/.test(skillName)) {
  throw new Error(`Invalid required skill name: ${skillName}`);
}

function writeAtomic(filePath, content) {
  const stat = fs.statSync(filePath);
  const tempPath = `${filePath}.required-skill-${process.pid}.tmp`;

  try {
    fs.writeFileSync(tempPath, content, { mode: stat.mode });
    fs.renameSync(tempPath, filePath);
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }
}

function ensureServerInstruction() {
  const serverPath = path.join(packageRoot, "dist", "server.js");
  const marker = `call load_skill with name=\\"${skillName}\\" and source=\\"user\\"`;
  const anchor = '        "Preferred workflow:",\n';
  const instruction =
    `        "Mandatory startup rule: Immediately after open_current_workspace, ` +
    `call load_skill with name=\\"${skillName}\\" and source=\\"user\\". ` +
    `Do this once per MCP session before any user-facing Chinese response. ` +
    `This does not require an explicit @ invocation from the user.",\n`;

  const source = fs.readFileSync(serverPath, "utf8");
  if (source.includes(marker)) return false;
  if (!source.includes(anchor)) {
    throw new Error(`CodexPro server instruction anchor changed: ${serverPath}`);
  }

  const updated = source.replace(anchor, `${anchor}${instruction}`);
  writeAtomic(serverPath, updated);
  return true;
}

function ensurePromptInstruction() {
  const promptPath = path.join(packageRoot, "CHATGPT_PROMPT.md");
  if (!fs.existsSync(promptPath)) return false;

  const marker = `call load_skill with name="${skillName}" and source="user"`;
  const anchor = "Call server_config first, then open_current_workspace with include_tree=false.\n";
  const instruction =
    `Immediately after open_current_workspace, call load_skill with name="${skillName}" ` +
    `and source="user" once for this MCP session. Apply it to every user-facing ` +
    `Chinese response. Do not wait for an explicit @ invocation.\n`;

  const source = fs.readFileSync(promptPath, "utf8");
  if (source.includes(marker)) return false;
  if (!source.includes(anchor)) {
    throw new Error(`CodexPro ChatGPT prompt anchor changed: ${promptPath}`);
  }

  const updated = source.replace(anchor, `${anchor}${instruction}`);
  writeAtomic(promptPath, updated);
  return true;
}

const serverChanged = ensureServerInstruction();
const promptChanged = ensurePromptInstruction();

console.log(
  serverChanged || promptChanged
    ? `Restored mandatory CodexPro skill: ${skillName}`
    : `Mandatory CodexPro skill already present: ${skillName}`,
);
