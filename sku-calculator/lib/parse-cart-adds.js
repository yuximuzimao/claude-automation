/**
 * 加购数据解析
 * 读取鲸灵平台导出的 Excel，提取每个 SKU 的加购件数
 * 支持表头名匹配（不依赖列位置）
 */

const XLSX = require('xlsx');
const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, '../data/cart-adds.json');

// 已知的列名映射（鲸灵导出格式可能变化，按优先级尝试）
const COL_ALIASES = {
  货号:      ['货号'],
  商品名称:  ['商品名称'],
  skuName:   ['属性1', '属性1值', '主销售属性', 'sku名称'],
  加购件数:  ['加购件数', '加购数量'],
  加购用户数: ['加购用户数', '加购人数'],
  skuId:     ['sku_id', 'sku id', 'skuid'],
  spuId:     ['spu_id', 'spu id', 'spuid'],
};

/**
 * 从 header 行找到指定字段的列索引
 * @param {string[]} headers 表头列表
 * @param {string} field COL_ALIASES 中的 key
 * @returns {number} 列索引（-1 表示未找到）
 */
function findCol(headers, field) {
  const aliases = COL_ALIASES[field] || [field];
  for (const alias of aliases) {
    const idx = headers.findIndex(h => h && h.toString().trim() === alias.trim());
    if (idx !== -1) return idx;
  }
  return -1;
}

/**
 * 解析加购 Excel 文件
 * @param {string} filePath Excel 文件路径
 * @returns {{ skus: object[], warnings: string[] }}
 */
function parseCartAdds(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`文件不存在: ${filePath}`);
  }

  const wb = XLSX.readFile(filePath);
  const sheetName = wb.SheetNames[0];
  const ws = wb.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: null });

  if (rows.length < 2) {
    throw new Error('Excel 文件为空或只有表头');
  }

  const headers = rows[0].map(h => h ? h.toString().trim() : '');

  // 找各列索引
  const cols = {
    货号:      findCol(headers, '货号'),
    商品名称:  findCol(headers, '商品名称'),
    skuName:   findCol(headers, 'skuName'),
    加购件数:  findCol(headers, '加购件数'),
    加购用户数: findCol(headers, '加购用户数'),
    skuId:     findCol(headers, 'skuId'),
    spuId:     findCol(headers, 'spuId'),
  };

  const warnings = [];
  if (cols.货号 === -1) warnings.push('⚠️  未找到"货号"列，请检查表头');
  if (cols.加购件数 === -1) warnings.push('⚠️  未找到"加购件数"列，SKU 将使用默认库存');
  if (cols.skuName === -1) warnings.push('⚠️  未找到 SKU 变体名列（属性1/主销售属性等）');

  const skus = [];
  const seen = new Set(); // 去重：货号+变体名

  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (!row || row.every(v => v === null || v === '')) continue;

    const huohao = cols.货号 >= 0 ? (row[cols.货号] || '').toString().trim() : '';
    if (!huohao) continue;

    const skuName = cols.skuName >= 0 ? (row[cols.skuName] || '').toString().trim() : '';
    const key = `${huohao}::${skuName}`;
    if (seen.has(key)) {
      warnings.push(`⚠️  重复行 row${r + 1}：${key}，已跳过`);
      continue;
    }
    seen.add(key);

    const cartAddCount = cols.加购件数 >= 0
      ? (parseFloat(row[cols.加购件数]) || 0)
      : 0;

    skus.push({
      key,
      huohao,
      skuName,
      productName: cols.商品名称 >= 0 ? (row[cols.商品名称] || '').toString().trim() : '',
      cartAddCount,
      skuId: cols.skuId >= 0 ? (row[cols.skuId] || null) : null,
      spuId: cols.spuId >= 0 ? (row[cols.spuId] || null) : null,
    });
  }

  if (skus.length === 0) {
    warnings.push('⚠️  未解析到任何 SKU 数据，请检查文件格式');
  }

  return { skus, warnings };
}

/**
 * 解析并保存到 data/cart-adds.json
 * @param {string} filePath
 * @returns {{ skus, warnings }}
 */
function parseAndSave(filePath) {
  const result = parseCartAdds(filePath);
  const output = {
    _meta: {
      sourceFile: path.basename(filePath),
      parsedAt: new Date().toISOString(),
      totalSkus: result.skus.length,
      withCartData: result.skus.filter(s => s.cartAddCount > 0).length,
    },
    skus: result.skus,
  };
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2), 'utf-8');
  return result;
}

module.exports = { parseCartAdds, parseAndSave };
