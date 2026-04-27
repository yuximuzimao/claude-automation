'use strict';
const cdp = require('../cdp');
const { navigateErp } = require('../erp/navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 切换店铺过滤器（见 RULES 4.1 Step 2）
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

// 确认搜索模式为「精确搜索」+「平台商家编码」
const CHECK_SEARCH_MODE_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner'));
  var hasExact = !!inputs.find(function(i){ return i.value === '精确搜索'; });
  var hasField = !!inputs.find(function(i){ return i.value === '平台商家编码'; });
  return JSON.stringify({hasExact: hasExact, hasField: hasField});
})()`;

function makeSearchBarcodeJS(barcode) {
  return `(function(){
    var inputs = Array.from(document.querySelectorAll('input.el-input__inner'));
    var hasField = inputs.find(function(i){ return i.value === '平台商家编码'; });
    if (!hasField) return JSON.stringify({error:'未找到平台商家编码字段'});
    var pivotIdx = inputs.indexOf(hasField);
    var inp = inputs[pivotIdx + 1];
    if (!inp) return JSON.stringify({error:'搜索输入框未找到'});
    inp.click(); inp.focus();
    inp.value = ${JSON.stringify(barcode)};
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new Event('change', {bubbles:true}));
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

    // 验证搜索模式
    await retry(async () => {
      const mode = await cdp.eval(targetId, CHECK_SEARCH_MODE_JS);
      if (!mode.hasExact || !mode.hasField) {
        throw new Error(`搜索模式不正确: hasExact=${mode.hasExact}, hasField=${mode.hasField}，请手动设置为「精确搜索」+「平台商家编码」`);
      }
    }, { maxRetries: 3, delayMs: 1000, label: `check-search-mode ${barcode}` });

    // 填值搜索
    await retry(async () => {
      const fill = await cdp.eval(targetId, makeSearchBarcodeJS(barcode));
      if (fill.error) throw new Error(fill.error);
      await cdp.key(targetId, 'Enter');
      await sleep(3500);
      const hasResult = await cdp.eval(targetId, `document.body.innerText.includes(${JSON.stringify(barcode)})`);
      if (!hasResult) throw new Error(`搜索结果未包含货号 ${barcode}`);
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
