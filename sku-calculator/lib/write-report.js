/**
 * Excel 报告生成（exceljs 版，含联动公式）
 *
 * Sheet1「库存分配」列结构：
 *   A: 货号  B: 主销售属性  C: 建议库存（蓝色，可改）  D: 加购数
 *   每个单品占2列：[用量（蓝色）] [总占用 = $C{row}*用量列{row} （公式）]
 *
 * 汇总区（数据行之后）：
 *   合计行：每「总占用列」= SUM(该列数据区)
 *   云仓库存行：硬编码蓝色（可改）
 *   剩余库存行：= 云仓库存 - 合计（公式）
 *   余量达标行：= 剩余库存 >= 云仓库存*0.2（TRUE/FALSE，条件着色）
 *
 * Sheet2「瓶颈分析」：纯文字，不需要公式
 */

'use strict';

const ExcelJS = require('exceljs');
const colCache = require('exceljs/lib/utils/col-cache');
const path = require('path');
const { getAllColumns } = require('./product-catalog');

// 列号（1-based）→ Excel 列字母，使用 exceljs 内置
const colLetter = n => colCache.n2l(n);

// 颜色常量
const COLOR_BLUE_INPUT = { argb: 'FF0070C0' };   // 蓝色：用户可改的输入项
const COLOR_BLACK      = { argb: 'FF000000' };   // 黑色：公式
const COLOR_HEADER_BG  = { argb: 'FF4472C4' };   // 表头背景蓝
const COLOR_HEADER_FG  = { argb: 'FFFFFFFF' };   // 表头文字白
const COLOR_SUBHDR_BG  = { argb: 'FFD9E1F2' };   // 子表头背景浅蓝
const COLOR_TOTAL_BG   = { argb: 'FFFFF2CC' };   // 合计区背景黄

/**
 * 生成 Excel 报告
 */
async function writeReport(allocResult, warehouseStock, outputPath) {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'SKU Calculator';
  wb.created = new Date();

  const productCols = getAllColumns(); // 按 colIndex 升序

  await buildMainSheet(wb, allocResult, warehouseStock, productCols);
  buildAnalysisSheet(wb, allocResult, warehouseStock, productCols);

  await wb.xlsx.writeFile(outputPath);
  return outputPath;
}

