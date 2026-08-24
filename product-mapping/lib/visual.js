'use strict';
/**
 * WHAT: 视觉识别结论管理（visual-ok/visual-flag/visual-pending）
 * WHERE: check 流程 step ② 识图 → CLI → 此模块
 * WHY: 识图结论写入 sku-records.json，作为 match 流程的前置数据
 * ENTRY: cli.js: visual-ok / visual-flag / visual-pending 命令
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const IMG_DIR = path.join(__dirname, '../data/imgs');
const VERDICTS_FILE = path.join(__dirname, '../data/visual-verdicts.json');
const SKU_RECORDS_FILE = path.join(__dirname, '../data/sku-records.json');
const { recordKey, imageFileName } = require('./sku-identity');

function recognitionType(items) {
  const totalQty = items.reduce((sum, item) => sum + Number(item.qty || 0), 0);
  return totalQty === 1 ? '单品' : '组合装';
}

/**
 * 将 notes 文本（"商品A×N；商品B×M"）解析为 recognition 结构
 * 单品：所有 items 数量合计为 1；组合装：数量合计大于 1
 */
function parseNotesToRecognition(notes) {
  if (!notes || !notes.trim()) return null;
  // ERP 标准商品名经常包含空格，项目之间只用明确分隔符或换行切项。
  const parts = notes.split(/[、,，;；\n]+/).map(s => s.trim()).filter(Boolean);
  const items = [];
  for (const p of parts) {
    // 匹配"商品名×数量"，×可以是全角或半角。
    const m = p.match(/^(.+?)[×xX]\s*(\d+)$/);
    if (m) {
      items.push({ name: m[1].trim(), qty: parseInt(m[2], 10) });
    } else if (p) {
      // 没有数量的视为×1
      items.push({ name: p, qty: 1 });
    }
  }
  if (!items.length) return null;
  return {
    type: recognitionType(items),
    items,
    raw: notes,
  };
}


function readJson(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

/**
 * 图片路径：data/imgs/{productCode}__{platformCode}.jpg（由商品链接身份直接推导）
 */
function imgPath(productCode, platformCode) {
  return path.join(IMG_DIR, imageFileName(productCode, platformCode));
}

/**
 * 下载图片到本地（curl）
 * @param {string} url
 * @param {string} destPath
 */
function downloadImg(url, destPath) {
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  execSync(`curl -sf "${url}" -o "${destPath}"`, { timeout: 30000 });
  return destPath;
}

/**
 * 读取已保存的识图判断结果
 * @returns {Object} platformCode → verdict
 */
function loadVerdicts() {
  return readJson(VERDICTS_FILE, {});
}

function selectVerdictRecords(records, platformCode, productCode = null) {
  const matches = Object.values(records).filter(record =>
    record &&
    record.platformCode === platformCode &&
    (!productCode || record.productCode === productCode)
  );
  if (!productCode && matches.length > 1) {
    const productCodes = [...new Set(matches.map(record => record.productCode).filter(Boolean))];
    throw new Error(
      `平台编码 ${platformCode} 对应多个商品链接（${productCodes.join('、')}），请指定 productCode`
    );
  }
  if (productCode && matches.length === 0) {
    throw new Error(`未找到商品链接记录: ${recordKey(productCode, platformCode)}`);
  }
  if (!productCode && matches.length === 0) {
    throw new Error(`未找到平台编码记录: ${platformCode}`);
  }
  return matches;
}

/**
 * 记录识图判断结果
 * @param {string} platformCode
 * @param {'ok'|'mismatch'|'uncertain'} verdict
 * @param {string} notes - 我识别到的内容描述
 * @param {string} [matchDetail] - match.js 输出的比对结论
 */
function recordVerdict(platformCode, verdict, notes, matchDetail, productCode = null) {
  const verdicts = loadVerdicts();
  const value = {
    verdict,
    notes,
    matchDetail,
    reviewTime: new Date().toISOString()
  };

  if (fs.existsSync(SKU_RECORDS_FILE)) {
    const records = JSON.parse(fs.readFileSync(SKU_RECORDS_FILE, 'utf8'));
    const matches = selectVerdictRecords(records, platformCode, productCode);
    for (const record of matches) {
      verdicts[recordKey(record.productCode, record.platformCode)] = value;
      record.recognition = parseNotesToRecognition(notes);
    }
    fs.writeFileSync(SKU_RECORDS_FILE, JSON.stringify(records, null, 2));
  } else if (productCode) {
    verdicts[recordKey(productCode, platformCode)] = value;
  } else {
    verdicts[platformCode] = value;
  }
  fs.writeFileSync(VERDICTS_FILE, JSON.stringify(verdicts, null, 2));

  return value;
}

/**
 * 结构化写入单个商品链接的识图结果。
 *
 * WHY: ERP 标准商品名经常包含空格，不能经过 notes 文本分词；同时重复
 * platformCode 的活动链接必须按 productCode + platformCode 独立保存。
 *
 * @param {string} productCode
 * @param {string} platformCode
 * @param {Array<{name:string,qty:number}>} items
 * @param {'ok'|'mismatch'|'uncertain'} [verdict]
 * @param {string} [matchDetail]
 */
function recordRecognition(productCode, platformCode, items, verdict = 'ok', matchDetail = '') {
  if (!productCode || !platformCode) {
    throw new Error('recordRecognition 需要 productCode 和 platformCode');
  }
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error(`recordRecognition ${productCode}::${platformCode} 缺少识图明细`);
  }

  const normalizedItems = items.map((item, index) => {
    const name = typeof item?.name === 'string' ? item.name.trim() : '';
    const qty = Number(item?.qty);
    if (!name || !Number.isInteger(qty) || qty <= 0) {
      throw new Error(`recordRecognition ${productCode}::${platformCode} 第 ${index + 1} 项无效`);
    }
    return { name, qty };
  });
  const notes = normalizedItems.map(item => `${item.name}×${item.qty}`).join('；');
  const recognition = {
    type: recognitionType(normalizedItems),
    items: normalizedItems,
    raw: notes,
  };
  const value = {
    verdict,
    notes,
    matchDetail,
    reviewTime: new Date().toISOString(),
  };
  const key = recordKey(productCode, platformCode);
  const records = readJson(SKU_RECORDS_FILE, {});
  const record = records[key] || Object.values(records).find(candidate =>
    candidate?.productCode === productCode && candidate?.platformCode === platformCode
  );
  if (!record) {
    throw new Error(`未找到商品链接记录: ${key}`);
  }

  record.recognition = recognition;
  records[key] = record;
  fs.writeFileSync(SKU_RECORDS_FILE, JSON.stringify(records, null, 2));

  const verdicts = loadVerdicts();
  verdicts[key] = value;
  fs.writeFileSync(VERDICTS_FILE, JSON.stringify(verdicts, null, 2));
  return { ...value, recognition };
}

