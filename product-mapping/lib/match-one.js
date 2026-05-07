'use strict';
/**
 * 单货号编排器：7 步闭环，支持 --from 断点执行
 *
 * 步骤：download → read_skus → recognize（暂停）→ annotate → match → read_erp → verify
 *
 * 识图步骤（recognize）由 Claude 在对话中手动执行，脚本到此暂停并返回待识图列表。
 * 完成识图后，调用 --from annotate 继续后续步骤。
 */
const path = require('path');
const fs = require('fs');
const { downloadProducts } = require('./ops/download-products');
const { readSkus } = require('./ops/read-skus');
const { annotate } = require('./ops/annotate');
const { remapSingle } = require('./ops/remap-single');
const { createSuite } = require('./ops/create-suite');
const { readErpCodes } = require('./ops/read-erp-codes');
const { verifyArchive } = require('./ops/verify-archive');
const { safeWriteJson } = require('./utils/safe-write');
const { releaseErpLock } = require('./erp-lock');

const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');

const STEPS = ['download', 'read_skus', 'recognize', 'annotate', 'match', 'read_erp', 'verify'];

// stage 状态机：每步要求的前置 stage（最低要求，--from 时用 >= 比较）
const REQUIRED_STAGE = {
  download: null,
  read_skus: null,
  recognize: 'skus_read',
  annotate: 'images_done',
  match: 'annotated',
  read_erp: 'matched',
  verify: 'matched',
};

// stage 顺序（用于 >= 比较）
const STAGE_ORDER = ['skus_read', 'images_done', 'annotated', 'matched', 'verified'];

function stageAtLeast(current, required) {
  if (!required) return true;
  return STAGE_ORDER.indexOf(current) >= STAGE_ORDER.indexOf(required);
}

/**
 * @param {string} erpId
 * @param {string} jlId    - 鲸灵 targetId（暂未使用，预留）
 * @param {string} shopName
 * @param {string} productCode
 * @param {{ from?: string, brand?: string }} opts
 */
async function matchOne(erpId, jlId, shopName, productCode, opts = {}) {
  try {
  const { from, brand = 'kgos' } = opts;

  // --from 非法值校验
  if (from && !STEPS.includes(from)) {
    throw new Error(`非法步骤: ${from}，合法值: ${STEPS.join(', ')}`);
  }

  const startIdx = from ? STEPS.indexOf(from) : 0;

  // --from 时：校验当前 stage >= 前置要求（stage 只从文件读）
  if (from) {
    const required = REQUIRED_STAGE[from];
    if (required !== null) {
      if (!fs.existsSync(SKU_RECORDS_PATH)) {
        throw new Error(`--from ${from} 要求 stage>=${required}，但 sku-records.json 不存在`);
      }
      const data = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
      if (!stageAtLeast(data.stage, required)) {
        throw new Error(`--from ${from} 要求 stage>=${required}，当前 stage=${data.stage}`);
      }
      if (data.productCode !== productCode) {
        throw new Error(`sku-records.json 货号=${data.productCode}，与指定货号=${productCode} 不一致`);
      }
    }
  }

  // 步骤 0：下载平台商品
  if (startIdx <= 0) {
    console.error(`[match-one] ── 步骤1/7：下载平台商品 ──`);
    await downloadProducts(erpId, shopName);
  }

  // 步骤 1：读取 SKU 列表
  if (startIdx <= 1) {
    console.error(`[match-one] ── 步骤2/7：读取 SKU 列表 ──`);
    const r = await readSkus(erpId, shopName, productCode, { brand });
    console.error(`[match-one] SKU 数: ${r.data.skuCount}`);
  }

  // 步骤 2：识图（暂停，由 Claude 手动执行）
  if (startIdx <= 2) {
    const data = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
    const pendingSkus = Object.values(data.skus).map(s => ({
      platformCode: s.platformCode,
      skuName: s.skuName,
      imgUrl: s.imgUrl,
    }));
    console.error(`[match-one] ── 步骤3/7：识图（暂停）──`);
    console.error(`[match-one] 请对以下 ${pendingSkus.length} 个 SKU 完成识图，写入 recognition 字段后，更新 stage=images_done`);
    pendingSkus.forEach((s, i) => {
      console.error(`  [${i + 1}] ${s.platformCode} ${s.skuName}`);
      console.error(`       imgUrl: ${s.imgUrl || '（无图片）'}`);
    });
    return { pause: 'recognize', pendingSkus };
  }

  // 步骤 3：标注类型
  if (startIdx <= 3) {
    console.error(`[match-one] ── 步骤4/7：标注类型 ──`);
    const r = await annotate();
    console.error(`[match-one] 单品 ${r.data.singles} 个，套件 ${r.data.suites} 个`);
  }

  // 步骤 4：匹配（每处理一个 SKU 后重新读文件）
  if (startIdx <= 4) {
    console.error(`[match-one] ── 步骤5/7：执行匹配 ──`);

    // 先将 stage 置为 matched（匹配步骤开始标记）
    {
      const data = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
      data.stage = 'matched';
      safeWriteJson(SKU_RECORDS_PATH, data);
    }

    while (true) {
      // 每次循环重新从文件读，不依赖内存快照
      const data = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
      const next = Object.values(data.skus).find(
        s => s.matchStatus === 'unmatched' && s.itemType
      );
      if (!next) break;

      console.error(`[match-one] 处理 ${next.platformCode}（${next.itemType}）`);
      if (next.itemType === 'single') {
        await remapSingle(erpId, next);
      } else {
        await createSuite(erpId, next);
      }
    }
  }

  // 步骤 5：重读验证 ERP 编码
  if (startIdx <= 5) {
    console.error(`[match-one] ── 步骤6/7：重读验证 ERP 编码 ──`);
    const r = await readErpCodes(erpId, shopName, productCode);
    if (r.data.failed > 0) {
      throw new Error(`[match-one] ${r.data.failed} 个 SKU 匹配失败（failed-ai），需人工处理`);
    }
    console.error(`[match-one] 验证通过：matched-ai ${r.data.matched} 个`);
  }

  // 步骤 6：档案核查
  if (startIdx <= 6) {
    console.error(`[match-one] ── 步骤7/7：档案核查 ──`);
    const r = await verifyArchive(erpId, shopName, productCode);
    console.error(`[match-one] 核查完成：match=${r.data.match}, mismatch=${r.data.mismatch}`);
    return { done: true, summary: r.data };
  }

  return { done: true };
  } finally {
    await releaseErpLock();
  }
}

module.exports = { matchOne, STEPS };