async function buildMainSheet(wb, allocResult, warehouseStock, productCols) {
  const ws = wb.addWorksheet('库存分配');
  const { skuDetails } = allocResult;

  // ── 固定列：A=货号 B=主销售属性 C=建议库存 D=加购数 ──
  const FIXED_COLS = 4;

  // 每个单品占 2 列：[用量, 总占用]
  // 单品 i (0-based) 的用量列 = FIXED_COLS + 1 + i*2
  //                  总占用列 = FIXED_COLS + 2 + i*2

  const totalCols = FIXED_COLS + productCols.length * 2;

  // ── 列宽 ──
  ws.getColumn(1).width = 16; // 货号
  ws.getColumn(2).width = 38; // 主销售属性
  ws.getColumn(3).width = 12; // 建议库存
  ws.getColumn(4).width = 10; // 加购数
  for (let i = 0; i < productCols.length; i++) {
    ws.getColumn(FIXED_COLS + 1 + i * 2).width = 10; // 用量
    ws.getColumn(FIXED_COLS + 2 + i * 2).width = 10; // 总占用
  }

  // ── 行1：表头 ──
  const hdrRow = ws.getRow(1);
  hdrRow.height = 36;
  const hdrValues = ['货号', '主销售属性', '建议库存', '加购数'];
  for (const col of productCols) {
    const erpName = (col.erpNames && col.erpNames[0]) || col.displayName;
    hdrValues.push(erpName);
    hdrValues.push(''); // 总占用列（合并到一个表头）
  }
  hdrRow.values = hdrValues;

  // 表头合并（每个单品2列合并为1个表头）
  for (let i = 0; i < productCols.length; i++) {
    const c1 = FIXED_COLS + 1 + i * 2;
    const c2 = FIXED_COLS + 2 + i * 2;
    ws.mergeCells(1, c1, 1, c2);
  }

  // 表头样式
  hdrRow.eachCell({ includeEmpty: true }, (cell, colNum) => {
    if (colNum > totalCols) return;
    cell.font = { bold: true, color: COLOR_HEADER_FG, name: 'Arial', size: 10 };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_HEADER_BG };
    cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true };
    cell.border = {
      bottom: { style: 'thin', color: { argb: 'FFFFFFFF' } },
    };
  });

  // ── 行2：子表头（用量 / 总占用）──
  const subHdrRow = ws.getRow(2);
  subHdrRow.height = 18;
  const subHdrValues = ['', '', '', ''];
  for (let i = 0; i < productCols.length; i++) {
    subHdrValues.push('用量');
    subHdrValues.push('总占用');
  }
  subHdrRow.values = subHdrValues;
  subHdrRow.eachCell({ includeEmpty: true }, (cell, colNum) => {
    if (colNum > totalCols) return;
    cell.font = { bold: true, color: COLOR_BLACK, name: 'Arial', size: 9 };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_SUBHDR_BG };
    cell.alignment = { vertical: 'middle', horizontal: 'center' };
  });

  // ── 数据行（行3 起）──
  const DATA_START_ROW = 3;
  const dataRowCount = skuDetails.length;

  for (let di = 0; di < dataRowCount; di++) {
    const sku = skuDetails[di];
    const rowNum = DATA_START_ROW + di;
    const row = ws.getRow(rowNum);
    row.height = 16;

    // 固定列
    row.getCell(1).value = sku.huohao;
    row.getCell(2).value = sku.skuName;
    // 建议库存：硬编码蓝色
    const invCell = row.getCell(3);
    invCell.value = sku.allocatedInventory;
    invCell.font = { color: COLOR_BLUE_INPUT, name: 'Arial', size: 10 };
    // 加购数
    row.getCell(4).value = sku.cartAddCount;
    row.getCell(4).font = { color: COLOR_BLACK, name: 'Arial', size: 10 };

    // 单品列
    const invColLetter = colLetter(3); // C 列，固定不变
    for (let i = 0; i < productCols.length; i++) {
      const col = productCols[i];
      const qtyColNum   = FIXED_COLS + 1 + i * 2; // 用量列
      const totalColNum = FIXED_COLS + 2 + i * 2; // 总占用列
      const qtyColLetter   = colLetter(qtyColNum);
      const totalColLetter = colLetter(totalColNum);

      const breakdown = sku.productBreakdown[col.displayName];
      const qtyPerUnit = breakdown ? breakdown.qtyPerUnit : 0;

      // 用量：硬编码蓝色（仅非零）
      const qtyCell = row.getCell(qtyColNum);
      if (qtyPerUnit > 0) {
        qtyCell.value = qtyPerUnit;
        qtyCell.font = { color: COLOR_BLUE_INPUT, name: 'Arial', size: 10 };
      } else {
        qtyCell.value = 0;
        qtyCell.font = { color: { argb: 'FFAAAAAA' }, name: 'Arial', size: 10 };
      }

      // 总占用：公式 = $C{row} * 用量列{row}
      const totalCell = row.getCell(totalColNum);
      totalCell.value = { formula: `$${invColLetter}${rowNum}*${qtyColLetter}${rowNum}` };
      totalCell.font = { color: COLOR_BLACK, name: 'Arial', size: 10 };
      totalCell.numFmt = '0';
    }

    // 交替行底色
    if (di % 2 === 1) {
      row.eachCell({ includeEmpty: true }, (cell, colNum) => {
        if (colNum > totalCols) return;
        if (!cell.fill || cell.fill.pattern !== 'solid') {
          cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F2F2' } };
        }
      });
    }
  }

  // ── 汇总区 ──
  const SUMMARY_START = DATA_START_ROW + dataRowCount + 1; // 空一行
  const lastDataRow   = DATA_START_ROW + dataRowCount - 1;

  function setSummaryLabel(rowNum, label) {
    const r = ws.getRow(rowNum);
    r.getCell(4).value = label;
    r.getCell(4).font = { bold: true, name: 'Arial', size: 10 };
    r.getCell(4).fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    r.height = 18;
    return r;
  }

  const ROW_TOTAL   = SUMMARY_START;
  const ROW_STOCK   = SUMMARY_START + 1;
  const ROW_REMAIN  = SUMMARY_START + 2;
  const ROW_QUALIFY = SUMMARY_START + 3;

  const totalRow   = setSummaryLabel(ROW_TOTAL,   '合计');
  const stockRow   = setSummaryLabel(ROW_STOCK,   '云仓库存');
  const remainRow  = setSummaryLabel(ROW_REMAIN,  '剩余库存');
  const qualifyRow = setSummaryLabel(ROW_QUALIFY, '余量达标(≥20%)');

  for (let i = 0; i < productCols.length; i++) {
    const col = productCols[i];
    const qtyColNum   = FIXED_COLS + 1 + i * 2;
    const totalColNum = FIXED_COLS + 2 + i * 2;
    const totalColLetter = colLetter(totalColNum);
    const stockQty = warehouseStock[col.displayName] || 0;

    // 合计 = SUM(总占用列数据区)
    const totalCell = totalRow.getCell(totalColNum);
    totalCell.value = { formula: `SUM(${totalColLetter}${DATA_START_ROW}:${totalColLetter}${lastDataRow})` };
    totalCell.font = { bold: true, color: COLOR_BLACK, name: 'Arial', size: 10 };
    totalCell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    totalCell.numFmt = '0';

    // 用量列汇总区留空（不填公式），使用已缓存的行对象
    for (const r of [totalRow, stockRow, remainRow, qualifyRow]) {
      r.getCell(qtyColNum).fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    }

    // 云仓库存：硬编码蓝色
    const stockCell = stockRow.getCell(totalColNum);
    stockCell.value = stockQty;
    stockCell.font = { color: COLOR_BLUE_INPUT, name: 'Arial', size: 10 };
    stockCell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    stockCell.numFmt = '0';

    // 剩余库存 = 云仓库存 - 合计（公式）
    const remainCell = remainRow.getCell(totalColNum);
    remainCell.value = { formula: `${totalColLetter}${ROW_STOCK}-${totalColLetter}${ROW_TOTAL}` };
    remainCell.font = { color: COLOR_BLACK, name: 'Arial', size: 10 };
    remainCell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    remainCell.numFmt = '0';

    // 余量达标 = 剩余 >= 云仓*0.2（公式）
    const qualCell = qualifyRow.getCell(totalColNum);
    qualCell.value = { formula: `IF(${totalColLetter}${ROW_REMAIN}>=${totalColLetter}${ROW_STOCK}*0.2,"✓ 达标","✗ 不足")` };
    qualCell.font = { name: 'Arial', size: 10 };
    qualCell.fill = { type: 'pattern', pattern: 'solid', fgColor: COLOR_TOTAL_BG };
    qualCell.alignment = { horizontal: 'center' };

  }

  // 冻结前两行表头
  ws.views = [{ state: 'frozen', ySplit: 2 }];

  // 人工复核警告（如有）放到 qualify 行下方
  const warnings = (allocResult._meta && allocResult._meta.warnings) || [];
  const reviewWarnings = warnings.filter(w => w.includes('人工复核'));
  if (reviewWarnings.length) {
    const warnStartRow = ROW_QUALIFY + 2;
    ws.getRow(warnStartRow).getCell(1).value = '⚠️ 人工复核提示';
    ws.getRow(warnStartRow).getCell(1).font = { bold: true, color: { argb: 'FF9C0006' }, name: 'Arial', size: 10 };
    for (let j = 0; j < reviewWarnings.length; j++) {
      ws.getRow(warnStartRow + 1 + j).getCell(1).value = reviewWarnings[j];
      ws.getRow(warnStartRow + 1 + j).getCell(1).font = { color: { argb: 'FF9C0006' }, name: 'Arial', size: 9 };
    }
  }
}

