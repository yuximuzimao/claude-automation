import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

const packageRoot = process.env.CODEXPRO_PACKAGE_ROOT;
assert.ok(packageRoot, "Set CODEXPRO_PACKAGE_ROOT to the installed CodexPro package.");
const load = (file) => import(pathToFileURL(path.join(packageRoot, file)).href);
const { loadConfig } = await load("dist/config.js");
const { PathGuard, WorkspaceManager } = await load("dist/guard.js");
const { readTextFile, readTextFilePage } = await load("dist/fsOps.js");

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "codexpro-paged-read-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const config = { ...loadConfig(["--root", root]), maxReadBytes: 180_000 };
  const guard = new PathGuard(config);
  const workspace = new WorkspaceManager(config).defaultWorkspace();
  return { root, config, guard, workspace };
}

test("71,807-byte file can be read with the previously failing 30KB budget", async (t) => {
  const f = await fixture(t);
  const text = "entry: value\n".repeat(5_500).padEnd(71_807, "x");
  assert.equal(Buffer.byteLength(text), 71_807);
  await fs.writeFile(path.join(f.root, "registry.txt"), text);
  await assert.rejects(readTextFile(f.config, f.guard, f.workspace, "registry.txt", {
    maxBytes: 30_000, startLine: 1, endLine: 160
  }), /File is too large/);
  const result = await readTextFilePage(f.config, f.guard, f.workspace, "registry.txt", {
    maxBytes: 30_000, startLine: 1, endLine: 160
  });
  assert.equal(result.endLine, 160);
  assert.ok(result.text.includes("160 | entry: value"));
  assert.equal(result.bytes, 71_807);
  assert.ok(result.returnedBytes <= 30_000);
});

test("file larger than the old 180KB ceiling supports a narrow line range", async (t) => {
  const f = await fixture(t);
  const text = Array.from({ length: 20_000 }, (_, i) => `registry entry ${i} ${"x".repeat(20)}`).join("\n");
  await fs.writeFile(path.join(f.root, "large.txt"), text);
  const result = await readTextFilePage(f.config, f.guard, f.workspace, "large.txt", {
    maxBytes: 1_000, startLine: 1_001, endLine: 1_010
  });
  assert.ok(result.bytes > 180_000);
  assert.equal(result.startLine, 1_001);
  assert.equal(result.endLine, 1_010);
  assert.ok(result.text.includes("registry entry 1000"));
  assert.equal(result.sha256, createHash("sha256").update(text).digest("hex"));
});

test("automatic pages preserve UTF-8, CRLF and every line without overlap", async (t) => {
  const f = await fixture(t);
  const expected = Array.from({ length: 400 }, (_, i) => `${i}: 中文😀 ${"a".repeat(30)}`).concat("");
  await fs.writeFile(path.join(f.root, "unicode.txt"), expected.join("\r\n"));
  const actual = [];
  let startLine = 1;
  for (let pages = 0; startLine != null; pages++) {
    assert.ok(pages < 100, "pagination must advance");
    const page = await readTextFilePage(f.config, f.guard, f.workspace, "unicode.txt", {
      maxBytes: 1_000, startLine
    });
    assert.ok(Buffer.byteLength(page.text, "utf8") <= 1_000);
    assert.equal(page.returnedBytes, Buffer.byteLength(page.text, "utf8"));
    assert.ok(!page.text.includes("\ufffd"));
    actual.push(...page.text.split("\n").map((line) => line.replace(/^\s*\d+ \| /, "")));
    assert.equal(page.endLine, startLine + page.text.split("\n").length - 1);
    startLine = page.nextStartLine;
  }
  assert.deepEqual(actual, expected);
});

test("server output ceiling still applies and an oversized single line is explicit", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.root, "rows.txt"), "row\n".repeat(1_000));
  const result = await readTextFilePage({ ...f.config, maxReadBytes: 1_000 }, f.guard, f.workspace, "rows.txt", {
    maxBytes: 2_000_000
  });
  assert.ok(result.returnedBytes <= 1_000);
  assert.ok(result.nextStartLine > 1);
  await fs.writeFile(path.join(f.root, "one-line.txt"), "中".repeat(1_000));
  await assert.rejects(readTextFilePage(f.config, f.guard, f.workspace, "one-line.txt", {
    maxBytes: 1_000
  }), /第 1 行本身超过.*按键提取/);
});

test("small reads and internal read semantics remain intact", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.root, "small.txt"), "alpha\nbeta\n");
  const original = await readTextFile(f.config, f.guard, f.workspace, "small.txt");
  const paged = await readTextFilePage(f.config, f.guard, f.workspace, "small.txt");
  for (const key of Object.keys(original)) assert.deepEqual(paged[key], original[key]);
  assert.equal(paged.nextStartLine, null);
});

test("path, binary and source-size safety checks still reject disallowed files", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.root, ".env"), "PRIVATE=fixture");
  await assert.rejects(readTextFilePage(f.config, f.guard, f.workspace, ".env"), /blocked/);
  await assert.rejects(readTextFilePage(f.config, f.guard, f.workspace, "../outside.txt"), /escapes workspace/);
  await fs.writeFile(path.join(f.root, "binary.txt"), Buffer.from([65, 0, 66]));
  await assert.rejects(readTextFilePage(f.config, f.guard, f.workspace, "binary.txt"), /binary/);
  await fs.writeFile(path.join(f.root, "oversize.txt"), "x".repeat(2_000_001));
  await assert.rejects(readTextFilePage(f.config, f.guard, f.workspace, "oversize.txt", {
    startLine: 1, endLine: 1
  }), /Limit: 2000000 bytes/);
});

test("the MCP read tool returns a page and continuation without opening a port", async (t) => {
  const f = await fixture(t);
  const { createCodexProServer } = await load("dist/server.js");
  const { Client } = await load("node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js");
  const { InMemoryTransport } = await load("node_modules/@modelcontextprotocol/sdk/dist/esm/inMemory.js");
  await fs.writeFile(path.join(f.root, "mcp.txt"), "readable entry\n".repeat(20_000));
  const server = createCodexProServer(f.config);
  const client = new Client({ name: "paged-read-test", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  try {
    await server.connect(serverTransport);
    await client.connect(clientTransport);
    const result = await client.callTool({ name: "read", arguments: { path: "mcp.txt", max_bytes: 1_000 } });
    assert.ok(!result.isError);
    assert.ok(result.structuredContent.returnedBytes <= 1_000);
    assert.ok(result.structuredContent.nextStartLine > 1);
    assert.ok(result.content[0].text.includes(`start_line 设为 ${result.structuredContent.nextStartLine}`));
  } finally {
    await Promise.allSettled([client.close(), server.close()]);
  }
});
