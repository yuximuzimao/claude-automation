'use strict';
/**
 * 供应商 ID 验证
 * 确保加购表格中所有数据属于目标店铺（供应商ID一致）
 * 任何一行不匹配即抛出错误，要求人工处理
 */

const fs   = require('fs');
const path = require('path');

const CART_ADDS_FILE = path.join(__dirname, '../data/cart-adds.json');

/**
 * 验证 cart-adds.json 中所有 SKU 的供应商ID是否与期望值一致
 * @param {string|number} expectedSupplierId - 期望的供应商ID（如 42528）
 * @throws 如果任何一行供应商ID不匹配或缺失
 */
function validateSupplier(expectedSupplierId) {
  const expected = String(expectedSupplierId).trim();

  if (!fs.existsSync(CART_ADDS_FILE)) {
    throw new Error('cart-adds.json 不存在，请先执行 parse 命令');
  }

  const cartData = JSON.parse(fs.readFileSync(CART_ADDS_FILE, 'utf-8'));
  const skus = cartData.skus || [];

  if (skus.length === 0) {
    throw new Error('cart-adds.json 中没有 SKU 数据');
  }

  const mismatches = [];
  const missing = [];

  for (const sku of skus) {
    if (!sku.supplierId) {
      missing.push(sku.key);
    } else if (String(sku.supplierId).trim() !== expected) {
      mismatches.push({ key: sku.key, supplierId: sku.supplierId });
    }
  }

  if (missing.length > 0) {
    throw new Error(
      `以下 ${missing.length} 个 SKU 缺少供应商ID（请检查 Excel 是否包含「供应商id」列）:\n` +
      missing.slice(0, 10).join('\n') +
      (missing.length > 10 ? `\n...共 ${missing.length} 条` : '')
    );
  }

  if (mismatches.length > 0) {
    const lines = mismatches.slice(0, 10).map(m => `  ${m.key}  →  供应商ID: ${m.supplierId}`).join('\n');
    throw new Error(
      `供应商ID 不匹配！期望: ${expected}，以下 ${mismatches.length} 个 SKU 数据来自其他店铺，请人工处理:\n` +
      lines +
      (mismatches.length > 10 ? `\n  ...共 ${mismatches.length} 条` : '')
    );
  }

  console.log(`✓ 供应商ID 验证通过: 全部 ${skus.length} 个 SKU 均属于供应商 ${expected}`);
}

module.exports = { validateSupplier };
