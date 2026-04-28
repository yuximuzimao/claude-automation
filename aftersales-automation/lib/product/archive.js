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
  // 找包含「精确查询」文字的 li 选项（el-select 下拉列表项），点 li 而非 span
  var li = Array.from(document.querySelectorAll('li.el-select-dropdown__item')).find(function(e){
    var r = e.getBoundingClientRect();
    return e.textContent.trim() === '精确查询' && r.width > 0;
  });
  if (!li) {
    // 降级：找宽度 > 0 的叶子 span
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
    // 找持有 handleQuery 的父 Vue 组件（见 docs/erp-query.md §2 + docs/ops-tech.md #22）
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
// ⚠️ 子商品弹窗关闭按钮类名是 el-dialog__closeBtn，不是标准的 el-dialog__headerbtn
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

// 读子商品明细表格（a.ml_15点击后出现的 el-table__row）
// 列定义: [1]=商品名称, [3]=商家编码(specCode), [10]=组合数量(qty in bundle)
const READ_SUB_ITEMS_JS = `(function(){
  var rows = Array.from(document.querySelectorAll('tr.el-table__row'));
  var items = [];
  rows.forEach(function(r){
    var cells = Array.from(r.querySelectorAll('td')).map(function(td){ return td.innerText.trim(); });
    // 子商品行：cells[1] 为商品名称，cells[3] 为商家编码，cells[10] 为组合数量
    if (cells[1] && cells[3] && cells[10] && !isNaN(parseInt(cells[10]))) {
      items.push({
        name: cells[1],
        specCode: cells[3],
        qty: parseInt(cells[10])
      });
    }
  });
  return JSON.stringify(items.length ? items : {error:'未找到子商品行'});
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
        const raw = await retry(async () => {
          const r = await cdp.eval(targetId, READ_SUB_ITEMS_JS);
          if (r.error) throw new Error(r.error);
          return r;
        }, { maxRetries: 3, delayMs: 1000, label: `read-sub-items ${specCode}` });
        subItems = raw;
      } finally {
        // CLOSE_SUB_DIALOG_JS 内部已处理无弹窗情况（skipped），直接调用即可
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