/**
 * 从核查报告中提取待视觉核查项
 * @param {object} report - runCheck 返回的报告对象
 * @returns {Array<{productCode, productName, skuName, platformCode, erpCode, erpName, imgPath}>}
 */
function listPending(report) {
  const verdicts = loadVerdicts();
  const pending = [];
  for (const p of report.products) {
    for (const sku of p.skus) {
      const key = recordKey(p.productCode, sku.platformCode);
      if (sku.status === '已匹配-待视觉核查' && !verdicts[key] && !verdicts[sku.platformCode]) {
        pending.push({
          productCode: p.productCode,
          productName: p.productName,
          skuName: sku.skuName,
          platformCode: sku.platformCode,
          erpCode: sku.erpCode,
          erpName: sku.erpName,
          imgPath: imgPath(p.productCode, sku.platformCode)
        });
      }
    }
  }
  return pending;
}

/**
 * 将识图判断合并回报告，更新各 SKU 的 visualVerdict 字段
 * @param {object} report
 * @returns {object} 更新后的报告
 */
function mergeVerdicts(report) {
  const verdicts = loadVerdicts();
  for (const p of report.products) {
    for (const sku of p.skus) {
      const saved = verdicts[recordKey(p.productCode, sku.platformCode)] || verdicts[sku.platformCode];
      if (saved) {
        sku.visualVerdict = saved.verdict;
        sku.visualNotes = saved.notes;
        sku.matchDetail = saved.matchDetail;
        // 更新 status
        if (sku.status === '已匹配-待视觉核查') {
          sku.status = saved.verdict === 'ok'
            ? '已匹配-视觉确认'
            : saved.verdict === 'mismatch'
              ? '已匹配-视觉不符'
              : '已匹配-无法判断';
        }
      }
    }
  }
  return report;
}

module.exports = {
  imgPath,
  downloadImg,
  loadVerdicts,
  recordVerdict,
  recordRecognition,
  parseNotesToRecognition,
  selectVerdictRecords,
  listPending,
  mergeVerdicts,
  recognitionType,
};
