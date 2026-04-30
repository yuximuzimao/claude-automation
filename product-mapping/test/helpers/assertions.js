'use strict';
// 断言工具：文件级 + 数据级 + 日志级

const fs = require('fs');
const assert = require('assert');

/**
 * 断言文件存在且为有效 JSON
 */
function assertFileJson(filePath, validator) {
  assert.ok(fs.existsSync(filePath), `文件不存在: ${filePath}`);
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  if (validator) validator(data);
  return data;
}

/**
 * 断言 sku-records.json 的 stage 字段
 */
function assertStage(filePath, expected) {
  const data = assertFileJson(filePath);
  assert.strictEqual(data.stage, expected, `stage 期望 "${expected}"，实际 "${data.stage}"`);
}

/**
 * 断言单个 SKU 的 matchStatus
 */
function assertMatchStatus(filePath, platformCode, expected) {
  const data = assertFileJson(filePath);
  const sku = data.skus && data.skus[platformCode];
  assert.ok(sku, `SKU ${platformCode} 不存在`);
  assert.strictEqual(sku.matchStatus, expected, `SKU ${platformCode} matchStatus 期望 "${expected}"，实际 "${sku.matchStatus}"`);
}

/**
 * 断言无残留 .tmp 文件
 */
function assertNoTmpFiles(dir) {
  const files = fs.readdirSync(dir);
  const tmpFiles = files.filter(f => f.endsWith('.tmp'));
  assert.strictEqual(tmpFiles.length, 0, `发现残留 .tmp 文件: ${tmpFiles.join(', ')}`);
}

/**
 * 断言日志包含指定模块和标识
 */
function assertLogContains(logs, module, identifier) {
  const found = logs.some(log =>
    log.includes(`[${module}]`) && log.includes(identifier)
  );
  assert.ok(found, `日志中未找到 [${module}] 包含 "${identifier}"，实际日志: ${logs.join('\n')}`);
}

/**
 * 断言返回值格式 { ok: true, ... }
 */
function assertOk(result) {
  assert.strictEqual(result.ok, true, `期望 {ok: true}，实际 ${JSON.stringify(result)}`);
}

/**
 * 断言返回值格式 { ok: true, skipped: true }
 */
function assertSkipped(result) {
  assert.strictEqual(result.ok, true);
  assert.strictEqual(result.skipped, true, `期望 {ok: true, skipped: true}，实际 ${JSON.stringify(result)}`);
}

/**
 * 断言函数抛出指定错误
 */
async function assertThrows(fn, messageMatch) {
  try {
    await fn();
    assert.fail('期望抛出错误但未抛出');
  } catch (e) {
    if (messageMatch) {
      assert.ok(
        e.message.includes(messageMatch),
        `错误消息期望包含 "${messageMatch}"，实际: "${e.message}"`
      );
    }
  }
}

module.exports = {
  assertFileJson,
  assertStage,
  assertMatchStatus,
  assertNoTmpFiles,
  assertLogContains,
  assertOk,
  assertSkipped,
  assertThrows,
};
