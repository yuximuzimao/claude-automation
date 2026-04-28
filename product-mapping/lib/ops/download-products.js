'use strict';
/**
 * 第一步：下载平台商品
 * 封装 correspondence.js 的 downloadPlatformProducts，负责导航+下载
 */
const { ensureCorrPage } = require('./ensure-corr-page');
const { downloadPlatformProducts } = require('../correspondence');

/**
 * @param {string} erpId
 * @param {string} shopName
 * @returns {Promise<{ok: true}>}
 */
async function downloadProducts(erpId, shopName) {
  await ensureCorrPage(erpId);
  await downloadPlatformProducts(erpId, shopName);
  return { ok: true };
}

module.exports = { downloadProducts };
