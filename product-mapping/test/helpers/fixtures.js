'use strict';
// 测试数据工厂 + 备份/恢复 + 状态校验

const fs = require('fs');
const path = require('path');
const { safeWriteJson } = require('../../lib/utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');
const BACKUP_PATH = path.join(__dirname, '../fixtures/_sku-records-backup.json');

/**
 * 创建单个 SKU 记录对象
 */
function makeSkuRecord(overrides = {}) {
  return {
    platformCode: '000001',
    skuName: '测试商品*1盒',
    productCode: 'test-product',
    shopName: '测试店铺',
    imgUrl: '',
    erpCode: '',
    erpName: '',
    recognition: null,
    itemType: null,
    matchStatus: 'unmatched',
    archiveType: null,
    archiveTitle: null,
    subItems: null,
    comparisonResult: null,
    comparisonDetail: null,
    ...overrides,
  };
}

/**
 * 创建完整的 sku-records.json fixture
 */
function makeSkuRecordsJson({ stage, shopName, productCode, skus }) {
  return {
    stage,
    shopName,
    productCode,
    skus,
  };
}

/**
 * 创建 annotated 阶段的 fixture（用于 annotate 测试后的 match 测试）
 */
function makeAnnotatedFixture(skuEntries) {
  const skus = {};
  for (const entry of skuEntries) {
    skus[entry.platformCode] = makeSkuRecord(entry);
  }
  return makeSkuRecordsJson({
    stage: 'annotated',
    shopName: '测试店铺',
    productCode: 'test-product',
    skus,
  });
}

/**
 * 写入 fixture 到 sku-records.json（测试用）
 */
function writeFixture(data) {
  safeWriteJson(SKU_RECORDS_PATH, data);
}

/**
 * 备份当前 sku-records.json
 */
function backupSkuRecords() {
  try {
    const data = fs.readFileSync(SKU_RECORDS_PATH, 'utf8');
    fs.writeFileSync(BACKUP_PATH, data);
  } catch (e) {
    // 文件不存在时忽略
    if (e.code !== 'ENOENT') throw e;
  }
}

/**
 * 恢复 sku-records.json 从备份
 */
function restoreSkuRecords() {
  try {
    const data = fs.readFileSync(BACKUP_PATH, 'utf8');
    fs.writeFileSync(SKU_RECORDS_PATH, data);
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
}

/**
 * 读取当前 sku-records.json
 */
function readSkuRecords() {
  try {
    return JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * 校验 ERP 当前状态是否符合预期（fail-fast）
 * 用于写操作测试前，确保数据没有被之前的测试污染
 */
function assertErpState(productCode, expectedMatchStatuses) {
  const data = readSkuRecords();
  if (!data) throw new Error('sku-records.json 不存在，无法校验 ERP 状态');
  if (data.productCode !== productCode) {
    throw new Error(`ERP 状态不一致: 期望 productCode=${productCode}，实际=${data.productCode}`);
  }

  for (const [platformCode, expectedStatus] of Object.entries(expectedMatchStatuses)) {
    const sku = data.skus && data.skus[platformCode];
    if (!sku) {
      throw new Error(`ERP 状态不一致: SKU ${platformCode} 不存在`);
    }
    if (sku.matchStatus !== expectedStatus) {
      throw new Error(`ERP 状态不一致: SKU ${platformCode} 期望 matchStatus=${expectedStatus}，实际=${sku.matchStatus}，请手动恢复后重试`);
    }
  }
}

module.exports = {
  makeSkuRecord,
  makeSkuRecordsJson,
  makeAnnotatedFixture,
  writeFixture,
  backupSkuRecords,
  restoreSkuRecords,
  readSkuRecords,
  assertErpState,
  SKU_RECORDS_PATH,
};
