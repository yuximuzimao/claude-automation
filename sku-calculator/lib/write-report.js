/**
 * Excel 报告生成
 * 输出格式对齐 0422实时库存.xlsx 模板：
 *   - 列 A-E: 货号, 主销售属性, 建议库存, 加购数
 *   - 列 F-AS: 19个单品 × 2列（单位用量, 总占用）
 *   - 底部汇总行: 合计 / 云仓库存 / 剩余库存
 *   - 额外 sheet "瓶颈分析": k值, 瓶颈单品, 各单品利用率
 */

const XLSX = require('xlsx');
const path = require('path');
const { getAllColumns } = require('./product-catalog');

/**
 * 生成 Excel 报告
 * @param {object} allocResult - allocate() 的返回值
 * @param {object} warehouseStock - { [displayName]: qty } 原始云仓库存
 * @param {string} outputPath - 输出文件路径
 */
function writeReport(allocResult, warehouseStock, outputPath) {
  const wb = XLSX.utils.book_new();
  const productCols = getAllColumns(); // 19个单品，按 colIndex 升序

  // ─── Sheet 1: 库存分配 ───
  const sheet1Data = buildMainSheet(allocResult, warehouseStock, productCols);
  const ws1 = XLSX.utils.aoa_to_sheet(sheet1Data);
  applyColumnWidths(ws1, productCols);
  XLSX.utils.book_append_sheet(wb, ws1, '库存分配');

  // ─── Sheet 2: 瓶颈分析 ───
  const sheet2Data = buildAnalysisSheet(allocResult, warehouseStock, productCols);
  const ws2 = XLSX.utils.aoa_to_sheet(sheet2Data);
  XLSX.utils.book_append_sheet(wb, ws2, '瓶颈分析');

  XLSX.writeFile(wb, outputPath);
  return outputPath;
}

function buildMainSheet(allocResult, warehouseStock, productCols) {
  const { skuDetails, totalDemand, available } = allocResult;

  // 第1行：表头
  const headerRow1 = ['货号', '主销售属性', '建议库存', '加购数'];
  for (const col of productCols) {
    headerRow1.push(col.displayName); // 单位用量列
    headerRow1.push('');              // 总占用列（合并标题）
  }

  // 数据行
  const rows = [headerRow1];
  for (const sku of skuDetails) {
    const row = [
      sku.huohao,
      sku.skuName,
      sku.allocatedInventory,
      sku.cartAddCount,
    ];
    for (const col of productCols) {
      const breakdown = sku.productBreakdown[col.displayName];
      if (breakdown) {
        row.push(breakdown.qtyPerUnit);   // 单位用量
        row.push(breakdown.totalDemand);  // 总占用
      } else {
        row.push(0);
        row.push(0);
      }
    }
    rows.push(row);
  }

  // 空行分隔
  rows.push([]);

  // 汇总行：合计（各单品总占用）
  const totalRow = ['', '', '', '合计'];
  for (const col of productCols) {
    totalRow.push(''); // 单位用量列不填
    totalRow.push(totalDemand[col.displayName] || 0);
  }
  rows.push(totalRow);

  // 云仓库存行
  const stockRow = ['', '', '', '云仓库存'];
  for (const col of productCols) {
    stockRow.push('');
    stockRow.push(warehouseStock[col.displayName] || 0);
  }
  rows.push(stockRow);

  // 剩余库存行（云仓 - 合计）
  const remainRow = ['', '', '', '剩余库存'];
  for (const col of productCols) {
    const rem = (warehouseStock[col.displayName] || 0) - (totalDemand[col.displayName] || 0);
    remainRow.push('');
    remainRow.push(rem);
  }
  rows.push(remainRow);

  return rows;
}

function buildAnalysisSheet(allocResult, warehouseStock, productCols) {
  const { _meta, available, totalDemand } = allocResult;

  const rows = [];
  rows.push(['── 分配参数 ──']);
  rows.push(['全局缩放系数 k', _meta.k]);
  rows.push(['k < 1 说明', _meta.k < 1 ? '库存不足，按比例缩减' : '库存充足，按加购数分配']);
  rows.push(['库存余量比例', `${(_meta.reserve * 100).toFixed(0)}%`]);
  rows.push(['无加购SKU保底', `${_meta.coldFixed} 件`]);
  rows.push(['有加购SKU数', _meta.activeCount]);
  rows.push(['无加购SKU数', _meta.coldCount]);
  rows.push([]);

  rows.push(['── 瓶颈分析 ──']);
  rows.push(['瓶颈单品', _meta.bottleneck || '（无）']);
  rows.push(['瓶颈利用率', _meta.bottleneckRatio !== null
    ? `${(Math.min(_meta.bottleneckRatio, 1) * 100).toFixed(1)}%`
    : 'N/A'
  ]);
  rows.push([]);

  rows.push(['── 各单品详情 ──']);
  rows.push(['单品', '云仓库存', '可用量(80%)', '总需求', '剩余', '利用率']);
  for (const col of productCols) {
    const stockQty = warehouseStock[col.displayName] || 0;
    const avail = available[col.displayName] || 0;
    const demand = totalDemand[col.displayName] || 0;
    const remaining = stockQty - demand;
    const utilization = avail > 0 ? Math.min(demand / avail, 1) : (demand > 0 ? 1 : 0);
    rows.push([
      col.displayName,
      stockQty,
      Math.round(avail),
      demand,
      remaining,
      `${(utilization * 100).toFixed(1)}%`,
    ]);
  }
  rows.push([]);

  if (_meta.warnings && _meta.warnings.length > 0) {
    rows.push(['── 警告 ──']);
    for (const w of _meta.warnings) {
      rows.push([w]);
    }
  }

  return rows;
}

function applyColumnWidths(ws, productCols) {
  const colWidths = [
    { wch: 16 }, // 货号
    { wch: 40 }, // 主销售属性
    { wch: 10 }, // 建议库存
    { wch: 10 }, // 加购数
  ];
  for (let i = 0; i < productCols.length; i++) {
    colWidths.push({ wch: 12 }); // 单位用量
    colWidths.push({ wch: 10 }); // 总占用
  }
  ws['!cols'] = colWidths;
}

module.exports = { writeReport };
