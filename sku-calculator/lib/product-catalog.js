/**
 * 单品目录注册
 * 维护 19 个单品的显示名、ERP名称、列顺序映射
 * 数据来源: data/product-columns.json
 */

const fs = require('fs');
const path = require('path');

const COLUMNS_FILE = path.join(__dirname, '../data/product-columns.json');

let _catalog = null;

function loadCatalog() {
  if (_catalog) return _catalog;
  const columns = JSON.parse(fs.readFileSync(COLUMNS_FILE, 'utf-8'));

  // 建立多方向索引
  const byIndex = {};          // colIndex -> entry
  const byDisplayName = {};    // displayName -> entry
  const byErpName = {};        // erpName (各别名) -> entry

  for (const entry of columns) {
    byIndex[entry.colIndex] = entry;
    byDisplayName[entry.displayName] = entry;
    for (const erpName of entry.erpNames) {
      byErpName[erpName] = entry;
    }
  }

  _catalog = { columns, byIndex, byDisplayName, byErpName };
  return _catalog;
}

/**
 * 通过 ERP 名称获取对应的单品条目
 * @param {string} erpName
 * @returns {object|null} entry (含 colIndex, displayName)
 */
function getByErpName(erpName) {
  const { byErpName } = loadCatalog();
  return byErpName[erpName] || null;
}

/**
 * 通过显示名获取条目
 * @param {string} displayName
 * @returns {object|null}
 */
function getByDisplayName(displayName) {
  const { byDisplayName } = loadCatalog();
  return byDisplayName[displayName] || null;
}

/**
 * 获取按列顺序排列的所有单品
 * @returns {object[]} 按 colIndex 升序
 */
function getAllColumns() {
  const { columns } = loadCatalog();
  return [...columns].sort((a, b) => a.colIndex - b.colIndex);
}

/**
 * 获取总列数
 */
function getColumnCount() {
  return loadCatalog().columns.length;
}

function clearCache() {
  _catalog = null;
}

module.exports = { getByErpName, getByDisplayName, getAllColumns, getColumnCount, clearCache };
