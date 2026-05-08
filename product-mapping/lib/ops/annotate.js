'use strict';
/**
 * 第四步：标注类型（纯数据，无浏览器操作）
 *
 * 读 sku-records.json（stage=images_done）
 * 如有 data/products/{brand}/accessories.json，在标注前注入不可见配件（礼盒/礼袋/雪梨纸等）
 * 按 recognition.items 的 qty 之和判断 itemType
 * 写回 sku-records.json（stage=annotated）
 */
const path = require('path');
const fs = require('fs');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');
const PRODUCTS_DIR = path.join(__dirname, '../../data/products');

/**
 * @returns {Promise<{ok: true, data: {singles, suites, injected}}>}
 */
async function annotate() {
  const record = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));

  if (record.stage !== 'images_done') {
    throw new Error(`annotate: stage=${record.stage}，要求 images_done`);
  }

  // 加载品牌配件规则（如有）
  const brand = record.brand || 'kgos';
  const accFile = path.join(PRODUCTS_DIR, brand, 'accessories.json');
  let accRules = null;
  if (fs.existsSync(accFile)) {
    const acc = JSON.parse(fs.readFileSync(accFile, 'utf8'));
    accRules = acc.rules || null;
    if (accRules) {
      // 过滤掉示例条目（以 _ 开头的键）
      Object.keys(accRules).forEach(k => { if (k.startsWith('_')) delete accRules[k]; });
    }
    console.error(`[annotate] 已加载 ${brand} 配件规则（${Object.keys(accRules || {}).length} 条货号规则）`);
  }

  let singles = 0;
  let suites = 0;
  let injected = 0;

  for (const [platformCode, sku] of Object.entries(record.skus)) {
    if (!sku.recognition) {
      if (sku.matchStatus === 'matched-original') {
        console.error(`[annotate] ${platformCode} 已是 matched-original，recognition 为空，跳过`);
        continue;
      }
      throw new Error(`annotate: ${platformCode} 的 recognition 为 null，请先完成识图步骤`);
    }

    // 注入不可见配件（accessories overlay）
    if (accRules && sku.productCode && accRules[sku.productCode]) {
      const rule = accRules[sku.productCode];
      const existing = new Set(sku.recognition.items.map(i => i.name));
      const toInject = rule.accessories.filter(acc => !existing.has(acc.erpName));
      for (const acc of toInject) {
        sku.recognition.items.push({ name: acc.erpName, qty: acc.qty });
      }
      if (toInject.length > 0) {
        injected++;
        const note = rule.note ? `（${rule.note}）` : '';
        console.error(`[annotate] ${platformCode}${note}：注入配件 ${toInject.map(a => `${a.erpName}×${a.qty}`).join('，')}`);
      } else {
        console.error(`[annotate] ${platformCode}：配件已注入，跳过（幂等）`);
      }
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

  const injectedMsg = injected > 0 ? `，配件注入 ${injected} 个 SKU` : '';
  console.error(`[annotate] 完成：单品 ${singles} 个，套件 ${suites} 个${injectedMsg}`);
  return { ok: true, data: { singles, suites, injected } };
}

module.exports = { annotate };
