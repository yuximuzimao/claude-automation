'use strict';
/**
 * 第七步：档案核查 + 识图对比报告
 *
 * 对有 erpCode 的每个 SKU：查档案V2 → 对比识图结论
 * 写回 sku-records.json（stage=verified）
 */
const path = require('path');
const fs = require('fs');
const { initArchiveComp, queryArchive, querySubItems } = require('../archive');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * 集合等价比较：[{name, qty}] 两个数组是否完全一致（名称+数量）
 */
function itemSetsEqual(a, b) {
  const toKey = arr => arr.map(i => `${i.name}×${i.qty}`).sort().join('|');
  return toKey(a) === toKey(b);
}

/**
 * @param {string} erpId
 * @param {string} shopName
 * @param {string} productCode
 * @returns {Promise<{ok: true, data: {match, mismatch, details}}>}
 */
async function verifyArchive(erpId, shopName, productCode) {
  // stage 只从文件读（matched 或 verified 均可，支持重跑）
  const record = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const VALID_STAGES = ['matched', 'verified'];
  if (!VALID_STAGES.includes(record.stage)) {
    throw new Error(`verify-archive: stage=${record.stage}，要求 matched 或 verified`);
  }

  await initArchiveComp(erpId);

  let matchCount = 0;
  let mismatchCount = 0;
  const details = [];

  for (const [platformCode, sku] of Object.entries(record.skus)) {
    if (!sku.erpCode) {
      console.error(`[verify-archive] ${platformCode} 无 erpCode，跳过`);
      continue;
    }

    console.error(`[verify-archive] 查询 ${platformCode} → ${sku.erpCode}`);

    // 每次都从文件读 stage（不用内存），queryArchive 时页面状态可能变
    const archiveItem = await queryArchive(erpId, sku.erpCode);
    if (!archiveItem) {
      sku.archiveType = null;
      sku.archiveTitle = null;
      sku.comparisonResult = 'mismatch';
      sku.comparisonDetail = `档案V2中未找到 erpCode=${sku.erpCode}`;
      mismatchCount++;
      details.push({ platformCode, result: 'mismatch', detail: sku.comparisonDetail });
      continue;
    }

    sku.archiveType = String(archiveItem.type);
    sku.archiveTitle = archiveItem.title;

    const recognition = sku.recognition;
    if (!recognition) {
      sku.comparisonResult = 'mismatch';
      sku.comparisonDetail = 'recognition 为空，无法对比';
      mismatchCount++;
      details.push({ platformCode, result: 'mismatch', detail: sku.comparisonDetail });
      continue;
    }

    let compResult;
    let compDetail;

    if (sku.itemType === 'single') {
      // 单品：识图名称 vs 档案标题
      const recName = recognition.items[0] ? recognition.items[0].name : '';
      if (recName === archiveItem.title) {
        compResult = 'match';
        compDetail = `识图: ${recName} = 档案: ${archiveItem.title}`;
      } else {
        compResult = 'mismatch';
        compDetail = `识图: ${recName} ≠ 档案: ${archiveItem.title}`;
      }
    } else {
      // 套件：集合等价比较
      if (!archiveItem.subItemNum) {
        compResult = 'mismatch';
        compDetail = `档案类型非组合装（type=${archiveItem.type}）或子品数量为 0`;
      } else {
        const subItems = await querySubItems(erpId, archiveItem.subItemNum);
        const archiveItems = subItems.map(s => ({ name: s.name, qty: s.qty }));
        if (itemSetsEqual(recognition.items, archiveItems)) {
          compResult = 'match';
          compDetail = `子品集合一致（${recognition.items.length} 种）`;
        } else {
          compResult = 'mismatch';
          const expStr = recognition.items.map(i => `${i.name}×${i.qty}`).sort().join(', ');
          const actStr = archiveItems.map(i => `${i.name}×${i.qty}`).sort().join(', ');
          compDetail = `识图: [${expStr}] ≠ 档案: [${actStr}]`;
        }
      }
      sku.subItems = await querySubItems(erpId, archiveItem.subItemNum || 0).catch(() => []);
    }

    sku.comparisonResult = compResult;
    sku.comparisonDetail = compDetail;
    if (compResult === 'match') matchCount++;
    else mismatchCount++;

    details.push({ platformCode, result: compResult, detail: compDetail });
    console.error(`[verify-archive] ${platformCode}: ${compResult} — ${compDetail}`);
  }

  record.stage = 'verified';
  safeWriteJson(SKU_RECORDS_PATH, record);

  const summary = { productCode, shopName, match: matchCount, mismatch: mismatchCount, details };
  console.error(`[verify-archive] 完成：match=${matchCount}, mismatch=${mismatchCount}`);
  return { ok: true, data: summary };
}

module.exports = { verifyArchive };
