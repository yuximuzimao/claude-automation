'use strict';
/**
 * WHAT: ERP 商品对应表查询（货号+attr1→匹配SKU）
 * WHERE: collect.js 商品采集 → CLI product-match 命令 → 此模块
 * WHY: 对应表是确认商品是否有档案的唯一入口，未匹配→无法核对→escalate
 * ENTRY: cli.js: product-match 命令, collect.js: 商品数据采集
 */
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
// 双通道匹配：优先按 label text 匹配，失败时 fallback 按 Vue option value 匹配
// ⚠️ 必须用 cdp.clickAt 物理点击才能触发 el-select mousedown 展开，JS .click() 无效
async function setMainPageSelect(targetId, optionText) {
  // Step 1: 先关闭所有已打开的下拉菜单
  await cdp.eval(targetId, `document.body.click()`);
  await sleep(200);

  // Step 2: 找到目标 select，给它的 input 打标记，再用 cdp.clickAt 物理点击打开
  const js = `(function(){
    var optionText = ${JSON.stringify(optionText)};
    var sels = Array.from(document.querySelectorAll('.el-select')).filter(function(s){
      return !s.closest('.el-dialog__wrapper');
    });
    function trySelect(s, i) {
      var inp = s.querySelector('input');
      if (inp && inp.value === optionText) return JSON.stringify({already: true, idx: i});
      // 给 input 打唯一标记，供外部 cdp.clickAt 定位
      var mark = 'km-sel-' + i + '-' + Date.now();
      if (inp) inp.setAttribute('data-km-mark', mark);
      return JSON.stringify({needClick: true, idx: i, mark: mark});
    }
    // 通道1: label/currentLabel 精确匹配
    for (var i = 0; i < sels.length; i++) {
      var vm = sels[i].__vue__;
      if (!vm || !vm.options) continue;
      var hasOpt = Array.from(vm.options).some(function(o){ return (o.label||o.currentLabel||'') === optionText; });
      if (hasOpt) return trySelect(sels[i], i);
    }
    // 通道2: value fallback
    for (var i = 0; i < sels.length; i++) {
      var vm = sels[i].__vue__;
      if (!vm || !vm.options) continue;
      var hasVal = Array.from(vm.options).some(function(o){ return String(o.value) === optionText; });
      if (hasVal) return trySelect(sels[i], i);
    }
    return JSON.stringify({error:'SELECTOR_BROKEN: 未找到包含选项「' + optionText + '」的 select（text+value 双通道均未命中）'});
  })()`;
  const r = await cdp.eval(targetId, js);
  if (r.error) throw new Error(r.error);
  if (r.already) return;
  // 用物理点击打开 dropdown（JS .click() 不触发 mousedown，el-select 不会展开）
  await cdp.clickAt(targetId, `input[data-km-mark="${r.mark}"]`);
  await sleep(500);

  // Step 3: 在可见的 dropdown 中找到匹配项并点击（只找最近弹出的）
  await cdp.eval(targetId, `(function(){
    var optionText = ${JSON.stringify(optionText)};
    var dropdowns = Array.from(document.querySelectorAll('.el-select-dropdown')).filter(function(d){
      return d.style.display !== 'none' && d.offsetHeight > 0;
    });
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
    // 搜索输入框定位：.el-input-popup-editor（排除 dialog 内的实例）
    var editors = Array.from(document.querySelectorAll('.el-input-popup-editor')).filter(function(e){
      return !e.closest('.el-dialog__wrapper');
    });
    if (!editors.length) return JSON.stringify({error:'SELECTOR_BROKEN: 搜索输入框未找到（.el-input-popup-editor 不存在或全在 dialog 内）'});
    var editor = editors[0];
    var inp = editor.querySelector('input');
    if (!inp) return JSON.stringify({error:'SELECTOR_BROKEN: 搜索输入框内 input 不存在'});
    inp.click(); inp.focus();
    // 使用原生 setter 绕过 Vue el-input 包装，确保响应式触发
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(inp, barcode);
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new Event('change', {bubbles:true}));
    // 验证值已写入
    if (inp.value !== barcode) return JSON.stringify({error:'UI_NOT_READY: 值写入失败，期望:'+barcode+'，实际:'+inp.value});
    // 触发回车搜索
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,bubbles:true}));
    return JSON.stringify({filled: inp.value});
  })()`;
}

// 验证搜索结果：唯一性 + 平台商家编码完全一致
// 多结果时尝试按 td 内容二次过滤（disambiguation），不直接报错死亡
function makeVerifyResultJS(barcode) {
  return `(function(){
    var barcode = ${JSON.stringify(barcode)};
    var parentRows = Array.from(document.querySelectorAll('tr.el-table__row'))
      .filter(function(r){ return r.querySelector('.el-table__expand-icon'); });
    if (parentRows.length === 0) return JSON.stringify({error:'NO_RESULT: 未找到任何结果行'});
    if (parentRows.length > 1) {
      // disambiguation：在多结果中找 td 内容完全等于 barcode 的行
      var exactRows = parentRows.filter(function(r){
        return Array.from(r.querySelectorAll('td')).some(function(td){ return td.innerText.trim() === barcode; });
      });
      if (exactRows.length === 1) return JSON.stringify({verified: true, disambiguated: true, originalCount: parentRows.length});
      if (exactRows.length === 0) return JSON.stringify({error:'MULTIPLE_RESULT: 共' + parentRows.length + '行，且无一行的 td 完全等于 ' + barcode});
      return JSON.stringify({error:'MULTIPLE_RESULT: 共' + parentRows.length + '行，其中' + exactRows.length + '行包含精确匹配，仍不唯一'});
    }
    // 唯一行：验证平台商家编码列完全一致
    var row = parentRows[0];
    var cells = Array.from(row.querySelectorAll('td'));
    var exactMatch = cells.some(function(td){ return td.innerText.trim() === barcode; });
    if (!exactMatch) return JSON.stringify({error:'NO_RESULT: 平台商家编码与搜索值不完全一致，实际行文字: ' + row.innerText.substring(0,100).replace(/\\s+/g,' ')});
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
    // 归一化工具函数
    var toHalf = function(s){ return s.replace(/[\uff01-\uff5e]/g, function(c){ return String.fromCharCode(c.charCodeAt(0)-0xFEE0); }); };
    var stripGift = function(s){ return s.replace(/\\s*赠[^;]*$/, '').trim(); };
    var baseNorm = function(s){ return toHalf(s.replace(/\\s+/g,' ').trim()); };

    // 两轮匹配：第一轮保留完整 attr1，第二轮去赠品后缀
    var candidates = [baseNorm(attr1)];
    var stripped = stripGift(baseNorm(attr1));
    if (stripped !== candidates[0]) candidates.push(stripped);

    var expCells = document.querySelectorAll('.el-table__expanded-cell');
    for (var round = 0; round < candidates.length; round++) {
      var normAttr1 = candidates[round];
      for (var c = 0; c < expCells.length; c++) {
        var tables = expCells[c].querySelectorAll('table');
        for (var t = 0; t < tables.length; t++) {
          var srs = tables[t].querySelectorAll('tbody tr');
          if (!srs.length || srs[0].querySelectorAll('td').length <= 11) continue;
          for (var s = 0; s < srs.length; s++) {
            var sc = srs[s].querySelectorAll('td');
            if (sc.length < 12) continue;
            var skuRaw = baseNorm(sc[4].innerText).split(';')[0].trim();
            if (skuRaw !== normAttr1) continue;
            var ei = sc[11].querySelector('input');
            if (ei && ei.value) return JSON.stringify({specCode: ei.value, searched: attr1, matchedSku: skuRaw, matchRound: round === 0 ? 'exact' : 'stripGift'});
          }
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

    // 设置店铺过滤器：先检测当前店铺，不是目标则切换，切换后再验证。
    // 不信任上次残留状态——因为不同工单可能属于不同店铺。
    // 最多尝试 3 次，3 次仍错必有异常，抛错停止等人工介入。
    await retry(async () => {
      const before = await cdp.eval(targetId, makeCheckShopJS(shopName));
      if (!before.correct) {
        await cdp.eval(targetId, makeSelectShopJS(shopName));
        await sleep(1500); // 等待 Vue 响应式更新
      }
      // 无论是否刚切换，都做后置检测
      const after = await cdp.eval(targetId, makeCheckShopJS(shopName));
      if (!after.correct) throw new Error(`店铺未切换为${shopName}（当前: ${JSON.stringify(after.tags)}）`);
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
      if (rowCount === 0) throw new Error(`NO_RESULT: 搜索无结果（0行），货号 ${barcode}`);
      if (rowCount > 50) throw new Error(`UI_NOT_READY: 搜索返回 ${rowCount} 行（疑似搜索条件未生效），货号 ${barcode}`);
      const hasResult = await cdp.eval(targetId, `document.body.innerText.includes(${JSON.stringify(barcode)})`);
      if (!hasResult) throw new Error(`NO_RESULT: 搜索结果未包含货号 ${barcode}（${rowCount}行中找不到）`);
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
