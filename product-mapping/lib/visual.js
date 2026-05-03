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

function readJson(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

/**
 * 图片路径：data/imgs/{platformCode}.jpg（由 platformCode 直接推导，不需要索引）
 */
function imgPath(platformCode) {
  return path.join(IMG_DIR, platformCode + '.jpg');
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

/**
 * 记录识图判断结果
 * @param {string} platformCode
 * @param {'ok'|'mismatch'|'uncertain'} verdict
 * @param {string} notes - 我识别到的内容描述
 * @param {string} [matchDetail] - match.js 输出的比对结论
 */
function recordVerdict(platformCode, verdict, notes, matchDetail) {
  const verdicts = loadVerdicts();
  verdicts[platformCode] = {
    verdict,        // 'ok' | 'mismatch' | 'uncertain'
    notes,          // 我看到的内容，如"益生菌×6、冰霸杯×1、玉米片×10、吸管袋×1"
    matchDetail,    // match.js 输出，如"MATCH" 或 "MISMATCH: 缺少 保温壶×1"
    reviewTime: new Date().toISOString()
  };
  fs.writeFileSync(VERDICTS_FILE, JSON.stringify(verdicts, null, 2));
  return verdicts[platformCode];
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
      if (sku.status === '已匹配-待视觉核查' && !verdicts[sku.platformCode]) {
        pending.push({
          productCode: p.productCode,
          productName: p.productName,
          skuName: sku.skuName,
          platformCode: sku.platformCode,
          erpCode: sku.erpCode,
          erpName: sku.erpName,
          imgPath: imgPath(sku.platformCode)
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
      if (verdicts[sku.platformCode]) {
        sku.visualVerdict = verdicts[sku.platformCode].verdict;
        sku.visualNotes = verdicts[sku.platformCode].notes;
        sku.matchDetail = verdicts[sku.platformCode].matchDetail;
        // 更新 status
        if (sku.status === '已匹配-待视觉核查') {
          sku.status = verdicts[sku.platformCode].verdict === 'ok'
            ? '已匹配-视觉确认'
            : verdicts[sku.platformCode].verdict === 'mismatch'
              ? '已匹配-视觉不符'
              : '已匹配-无法判断';
        }
      }
    }
  }
  return report;
}

module.exports = { imgPath, downloadImg, loadVerdicts, recordVerdict, listPending, mergeVerdicts };