function buildAnalysisSheet(wb, allocResult, warehouseStock, productCols) {
  const ws = wb.addWorksheet('瓶颈分析');
  ws.getColumn(1).width = 32;
  ws.getColumn(2).width = 14;
  ws.getColumn(3).width = 14;
  ws.getColumn(4).width = 14;
  ws.getColumn(5).width = 14;
  ws.getColumn(6).width = 12;

  const { _meta, available, totalDemand } = allocResult;

  const addRow = (values, opts = {}) => {
    const r = ws.addRow(values);
    if (opts.bold) r.font = { bold: true };
    if (opts.bg) {
      r.eachCell({ includeEmpty: true }, (cell, cn) => {
        if (cn <= values.length) {
          cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: opts.bg } };
        }
      });
    }
    return r;
  };

  addRow(['── 分配参数 ──'], { bold: true, bg: 'FFD9E1F2' });
  addRow(['最紧约束系数 k（参考值）', _meta.k]);
  addRow(['说明', _meta.k < 1 ? '存在库存不足单品，相关 SKU 按比例缩减；其余按充分利用库存分配' : '所有单品库存充足，全部按加购数充分分配']);
  addRow(['库存余量比例', `${(_meta.reserve * 100).toFixed(0)}%`]);
  addRow(['无加购SKU保底', `${_meta.coldFixed} 件`]);
  addRow(['有加购SKU数', _meta.activeCount]);
  addRow(['无加购SKU数', _meta.coldCount]);
  ws.addRow([]);

  addRow(['── 瓶颈分析 ──'], { bold: true, bg: 'FFD9E1F2' });
  addRow(['瓶颈单品', _meta.bottleneck || '（无）']);
  addRow(['瓶颈利用率', _meta.bottleneckRatio !== null
    ? `${(Math.min(_meta.bottleneckRatio, 1) * 100).toFixed(1)}%`
    : 'N/A'
  ]);
  ws.addRow([]);

  addRow(['── 各单品详情 ──'], { bold: true, bg: 'FFD9E1F2' });
  addRow(['单品', '云仓库存', '可用量(80%)', '总需求', '剩余', '利用率'], { bold: true, bg: 'FFD9E1F2' });

  for (const col of productCols) {
    const stockQty = warehouseStock[col.displayName] || 0;
    const avail = available[col.displayName] || 0;
    const demand = totalDemand[col.displayName] || 0;
    const remaining = stockQty - demand;
    const utilization = avail > 0 ? Math.min(demand / avail, 1) : (demand > 0 ? 1 : 0);
    const r = ws.addRow([
      col.displayName,
      stockQty,
      Math.round(avail),
      demand,
      remaining,
      `${(utilization * 100).toFixed(1)}%`,
    ]);
    if (utilization >= 0.9) {
      r.getCell(6).font = { color: { argb: 'FF9C0006' }, bold: true };
    }
  }
  ws.addRow([]);

  const warnings = (_meta.warnings || []);
  if (warnings.length) {
    addRow(['── 警告 ──'], { bold: true, bg: 'FFFFC7CE' });
    for (const w of warnings) {
      ws.addRow([w]);
    }
  }
}

module.exports = { writeReport };
