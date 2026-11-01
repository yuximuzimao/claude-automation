#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const packageRoot = process.argv[2];
if (!packageRoot) throw new Error("CodexPro package root is required.");

// 只给公开 read 工具分页，内部规则加载和写入校验继续使用原来的读取函数。
const pagedRead = String.raw`export async function readTextFilePage(config, guard, workspace, filePath, options = {}) {
    const maxBytes = Math.min(options.maxBytes ?? config.maxReadBytes, config.maxReadBytes);
    // 0.30.2 的范围读取仍以 2 MB 限制源文件；内部区间预算另需容纳行号前缀。
    const maxSourceBytes = 2_000_000;
    const maxNumberedBytes = maxSourceBytes + (maxSourceBytes + 1) * (String(maxSourceBytes + 1).length + 3);
    const result = await readTextFile({ ...config, maxReadBytes: maxNumberedBytes }, guard, workspace, filePath, {
        ...options,
        startLine: options.startLine ?? 1,
        maxBytes: maxNumberedBytes
    });
    const page = [];
    let returnedBytes = 0;
    for (const line of result.text.split("\n")) {
        const lineBytes = Buffer.byteLength(line, "utf8") + (page.length ? 1 : 0);
        if (returnedBytes + lineBytes > maxBytes) {
            if (!page.length) {
                throw new CodexProError("第 " + result.startLine + " 行本身超过本次返回上限（" + maxBytes + " 字节）。请提高 max_bytes，或用 search/bash 按键提取所需内容。");
            }
            break;
        }
        page.push(line);
        returnedBytes += lineBytes;
    }
    const endLine = result.startLine + page.length - 1;
    return {
        ...result,
        text: page.join("\n"),
        endLine,
        returnedBytes,
        truncated: result.truncated || endLine < result.endLine,
        nextStartLine: endLine < result.totalLines ? endLine + 1 : null
    };
}
`;

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) {
    throw new Error("CodexPro read 代码结构已变化，未写入补丁；请先核对新版实现。");
  }
  return source.replace(before, after);
}

const fsOpsPath = path.join(packageRoot, "dist/fsOps.js");
const serverPath = path.join(packageRoot, "dist/server.js");
const originals = [fsOpsPath, serverPath].map((file) => fs.readFileSync(file, "utf8"));
let [fsOps, server] = originals;
if (!fsOps.includes("export async function readTextFilePage(")) {
  fsOps = replaceOnce(fsOps, "export async function writeTextFile(", pagedRead + "export async function writeTextFile(");
}
if (!server.includes("const result = await readTextFilePage(")) {
  server = replaceOnce(server, "repoTree, listFiles, readTextFile, writeTextFile", "repoTree, listFiles, readTextFile, readTextFilePage, writeTextFile");
  server = replaceOnce(server, "const result = await readTextFile(config, guard, workspace, args.path, {", "const result = await readTextFilePage(config, guard, workspace, args.path, {");
  server = replaceOnce(server, "Maximum file bytes. Capped by server config.", "Maximum returned text bytes, including line numbers. Large files are paged automatically; continue from nextStartLine. Capped by server config.");
  server = replaceOnce(server,
    'Read a specific text file with line numbers. Avoid rereading files after write/edit/apply_patch unless exact final content is needed.',
    'Read a text file with line numbers. Returns a bounded page for large files; max_bytes limits returned text, not source file size. Follow the returned continuation instruction when more lines are needed. Avoid rereading files after write/edit/apply_patch unless exact final content is needed.');
  server = replaceOnce(server,
    'return textResult(text, { workspace_id: workspace.id, root: workspace.root, ...result });\n    });\n    registerCodexTool(config, server, "view_image",',
    'const continuation = result.nextStartLine == null ? "" : `\\n\\n这里只返回了文件的一部分。若需继续，请调用 read，path 保持不变，start_line 设为 ${result.nextStartLine}，并省略 end_line 或将其设到该行之后。`;' +
    '\n        return textResult(text + continuation, { workspace_id: workspace.id, root: workspace.root, ...result });\n    });\n    registerCodexTool(config, server, "view_image",');
}

const updates = [fsOps, server];
let changed = false;
for (const [index, file] of [fsOpsPath, serverPath].entries()) {
  if (updates[index] === originals[index]) continue;
  const temporary = `${file}.paged-read-${process.pid}.tmp`;
  try {
    fs.writeFileSync(temporary, updates[index], { mode: fs.statSync(file).mode });
    fs.renameSync(temporary, file);
    if (fs.readFileSync(file, "utf8") !== updates[index]) throw new Error(`写入验证失败：${file}`);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
  changed = true;
}
console.log(changed ? "CodexPro 大文件分段读取：已安装。" : "CodexPro 大文件分段读取：已就绪。");
