'use strict';
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
  var el = document.querySelector('.el-input__inner[placeholder="主商家编码"]');
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
const CLOSE_SUB_DIALOG_JS = `(function(){
  var visible = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!visible.length) return JSON.stringify({skipped: 'no visible dialog'});
  var btn = visible[0].querySelector('button.el-dialog__closeBtn');
  if (!btn) return JSON.stringify({skipped: 'no closeBtn in dialog'});
  btn.click();
  return JSON.stringify({closed: true});
})()`;

// 读子商品明细表格
// 策略：先尝试 dialog 限定，再无结果则退回到全页读取（dialog 表可能结构与主表不同）
// 所有读取结果均经过验证层过滤垃圾数据
const READ_SUB_ITEMS_JS = `(function(){
  function readRows(container) {
    var rows = Array.from(container.querySelectorAll('tr.el-table__row'));
    var items = [];
    var debug = [];
    rows.forEach(function(r, ri){
      var cells = Array.from(r.querySelectorAll('td')).map(function(td){ return td.innerText.trim(); });
      if (ri < 2) {
        debug.push({rowIdx: ri, cellCount: cells.length, cells: cells.slice(0, Math.min(cells.length, 12))});
      }
      if (!cells[1] || !cells[3] || !cells[10]) return;
      var qty = parseInt(cells[10]);
      if (isNaN(qty) || qty <= 0) return;
      if (!/^\\d{6,}$/.test(cells[3])) return;
      if (/已(下|付|发)单|\\d{4}-\\d{2}-\\d{2}\\s*\\d{2}:\\d{2}/.test(cells[1])) return;
      items.push({ name: cells[1], specCode: cells[3], qty: qty });
    });
    return { items: items, debug: debug };
  }

  // Step 1: 尝试限定在最新可见 dialog 内读取
  var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (dialogs.length) {
    var dialog = dialogs[dialogs.length - 1];
    var result = readRows(dialog);
    if (result.items.length) {
      result._source = 'dialog';
      return JSON.stringify(result);
    }
    // dialog 内没找到有效行 → 检查全页
    console.log('[archive] dialog内有' + result.debug.length + '行样本，cellCounts=' + JSON.stringify(result.debug.map(function(d){return d.cellCount;})));
  }

  // Step 2: 退回全页读取 + 验证过滤（dialog 限定可能因表结构差异失效）
  var pageResult = readRows(document);
  if (pageResult.items.length) {
    pageResult._source = 'page-fallback';
    return JSON.stringify(pageResult);
  }

  pageResult._source = 'none';
  return JSON.stringify(pageResult);
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
          if (raw && raw.items) {
            subItems = raw.items;
          }
          if (raw && raw._source) {
            console.error(`[product-archive] 子品读取来源: ${raw._source}, items=${subItems.length}`);
          }
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
