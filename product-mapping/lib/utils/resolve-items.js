'use strict';
/**
 * 临时合并识图结果 + 不可见配件
 *
 * 用途：match 时构建 ERP 子品列表、check 时比对识图 vs 档案明细
 * 关键设计：不修改原始 recognition，返回新数组
 *
 * @param {string} platformCode
 * @param {Array<{name:string,qty:number}>} recognitionItems  — 来自 recognition.items
 * @param {string} brand  — 品牌目录名，如 'hee'
 * @returns {Array<{name:string,qty:number}>}  — 识图 + 配件合并后的子品列表
 */
const path = require('path');
const fs = require('fs');

const PRODUCTS_DIR = path.join(__dirname, '../../data/products');

// 缓存，避免每次重复读文件
const _cache = {};

function loadAccessories(brand) {
  if (_cache[brand] !== undefined) return _cache[brand];
  const file = path.join(PRODUCTS_DIR, brand, 'accessories.json');
  try {
    const acc = JSON.parse(fs.readFileSync(file, 'utf8'));
    _cache[brand] = acc.rules || null;
  } catch {
    _cache[brand] = null;
  }
  return _cache[brand];
}

/**
 * @returns {Array<{name:string,qty:number}>}
 */
function resolveItems(platformCode, recognitionItems, brand) {
  const rules = loadAccessories(brand || 'hee');
  if (!rules || !rules[platformCode]) return recognitionItems.slice();

  const rule = rules[platformCode];
  const accessories = rule.accessories || [];
  if (accessories.length === 0) return recognitionItems.slice();

  // 合并：识图结果优先，配件追加（已在识图里出现的不重复加）
  const existing = new Set(recognitionItems.map(i => i.name));
  const extra = accessories.filter(a => !existing.has(a.erpName))
    .map(a => ({ name: a.erpName, qty: a.qty }));

  return [...recognitionItems, ...extra];
}

module.exports = { resolveItems };
