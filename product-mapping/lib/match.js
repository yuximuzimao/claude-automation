'use strict';

/**
 * 从报告 SKU 生成期望项列表（精确字符串，用于与识图结果逐一比对）
 * - 单品（archiveType=0）：[archiveTitle×1]
 * - 组合装（archiveType=2）：[subItem.name×qty, ...]
 *
 * @param {object} sku - 报告中的 SKU 对象（含 archiveType, archiveTitle, subItems）
 * @returns {string[]} 期望项列表，格式 "商品名×数量"
 */
function buildExpected(sku) {
  if (sku.archiveType === '2' && sku.subItems && sku.subItems.length > 0) {
    return sku.subItems.map(i => `${i.name}×${i.qty}`);
  }
  if (sku.archiveTitle) {
    return [`${sku.archiveTitle}×1`];
  }
  return [];
}

/**
 * 精确比对：期望项 vs 识图结果项（字符串完全一致）
 * 识图结果文本格式：每个条目 "商品名×数量"，多个条目用逗号或换行分隔
 *
 * @param {string[]} expected - buildExpected 输出
 * @param {string[]} observed - 识图结果解析后的列表
 * @returns {{ match: boolean, detail: string, missing: string[], extra: string[] }}
 */
function compareExact(expected, observed) {
  const expSet = new Set(expected);
  const obsSet = new Set(observed);

  const missing = expected.filter(e => !obsSet.has(e));
  const extra = observed.filter(o => !expSet.has(o));
  const match = missing.length === 0 && extra.length === 0;

  const parts = [match ? 'MATCH' : 'MISMATCH'];
  if (missing.length) parts.push('缺少: ' + missing.join(', '));
  if (extra.length) parts.push('多余: ' + extra.join(', '));

  return { match, detail: parts.join(' | '), missing, extra };
}

/**
 * 解析识图结果文本为条目列表
 * 输入格式：每条 "商品名×数量"，用逗号/顿号/换行分隔
 *
 * @param {string} visionText
 * @returns {string[]}
 */
function parseVisionText(visionText) {
  return visionText
    .split(/[,，、\n]/)
    .map(s => s.trim())
    .filter(s => s.length > 0);
}

/**
 * 一站式比对：从报告 SKU + 识图文本 → 结论
 *
 * @param {object} sku - 报告 SKU 对象
 * @param {string} visionText - 识图结果，格式 "名称×数量,名称×数量"
 * @returns {{ match: boolean, detail: string, expected: string[], observed: string[] }}
 */
function matchSku(sku, visionText) {
  const expected = buildExpected(sku);
  const observed = parseVisionText(visionText);
  const result = compareExact(expected, observed);
  return { ...result, expected, observed };
}

module.exports = { buildExpected, parseVisionText, compareExact, matchSku };

