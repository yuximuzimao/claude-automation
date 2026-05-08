'use strict';
/**
 * 第一步：下载平台商品
 * 封装 correspondence.js 的 downloadPlatformProducts，负责导航+下载
 * 防双下：同一店铺 8h 内已由 check（readAllCorrespondence）下载过则跳过
 */
const fs = require('fs');
const path = require('path');
const { ensureCorrPage } = require('./ensure-corr-page');
const { downloadPlatformProducts } = require('../correspondence');

const DOWNLOAD_MARKER_FILE = path.join(__dirname, '../../data/.download-marker.json');
const DOWNLOAD_TTL_MS = 8 * 60 * 60 * 1000; // 8 小时

/**
 * @param {string} erpId
 * @param {string} shopName
 * @returns {Promise<{ok: true, skipped?: true}>}
 */
async function downloadProducts(erpId, shopName) {
  // 防双下：check 已下载则跳过（8h TTL）
  try {
    const marker = JSON.parse(fs.readFileSync(DOWNLOAD_MARKER_FILE, 'utf8'));
    const elapsed = Date.now() - new Date(marker.downloadedAt).getTime();
    if (marker.shopName === shopName && elapsed < DOWNLOAD_TTL_MS) {
      const mins = Math.round(elapsed / 60000);
      console.error(`[download] ⏩ 已跳过（${shopName} ${mins} 分钟前已下载，TTL 8h）`);
      return { ok: true, skipped: true };
    }
  } catch {}

  await ensureCorrPage(erpId);
  await downloadPlatformProducts(erpId, shopName);
  return { ok: true };
}

module.exports = { downloadProducts };
