'use strict';
/**
 * WHAT: 从 ERP 库存状态页读取全量库存，映射为 displayName → 可用库存数
 * HOW:  点清空条件 → 点查询 → 翻页读全量 → getByErpName 映射
 * OUT:  data/warehouse-stock.json
 */
const fs   = require('fs');
const path = require('path');
const cdp  = require('../../product-mapping/lib/cdp');
const { navigateErp } = require('../../product-mapping/lib/navigate');
const { getByErpName } = require('./product-catalog');

const DATA_DIR   = path.join(__dirname, '../data');
const OUTPUT_FILE = path.join(DATA_DIR, 'warehouse-stock.json');

const STOCK_PAGE_HASH = '#/stock/newstatu/';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * 等待表格加载（有行且无 loading mask）
 */
async function waitForTableReady(erpId, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const ready = await cdp.eval(erpId, `
      (function(){
        var loading = document.querySelector('.el-loading-mask');
        if (loading) {
          var r = loading.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) return false;
        }
        var tables = [];
        document.querySelectorAll('.el-table').forEach(function(t){
          var r = t.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) tables.push(t);
        });
        if (!tables.length) return false;
        var rows = tables[0].querySelectorAll('tbody tr.el-table__row');
        return rows.length > 0;
      })()
    `);
    if (ready) return;
    await sleep(500);
  }
  throw new Error('等待表格超时');
}

/**
 * 读当前页所有行（从 Vue store 读，绕过虚拟滚动的 DOM 截断问题）
 * ERP 表格使用虚拟滚动，DOM 只渲染可视区约30行，Vue store.states.data 才是全量
 */
async function readCurrentPage(erpId) {
  return cdp.eval(erpId, `
    (function(){
      var tables = [];
      document.querySelectorAll('.el-table').forEach(function(t){
        var r = t.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) tables.push(t);
      });
      var vnode = tables[0] && tables[0].__vue__;
      var data = vnode && vnode.store && vnode.store.states && vnode.store.states.data;
      if (!data) return [];
      return data.map(function(item){
        return { name: item.title || '', avail: item.availableStock || 0 };
      });
    })()
  `);
}

/**
 * 主入口：查询 ERP 库存状态页全量数据
 * @param {string} erpId  - CDP target ID
 * @returns {object} { stock: {[displayName]: qty}, raw: [{name, avail}], warnings: [] }
 */
async function queryStock(erpId) {
  // 导航到库存状态页（自动处理登录和页面切换）
  await navigateErp(erpId, '库存状态');

  // 清空条件
  const cleared = await cdp.eval(erpId, `
    (function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && b.textContent.trim() === '清空条件';
      });
      if (btn) { btn.click(); return true; }
      return false;
    })()
  `);
  if (!cleared) throw new Error('找不到「清空条件」按钮');
  await sleep(800);

  // 点查询
  const queried = await cdp.eval(erpId, `
    (function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && b.textContent.trim() === '查询';
      });
      if (btn) { btn.click(); return true; }
      return false;
    })()
  `);
  if (!queried) throw new Error('找不到「查询」按钮');
  await sleep(2500);
  await waitForTableReady(erpId);

  // 等待分页信息加载，解析总记录数（totalText 可能延迟，需轮询）
  let totalRecords = 0;
  const totalWaitStart = Date.now();
  while (Date.now() - totalWaitStart < 10000) {
    const totalText = await cdp.eval(erpId, `
      (function(){
        var el = document.querySelector('.el-pagination__total');
        return el ? el.innerText.trim() : '';
      })()
    `);
    const m = totalText.match(/共(\d+)条/);
    if (m && parseInt(m[1], 10) > 0) {
      totalRecords = parseInt(m[1], 10);
      console.log(`  库存状态总记录: ${totalText}`);
      break;
    }
    await sleep(500);
  }
  if (totalRecords === 0) throw new Error('无法获取总记录数，分页信息未加载（超时10秒）');

  // 读页面实际 pageSize（每页条数选择器），fallback 50
  let PAGE_SIZE = 50;
  try {
    const psVal = await cdp.eval(erpId, `
      (function(){
        var sel = document.querySelector('.el-pagination .el-select .el-input__inner');
        return sel ? parseInt(sel.value, 10) : 50;
      })()
    `);
    if (psVal && psVal > 0) PAGE_SIZE = psVal;
  } catch (_) {}
  const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
  console.log(`  共 ${totalPages} 页，每页 ${PAGE_SIZE} 条`);

  // 翻页读全量数据（从 Vue store 读，绕过虚拟滚动截断）
  const allRows = [];
  for (let page = 1; page <= totalPages; page++) {
    if (page > 1) {
      await cdp.eval(erpId, `
        (function(){
          var btn = document.querySelector('button.btn-next');
          if (btn) btn.click();
        })()
      `);
      await sleep(2000);
      await waitForTableReady(erpId);
    }
    const rows = await readCurrentPage(erpId);
    console.log(`  第 ${page}/${totalPages} 页读取 ${rows.length} 条`);
    allRows.push(...rows);
  }

  console.log(`  共读取 ${allRows.length} 条原始数据（期望 ${totalRecords} 条）`);
  if (allRows.length !== totalRecords) {
    throw new Error(`数据不完整: 读取 ${allRows.length} 条，ERP 显示共 ${totalRecords} 条，请重试`);
  }

  // 映射 erpName → displayName
  const stock    = {};
  const warnings = [];
  const unmapped = [];

  for (const row of allRows) {
    if (!row.name) continue;
    const col = getByErpName(row.name);
    if (!col) {
      unmapped.push(row.name);
      continue;
    }
    const qty = typeof row.avail === 'number' ? row.avail : parseInt(row.avail, 10);
    if (isNaN(qty)) {
      warnings.push(`可用数解析失败: ${row.name} → "${row.avail}"`);
      continue;
    }
    // 同一 displayName 有多条（不同规格），取最大值或累加？取累加（一般不会重复）
    stock[col.displayName] = (stock[col.displayName] || 0) + qty;
  }

  if (unmapped.length > 0) {
    console.log(`  未映射商品（${unmapped.length} 条，非本次目录单品，已忽略）:`);
    unmapped.slice(0, 10).forEach(n => console.log(`    - ${n}`));
    if (unmapped.length > 10) console.log(`    ... 还有 ${unmapped.length - 10} 条`);
  }
  if (warnings.length > 0) {
    warnings.forEach(w => console.warn('  ⚠️ ', w));
  }

  return { stock, raw: allRows, warnings };
}

/**
 * 保存结果到 data/warehouse-stock.json
 */
async function queryStockAndSave(erpId) {
  // 清空旧数据，避免不同店铺间相互干扰
  fs.writeFileSync(OUTPUT_FILE, '{}', 'utf-8');

  const { stock, raw, warnings } = await queryStock(erpId);

  const output = {
    _meta: {
      source: 'ERP 库存状态页实时查询',
      queriedAt: new Date().toISOString(),
      totalRawRows: raw.length,
      mappedCount: Object.keys(stock).length,
      warnings,
    },
    stock,
  };
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2), 'utf-8');
  return output;
}

module.exports = { queryStock, queryStockAndSave };
