'use strict';
/**
 * WHAT: ERP 商品档案V2查询（规格编码→商品详情+子品明细）
 * WHERE: collect.js 商品采集 → CLI product-archive 命令 → 此模块
 * WHY: 档案V2是商品规格的唯一权威数据，子品明细用于套装数量核对
 * ENTRY: cli.js: product-archive 命令, collect.js: 商品数据采集
 */
const cdp = require('../cdp');
const { navigateErp } = require('../erp/navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 切换查询类型为「精确查询」（见 docs/erp-query.md §2）
const SET_EXACT_QUERY_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
    var r = i.getBoundingClientRect(); return r.width > 0 && r.height > 0;
  });
  var qt = inputs.find(function(i){ return i.placeholder === '查询类型'; });
  if (!qt) return JSON.stringify({error:'查询类型下拉不存在'});
  if (qt.value === '精确查询') return JSON.stringify({alreadySet: true});
  var sel = qt.closest('.el-select');
  if (sel) sel.click();
  return JSON.stringify({opened: true});
})()`;

const CLICK_EXACT_OPTION_JS = `(function(){
  var li = Array.from(document.querySelectorAll('li.el-select-dropdown__item')).find(function(e){
    var r = e.getBoundingClientRect();
    return e.textContent.trim() === '精确查询' && r.width > 0;
  });
  if (!li) {
    var span = Array.from(document.querySelectorAll('span')).find(function(e){
      var r = e.getBoundingClientRect();
      return e.textContent.trim() === '精确查询' && e.children.length === 0 && r.width > 0;
    });
    if (!span) return JSON.stringify({error:'精确查询选项不可见'});
    span.click();
    return JSON.stringify({clicked: true, via: 'span'});
  }
  li.click();
  return JSON.stringify({clicked: true, via: 'li'});
})()`;

function makeSearchSpecCodeJS(specCode) {
  return `(function(){
    var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
      var r = i.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var mainInp = inputs.find(function(i){ return i.placeholder === '主商家编码'; });
    if (!mainInp) return JSON.stringify({error:'主商家编码输入框不存在'});
    mainInp.value = '${specCode}';
    mainInp.dispatchEvent(new Event('input', {bubbles:true}));
    mainInp.dispatchEvent(new Event('change', {bubbles:true}));
    var el = mainInp; var sv = null;
    for (var i = 0; i < 12; i++) {
      if (!el) break;
      var v = el.__vue__;
      if (v && typeof v.handleQuery === 'function') { sv = v; break; }
      el = el.parentElement;
    }
    if (!sv) return JSON.stringify({error:'未找到 handleQuery'});
    sv.handleQuery();
    return JSON.stringify({searched: '${specCode}', searchData: sv.searchData});
  })()`;
}

const READ_DATALIST_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
    var r = i.getBoundingClientRect(); return r.width > 0 && r.height > 0;
  });
  var el = inputs.find(function(i){ return i.placeholder === '主商家编码'; });
  if (!el) return JSON.stringify({error:'未找到输入框'});
  var v = el; var sv = null;
  for (var i = 0; i < 12; i++) {
    if (!v) break;
    var vm = v.__vue__;
    if (vm && vm.dataList) { sv = vm; break; }
    v = v.parentElement;
  }
  if (!sv || !sv.dataList || !sv.dataList.length) {
    return JSON.stringify({error:'dataList 为空', count: sv ? sv.dataList.length : -1});
  }
  var item = sv.dataList[0];
  return JSON.stringify({
    outerId: item.outerId,
    title: item.title,
    subItemNum: item.subItemNum || 0,
    type: item.type,
    hasProduct: item.hasProduct
  });
})()`;

// 点击子商品数字链接（a.ml_15）展开单品明细
function makeClickSubItemLinkJS(subItemNum) {
  return `(function(){
    var el = Array.from(document.querySelectorAll('a.ml_15')).find(function(a){
      var r = a.getBoundingClientRect();
      return a.innerText.trim() === '${subItemNum}' && r.width > 0;
    });
    if (!el) return JSON.stringify({error:'subItem link not found for num=${subItemNum}'});
    el.click();
    return JSON.stringify({clicked: true});
  })()`;
}

// 关闭子商品弹窗（读完明细后调用）
// 使用 DOM 移除而非 btn.click()：Vue 的 fade 动画可能卡在中途不完成，导致弹窗残留
// 残留弹窗阻塞下次查询的 a.ml_15 点击和子品表格读取
const CLOSE_SUB_DIALOG_JS = `(function(){
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!wrappers.length) return JSON.stringify({skipped: 'no visible dialog'});
  var closed = 0;
  wrappers.forEach(function(w){
    // 优先 DOM 强制移除（绕过 Vue 动画），fallback 点关闭按钮
    if (w.parentNode) { w.parentNode.removeChild(w); closed++; }
    else {
      var btn = w.querySelector('button.el-dialog__closeBtn');
      if (btn) { btn.click(); closed++; }
    }
  });
  return JSON.stringify({closed: closed});
})()`;

