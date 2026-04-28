'use strict';
/**
 * 第四步：标注类型（纯数据，无浏览器操作）
 *
 * 读 sku-records.json（stage=images_done）
 * 按 recognition.items 的 qty 之和判断 itemType
 * 写回 sku-records.json（stage=annotated）
 */
const path = require('path');
const fs = require('fs');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * @returns {Promise<{ok: true, data: {singles, suites}}>}
 */
async function annotate() {
  const record = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));

  if (record.stage !== 'images_done') {
    throw new Error(`annotate: stage=${record.stage}，要求 images_done`);
  }

  let singles = 0;
  let suites = 0;

  for (const [platformCode, sku] of Object.entries(record.skus)) {
    if (!sku.recognition) {
      throw new Error(`annotate: ${platformCode} 的 recognition 为 null，请先完成识图步骤`);
    }
    const items = sku.recognition.items || [];
    const totalQty = items.reduce((sum, item) => sum + (item.qty || 0), 0);

    if (totalQty === 0) {
      throw new Error(`annotate: ${platformCode} 的 recognition.items 总数量为 0，识图结论有误`);
    }

    sku.itemType = totalQty === 1 ? 'single' : 'suite';
    if (totalQty === 1) singles++;
    else suites++;
  }

  record.stage = 'annotated';
  safeWriteJson(SKU_RECORDS_PATH, record);

  console.error(`[annotate] 完成：单品 ${singles} 个，套件 ${suites} 个`);
  return { ok: true, data: { singles, suites } };
}

module.exports = { annotate };
