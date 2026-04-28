'use strict';
/**
 * 分支 A：单品换绑（matchStatus=unmatched, itemType=single）
 *
 * 幂等：已有正确 erpCode（matched-original 或 matched-ai）→ 跳过
 * 成功后立即更新 matchStatus=matched-ai（让 while 循环不重复处理）
 */
const path = require('path');
const fs = require('fs');
const { ensureCorrPage } = require('./ensure-corr-page');
const { remapSku } = require('../remap-sku');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * @param {string} erpId
 * @param {object} sku - sku-records.json 中的单个 SKU 对象
 * @returns {Promise<{ok: true, skipped?: true}>}
 */
async function remapSingle(erpId, sku) {
  const { platformCode, erpCode, matchStatus, recognition } = sku;

  // 幂等检查：基于结果判断，不基于字段存在
  if (erpCode && (matchStatus === 'matched-original' || matchStatus === 'matched-ai')) {
    console.error(`[remap-single] ${platformCode} 已匹配（${matchStatus}），跳过`);
    return { ok: true, skipped: true };
  }

  if (!recognition || !recognition.items || !recognition.items.length) {
    throw new Error(`remap-single: ${platformCode} recognition 为空，请先完成识图`);
  }
  const erpName = recognition.items[0].name;

  console.error(`[remap-single] ${platformCode} → ${erpName}`);

  // 确保在对应表页面（快速 hash 检查，不做 full reload）
  await ensureCorrPage(erpId);

  // 调用 remapSku（skipNav=true：页面已就绪，跳过内部 navigateErp）
  const result = await remapSku(erpId, platformCode, erpName, {
    confirm: true,
    itemType: '普通商品',
    skipNav: true,
  });

  if (!result.ok) throw new Error(`remapSku 失败: ${result.message || JSON.stringify(result)}`);

  // 立即写回 sku-records.json（乐观标记，让 while 循环不重复处理；readErpCodes 会最终验证）
  const freshRecord = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const skuToUpdate = freshRecord.skus[platformCode];
  if (skuToUpdate) {
    skuToUpdate.matchStatus = 'matched-ai';
    if (result.erpCode) skuToUpdate.erpCode = result.erpCode;
  }
  safeWriteJson(SKU_RECORDS_PATH, freshRecord);

  console.error(`[remap-single] ${platformCode} 换绑成功 → ${result.erpCode}`);
  return { ok: true };
}

module.exports = { remapSingle };