// 读子商品明细表格：通过表头文本定位列索引，不做数据特征过滤
const READ_SUB_ITEMS_JS = `(function(){
  // 找最新打开的可见 dialog
  var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!dialogs.length) return JSON.stringify({error:'子商品弹窗未打开'});
  var dialog = dialogs[dialogs.length - 1];

  // 通过表头文本定位列索引
  var ths = dialog.querySelectorAll('th');
  var colName = -1, colCode = -1, colQty = -1;
  for (var i = 0; i < ths.length; i++) {
    var txt = ths[i].innerText.trim();
    if (txt === '商品名称') colName = i;
    else if (txt === '商家编码') colCode = i;
    else if (txt === '组合比例') colQty = i;
  }
  if (colName < 0 || colCode < 0 || colQty < 0) {
    var headerTexts = Array.from(ths).map(function(th){ return th.innerText.trim(); });
    return JSON.stringify({error:'未找到子品明细表头', headers: headerTexts, colName: colName, colCode: colCode, colQty: colQty});
  }

  // 读所有数据行
  var rows = dialog.querySelectorAll('tr.el-table__row');
  var items = [];
  var debugSkips = [];
  rows.forEach(function(r, ri){
    var cells = r.querySelectorAll('td');
    if (cells.length <= Math.max(colName, colCode, colQty)) {
      debugSkips.push({row:ri, reason:'cells too few', cellCount:cells.length});
      return;
    }
    var name = (cells[colName].innerText || '').trim();
    var code = (cells[colCode].innerText || '').trim();
    var qtyText = (cells[colQty].innerText || '').trim();
    var qty = parseInt(qtyText);
    if (!name) { debugSkips.push({row:ri, reason:'empty name'}); return; }
    if (!code) { debugSkips.push({row:ri, reason:'empty code'}); return; }
    if (isNaN(qty)) { debugSkips.push({row:ri, reason:'NaN qty', qtyText: qtyText}); return; }
    if (qty <= 0) { debugSkips.push({row:ri, reason:'qty<=0', qty: qty}); return; }
    items.push({ name: name, specCode: code, qty: qty });
  });
  if (!items.length) {
    return JSON.stringify({error:'弹窗内未找到子商品行', debug: {rowsFound: rows.length, colName: colName, colCode: colCode, colQty: colQty, skips: debugSkips}});
  }
  return JSON.stringify(items);
})()`;

async function productArchive(targetId, specCode) {
  try {
    await navigateErp(targetId, '商品档案V2');

    // 设置精确查询
    await retry(async () => {
      const set = await cdp.eval(targetId, SET_EXACT_QUERY_JS);
      if (set.error) throw new Error(set.error);
      if (!set.alreadySet) {
        await sleep(600);
        const click = await cdp.eval(targetId, CLICK_EXACT_OPTION_JS);
        if (click.error) throw new Error(click.error);
        await sleep(500);
      }
    }, { maxRetries: 3, delayMs: 800, label: 'set exact query' });

    // 搜索
    const data = await retry(async () => {
      const search = await cdp.eval(targetId, makeSearchSpecCodeJS(specCode));
      if (search.error) throw new Error(search.error);
      await sleep(3500);
      const d = await cdp.eval(targetId, READ_DATALIST_JS);
      if (d.error) throw new Error(d.error);
      return d;
    }, { maxRetries: 3, delayMs: 2000, label: `product-archive ${specCode}` });

    // 套件：点 a.ml_15 展开单品明细
    let subItems = [];
    if (data.subItemNum > 0) {
      try {
        await retry(async () => {
          const clickRes = await cdp.eval(targetId, makeClickSubItemLinkJS(data.subItemNum));
          if (clickRes.error) throw new Error(clickRes.error);
        }, { maxRetries: 3, delayMs: 1000, label: `click-sub-item ${specCode}` });
        await sleep(1500);
        try {
          const raw = await retry(async () => {
            const r = await cdp.eval(targetId, READ_SUB_ITEMS_JS);
            if (r.error) throw new Error(r.error);
            return r;
          }, { maxRetries: 3, delayMs: 1000, label: `read-sub-items ${specCode}` });
          subItems = Array.isArray(raw) ? raw : [];
        } catch (e) {
          console.error(`[product-archive] 子品明细读取失败: ${e.message}`);
        }
      } finally {
        await cdp.eval(targetId, CLOSE_SUB_DIALOG_JS);
        await sleep(600);
      }
    }

    return ok({ ...data, subItems });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { productArchive };
