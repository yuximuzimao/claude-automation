'use strict';
const cdp = require('../cdp');
const { navigateErp } = require('../erp/navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 切换店铺过滤器（见 docs/erp-query.md §1）
// ⚠️ 必须按当前处理账号传入对应店铺名（如「百浩创展」「杭州共途」），不能硬编码
// 用 Vue emit 直接设值（li.click() 不触发 Vue 响应，需绕过）
function makeCheckShopJS(shopName) {
  return `(function(){
  var shopName = ${JSON.stringify(shopName)};
  var wraps = Array.from(document.querySelectorAll('.el-select.select-wrap.support-dialog-select'));
  var shopWrap = wraps.find(function(w){
    var vm = w.__vue__;
    return vm && vm.options && Array.from(vm.options).some(function(o){ return (o.label||o.currentLabel||'').includes(shopName); });
  });
  if (!shopWrap) return JSON.stringify({tags:[], correct:false, error:'shopWrap not found'});
  var t = shopWrap.querySelector('span.el-select__tags-text');
  var tag = t ? t.innerText.trim() : '';
  var correct = tag.includes(shopName) && !tag.includes('已选');
  return JSON.stringify({tags:[tag], correct:correct});
})()`;
}

function makeSelectShopJS(shopName) {
  return `(function(){
  var shopName = ${JSON.stringify(shopName)};
  var wraps = Array.from(document.querySelectorAll('.el-select.select-wrap.support-dialog-select'));
  var shopWrap = wraps.find(function(w){
    var vm = w.__vue__;
    return vm && vm.options && Array.from(vm.options).some(function(o){ return (o.label||o.currentLabel||'').includes(shopName); });
  });
  if (!shopWrap) return JSON.stringify({error:'shopWrap not found'});
  var vm = shopWrap.__vue__;
  var t = shopWrap.querySelector('span.el-select__tags-text');
  if (t && t.innerText.includes(shopName) && !t.innerText.includes('已选')) return 'already set';
  var targetOpt = Array.from(vm.options).find(function(o){ return (o.label||o.currentLabel||'').includes(shopName); });
  if (!targetOpt) return JSON.stringify({error:'option not found: ' + shopName});
  var val = targetOpt.value;
  vm.$emit('input', [val]);
  vm.$emit('change', [val]);
  return JSON.stringify({emitted:true, val:val, shopName:shopName});
})()`;
}

// 在主页 el-select 中设置搜索模式
// 按选项内容定位正确的 select（不依赖固定索引，避免页面结构变化导致设错）
async function setMainPageSelect(targetId, optionText) {
  // Step 1: 先关闭所有已打开的下拉菜单，避免点到错误的 dropdown item
  await cdp.eval(targetId, `document.body.click()`);
  await sleep(200);

  // Step 2: 找到目标 select 并点击打开
  const js = `(function(){
    var optionText = ${JSON.stringify(optionText)};
    var sels = Array.from(document.querySelectorAll('.el-select')).filter(function(s){
      return !s.closest('.el-dialog__wrapper');
    });
    for (var i = 0; i < sels.length; i++) {
      var vm = sels[i].__vue__;
      if (!vm || !vm.options) continue;
      var hasOpt = Array.from(vm.options).some(function(o){ return (o.label||o.currentLabel||'') === optionText; });
      if (!hasOpt) continue;
      var inp = sels[i].querySelector('input');
      if (inp && inp.value === optionText) return JSON.stringify({already: true, idx: i});
      // 记录 select 的位置，用于后续定位正确的 dropdown
      var rect = sels[i].getBoundingClientRect();
      sels[i].click();
      return JSON.stringify({clicked: true, idx: i, top: rect.top, left: rect.left});
    }
    return JSON.stringify({error:'未找到包含选项「' + optionText + '」的 select'});
  })()`;
  const r = await cdp.eval(targetId, js);
  if (r.error) throw new Error(r.error);
  if (r.already) return;
  await sleep(500);

  // Step 3: 在可见的 dropdown 中找到匹配项并点击（只找最近弹出的）
  await cdp.eval(targetId, `(function(){
    var optionText = ${JSON.stringify(optionText)};
    var popper = document.querySelector('.el-select-dropdown__wrap');
    // 找所有可见的 dropdown items（在可见的 popper 容器内）
    var dropdowns = Array.from(document.querySelectorAll('.el-select-dropdown')).filter(function(d){
      return d.style.display !== 'none' && d.offsetHeight > 0;
    });
    // 从最后一个（最新打开的）开始找
    for (var d = dropdowns.length - 1; d >= 0; d--) {
      var items = dropdowns[d].querySelectorAll('.el-select-dropdown__item');
      for (var i = 0; i < items.length; i++) {
        if (items[i].innerText.trim() === optionText && items[i].getBoundingClientRect().height > 0) {
          items[i].click(); return 'clicked:' + optionText;
        }
      }
    }
    return 'not_found';
  })()`);
  await sleep(300);
}

// 确认搜索模式为「精确搜索」+「平台商家编码」
const CHECK_SEARCH_MODE_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner'));
  var hasExact = !!inputs.find(function(i){ return i.value === '精确搜索'; });
  var hasField = !!inputs.find(function(i){ return i.value === '平台商家编码'; });
  return JSON.stringify({hasExact: hasExact, hasField: hasField});
})()`;

function makeSearchBarcodeJS(barcode) {
  return `(function(){
    var barcode = ${JSON.stringify(barcode)};
    // 搜索输入框在 .el-input-popup-editor 内（与 product-mapping 项目一致，非 el-input__inner pivotIdx 方式）
    var editor = document.querySelector('.el-input-popup-editor');
    if (!editor) return JSON.stringify({error:'搜索输入框未找到（.el-input-popup-editor 不存在）'});
    var inp = editor.querySelector('input');
    if (!inp) return JSON.stringify({error:'搜索输入框内 input 不存在'});
    inp.click(); inp.focus();
    // 使用原生 setter 绕过 Vue el-input 包装，确保响应式触发
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(inp, barcode);
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new Event('change', {bubbles:true}));
    // 验证值已写入
    if (inp.value !== barcode) return JSON.stringify({error:'值写入失败，期望:'+barcode+'，实际:'+inp.value});
    // 触发回车搜索
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,bubbles:true}));
    return JSON.stringify({filled: inp.value});
  })()`;
}

// 验证搜索结果：唯一性 + 平台商家编码完全一致
function makeVerifyResultJS(barcode) {
  return `(function(){
    var barcode = ${JSON.stringify(barcode)};
    var parentRows = Array.from(document.querySelectorAll('tr.el-table__row'))
      .filter(function(r){ return r.querySelector('.el-table__expand-icon'); });
    if (parentRows.length === 0) return JSON.stringify({error:'未找到任何结果行'});
    if (parentRows.length > 1) return JSON.stringify({error:'结果不唯一，共' + parentRows.length + '行，精确搜索应只返回1行', count: parentRows.length});
    // 验证平台商家编码列完全一致（td 文字完全等于 barcode）
    var row = parentRows[0];
    var cells = Array.from(row.querySelectorAll('td'));
    var exactMatch = cells.some(function(td){ return td.innerText.trim() === barcode; });
    if (!exactMatch) return JSON.stringify({error:'平台商家编码与搜索值不完全一致，实际行文字: ' + row.innerText.substring(0,100).replace(/\\s+/g,' ')});
    return JSON.stringify({verified: true});
  })()`;
}

// 展开目标行
function makeExpandAndReadJS(barcode) {
  return `(function(){
    var barcode = ${JSON.stringify(barcode)};
    var rows = Array.from(document.querySelectorAll('tr.el-table__row'));
    var targetRow = rows.find(function(r){
      return r.querySelector('.el-table__expand-icon') && r.innerText.includes(barcode);
    });
    if (!targetRow) return JSON.stringify({error:'未找到货号行: ' + barcode});
    if (!targetRow.classList.contains('expanded')) {
      targetRow.querySelector('.el-table__expand-icon').click();
    }
    return JSON.stringify({expanded: true, rowText: targetRow.innerText.substring(0, 200)});
  })()`;
}

function makeReadSpecCodeJS(attr1) {
  return `(function(){
    var attr1 = ${JSON.stringify(attr1)};
    // 归一化：多个空格→单空格，trim
    var normalize = function(s){ return s.replace(/\\s+/g,' ').trim(); };
    var normAttr1 = normalize(attr1);
    // 在展开子表中精确匹配 skuName（td[4]），取 ERP编码 input（td[11]）
    // ERP 对应表 td[4] 格式为 "skuName;店铺简称"（如"防晒*2支 赠防晒口罩*1;悦希"），
    // 取分号前的部分再与 attr1 比较，必须完全相等（不能用 includes）
    // 与 correspondence.js 读取方式保持一致（sc[4]=skuName, sc[11]=erpCode input）
    var expCells = document.querySelectorAll('.el-table__expanded-cell');
    for (var c = 0; c < expCells.length; c++) {
      var tables = expCells[c].querySelectorAll('table');
      for (var t = 0; t < tables.length; t++) {
        var srs = tables[t].querySelectorAll('tbody tr');
        if (!srs.length || srs[0].querySelectorAll('td').length <= 11) continue;
        for (var s = 0; s < srs.length; s++) {
          var sc = srs[s].querySelectorAll('td');
          if (sc.length < 12) continue;
          var skuName = normalize(sc[4].innerText).split(';')[0].trim();
          if (skuName !== normAttr1) continue;
          var ei = sc[11].querySelector('input');
          if (ei && ei.value) return JSON.stringify({specCode: ei.value, searched: attr1, matchedSku: skuName});
        }
      }
    }
    return JSON.stringify({specCode: null, searched: attr1});
  })()`;
}

async function productMatch(targetId, barcode, attr1, shopName) {
  try {
    if (!shopName) throw new Error('必须传入 shopName（如「百浩创展」「杭州共途」），不能省略');

    await navigateErp(targetId, '商品对应表');

    // 设置店铺过滤器（按传入的店铺名切换，不硬编码）
    await retry(async () => {
      const shop = await cdp.eval(targetId, makeCheckShopJS(shopName));
      if (!shop.correct) {
        await cdp.eval(targetId, makeSelectShopJS(shopName));
        await sleep(1500); // 等待 Vue 响应式更新
        const shop2 = await cdp.eval(targetId, makeCheckShopJS(shopName));
        if (!shop2.correct) throw new Error(`店铺未切换为${shopName}: ${JSON.stringify(shop2.tags)}`);
      }
    }, { maxRetries: 3, delayMs: 1500, label: `set shop filter ${shopName}` });
    await sleep(1500); // 过滤器切换后额外等待，确保查询参数生效后再搜索

    // 设置搜索模式为「精确搜索」+「平台商家编码」，然后验证
    await retry(async () => {
      await setMainPageSelect(targetId, '精确搜索');
      await setMainPageSelect(targetId, '平台商家编码');
      const mode = await cdp.eval(targetId, CHECK_SEARCH_MODE_JS);
      if (!mode.hasExact || !mode.hasField) {
        throw new Error(`搜索模式设置失败: hasExact=${mode.hasExact}, hasField=${mode.hasField}`);
      }
    }, { maxRetries: 3, delayMs: 1500, label: `set-search-mode ${barcode}` });

    // 填值搜索（Enter 已在 makeSearchBarcodeJS 内联触发）
    await retry(async () => {
      const fill = await cdp.eval(targetId, makeSearchBarcodeJS(barcode));
      if (fill.error) throw new Error(fill.error);
      await sleep(3500);
      // 检查结果数量：0 行说明搜索无结果，>50 说明搜索条件没生效（返回全量）
      const rowCount = await cdp.eval(targetId,
        `Array.from(document.querySelectorAll('tr.el-table__row')).filter(function(r){return r.querySelector('.el-table__expand-icon')}).length`
      );
      if (rowCount === 0) throw new Error(`搜索无结果（0行），货号 ${barcode}`);
      if (rowCount > 50) throw new Error(`搜索返回 ${rowCount} 行（疑似搜索条件未生效），货号 ${barcode}`);
      const hasResult = await cdp.eval(targetId, `document.body.innerText.includes(${JSON.stringify(barcode)})`);
      if (!hasResult) throw new Error(`搜索结果未包含货号 ${barcode}（${rowCount}行中找不到）`);
    }, { maxRetries: 3, delayMs: 2000, label: `product-match ${barcode}` });

    // ── 验证1：结果唯一性 + 平台商家编码完全一致 ───────────────
    await retry(async () => {
      const verify = await cdp.eval(targetId, makeVerifyResultJS(barcode));
      if (verify.error) throw new Error(`搜索结果验证失败: ${verify.error}`);
    }, { maxRetries: 3, delayMs: 2000, label: `verify-result ${barcode}` });
    await sleep(800);

    // 展开行
    await retry(async () => {
      const expand = await cdp.eval(targetId, makeExpandAndReadJS(barcode));
      if (expand.error) throw new Error(expand.error);
    }, { maxRetries: 3, delayMs: 1500, label: `expand-row ${barcode}` });
    await sleep(2500);

    // 读全部 specCode（用于 attr1="" 或 attr1 匹配失败时回退）
    const readAllCodes = async () => {
      const codes = await cdp.eval(targetId, `(function(){
        var rows = Array.from(document.querySelectorAll('tr'));
        var codes = [];
        rows.forEach(function(r){
          var inputs = r.querySelectorAll('input[type=text]');
          if (inputs[1] && inputs[1].value) codes.push({text: r.innerText.substring(0,50).replace(/\\s+/g,' ').trim(), code: inputs[1].value});
        });
        return JSON.stringify(codes);
      })()`);
      return codes;
    };

    // 读规格商家编码
    if (!attr1) {
      const codes = await readAllCodes();
      return ok({ barcode, specCodes: codes });
    }

    const spec = await retry(async () => {
      const s = await cdp.eval(targetId, makeReadSpecCodeJS(attr1));
      return s;
    }, { maxRetries: 3, delayMs: 1500, label: `read-spec-code ${barcode} ${attr1}` });
    if (!spec.specCode) {
      // attr1 精确匹配失败（命名/空格差异），回退到全量模式
      const codes = await readAllCodes();
      return ok({ barcode, attr1, matched: false, specCodes: codes });
    }

    return ok({ barcode, attr1, specCode: spec.specCode });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { productMatch };
