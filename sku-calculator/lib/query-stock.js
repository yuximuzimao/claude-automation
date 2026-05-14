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

  // 确认总记录数
  const totalText = await cdp.eval(erpId, `
    (function(){
      var el = document.querySelector('.el-pagination__total');
      return el ? el.innerText.trim() : '';
    })()
  `);
  console.log(`  库存状态总记录: ${totalText}`);

  // 翻页读全量数据（从 Vue store 读，绕过虚拟滚动截断）
  const allRows = [];
  let page = 1;
  while (true) {
    const rows = await readCurrentPage(erpId);
    console.log(`  第 ${page} 页读取 ${rows.length} 条`);
    allRows.push(...rows);

    // 检查下一页
    const nextDisabled = await cdp.eval(erpId, `
      (function(){
        var btn = document.querySelector('button.btn-next');
        return !btn || btn.disabled;
      })()
    `);
    if (nextDisabled) break;

    // 翻页
    await cdp.eval(erpId, `document.querySelector('button.btn-next').click()`);
    await sleep(2000);
    await waitForTableReady(erpId);
    page++;
  }

  console.log(`  共读取 ${allRows.length} 条原始数据`);

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
    console.log(`  未映射商品（${unmapped.length} 条，非 KGOS 单品，已忽略）:`);
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
