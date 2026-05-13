'use strict';
/**
 * 复制为套件：在「选择商品」弹窗中逐一搜索子品、勾选、填数量，最后确定
 *
 * 调用时机：mark-suite 完成后（目标行已出现「复制为套件」按钮）
 *
 * 用法：node lib/copy-as-suite.js <店铺> <货号> <platformCode> <子品JSON>
 * 子品JSON示例：'[{"name":"KGOS益生菌固体饮料 2g*15","qty":6},{"name":"KGOS手提保温壶","qty":1}]'
 *
 * ⚠️ 红线：
 *   1. 点击「复制为套件」前必须确认目标行存在该按钮（mark-suite 已完成）
 *   2. 每加完一个子品必须读底部计数验证，不一致则报错
 *   3. 确定按钮：找所有 .el-dialog__footer，取 getBoundingClientRect().height > 0 的那个
 *      不能用文字匹配（innerText 有时带空格）
 */
const cdp = require('./cdp');
const { navigateErp } = require('./navigate');
const { sleep } = require('./wait');

// JS 表达式：找标题匹配且可见（height > 0）的弹窗 wrapper
const FIND_SELECT_DIALOG =
  'Array.from(document.querySelectorAll(\'.el-dialog__wrapper\')).find(function(d){' +
  'var t=d.querySelector(\'.el-dialog__title\');' +
  'return t&&t.innerText.trim()===\'选择商品\'&&d.getBoundingClientRect().height>0;})';

const FIND_REBIND_DIALOG =
  'Array.from(document.querySelectorAll(\'.el-dialog__wrapper\')).find(function(d){' +
  'var t=d.querySelector(\'.el-dialog__title\');' +
  'return t&&t.innerText.trim()===\'换对应商品\'&&d.getBoundingClientRect().height>0;})';

async function clickCopyAsSuite(erpId, platformCode) {
  const r = await cdp.eval(erpId, `(function(){
    var expCells = document.querySelectorAll('.el-table__expanded-cell');
    for(var c=0;c<expCells.length;c++){
      var rows = expCells[c].querySelectorAll('tbody tr');
      for(var i=0;i<rows.length;i++){
        var tds = rows[i].querySelectorAll('td');
        if(tds.length>=6 && tds[5].innerText.trim()===${JSON.stringify(platformCode)}){
          var links = Array.from(rows[i].querySelectorAll('a'));
          var btn = links.find(function(a){ return a.innerText.trim() === '复制为套件'; });
          if(!btn) return JSON.stringify({error:'复制为套件 not found', btns: links.map(function(a){return a.innerText;})});
          btn.click();
          return JSON.stringify({clicked:'复制为套件'});
        }
      }
    }
    return JSON.stringify({error:${JSON.stringify(platformCode)} + ' not found in expanded cells'});
  })()`);
  return r;
}

async function addProductToDialog(erpId, productName, amount, expectedCount) {
  // 前置验证：弹窗必须可见
  const r0 = await cdp.eval(erpId,
    `(function(){var w=${FIND_SELECT_DIALOG};` +
    `if(!w)return JSON.stringify({error:'选择商品 dialog not visible'});` +
    `return JSON.stringify({ok:true});})()`,
  );
  if (r0 && r0.error) throw new Error(`操作前验证失败：${r0.error}`);

  // 搜索商品名称（限定在弹窗内，只发 input + Enter）
  const r1 = await cdp.eval(erpId, `(function(){
    var w = ${FIND_SELECT_DIALOG};
    if(!w) return JSON.stringify({error:'dialog gone'});
    var inp = w.querySelector('input[placeholder="商品名称"]');
    if(!inp) return JSON.stringify({error:'商品名称 input not found'});
    inp.value = ${JSON.stringify(productName)};
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));
    return JSON.stringify({searched: ${JSON.stringify(productName)}});
  })()`);
  if (r1 && r1.error) throw new Error(r1.error);

  // 等待搜索结果刷新为目标商品（最多等 10s，每 1s 检查一次）
  // 用完整商品名验证，防止相近名称误判
  let r2;
  for (let attempt = 0; attempt < 10; attempt++) {
    await sleep(1000);
    r2 = await cdp.eval(erpId,
      `(function(){var w=${FIND_SELECT_DIALOG};` +
      `if(!w)return JSON.stringify({error:'dialog gone'});` +
      `var pName=${JSON.stringify(productName)};` +
      `var rows=Array.from(w.querySelectorAll('tbody tr'));` +
      `var first=rows[0]?rows[0].innerText.replace(/\\t+/g,' ').trim().substring(0,120):'';` +
      `var hasExact=rows.some(function(r){` +
      `  return Array.from(r.querySelectorAll('td')).some(function(td){return td.innerText.trim()===pName;});` +
      `});` +
      `return JSON.stringify({count:rows.length,first:first,hasExact:hasExact});` +
      `})()`,
    );
    if (!r2 || r2.error) throw new Error(r2 ? r2.error : '读取结果失败');
    if ((r2.count === 1 && r2.first.includes(productName)) || r2.hasExact) break;
    r2 = null; // 结果未就绪，继续等
  }
  if (!r2) throw new Error(`搜索「${productName}」超时`);
  if (r2.count === 0) throw new Error(`搜索「${productName}」无结果`);
  if (r2.count !== 1 && !r2.hasExact) throw new Error(`搜索「${productName}」返回 ${r2.count} 条结果，无精确匹配行，请修正名称后重试`);
  console.log(`  搜索结果 ${r2.count} 条，首行: ${r2.first}`);
  await sleep(500); // 结果已刷新，等 UI 稳定再操作

  // 找精确匹配商品名的行（防止多结果时误选套件），无精确匹配才退化到第一行
  const r3 = await cdp.eval(erpId,
    `(function(){var w=${FIND_SELECT_DIALOG};` +
    `var pName=${JSON.stringify(productName)};` +
    `var rows=Array.from(w.querySelectorAll('tbody tr'));` +
    `var target=rows.find(function(r){` +
    `  var tds=Array.from(r.querySelectorAll('td'));` +
    `  return tds.some(function(td){return td.innerText.trim()===pName;});` +
    `})||rows[0];` +
    `if(!target)return JSON.stringify({error:'no rows'});` +
    `var cb=target.querySelector('input[type=checkbox]');` +
    `if(!cb)return JSON.stringify({error:'checkbox not found'});` +
    `cb.click();return JSON.stringify({checked:cb.checked});` +
    `})()`,
  );
  if (r3 && r3.error) throw new Error(r3.error);
  await sleep(500);

  // 填数量（限定在弹窗内的 spinbutton）
  const r4 = await cdp.eval(erpId, `(function(){
    var w = ${FIND_SELECT_DIALOG};
    if(!w) return JSON.stringify({error:'dialog gone'});
    var qtyEl = w.querySelector('input[role=spinbutton]');
    if(!qtyEl) return JSON.stringify({error:'spinbutton not found'});
    qtyEl.focus();
    qtyEl.value = ${JSON.stringify(String(amount))};
    qtyEl.dispatchEvent(new Event('input', {bubbles:true}));
    qtyEl.dispatchEvent(new Event('change', {bubbles:true}));
    return JSON.stringify({ok:true, value:qtyEl.value});
  })()`);
  if (r4 && r4.error) throw new Error(r4.error);
  console.log(`  [qty] ${r4 && r4.value}`);
  await sleep(300);

  // 读底部计数验证（已选种类数必须 = expectedCount）
  const r5 = await cdp.eval(erpId,
    `(function(){var w=${FIND_SELECT_DIALOG};` +
    `var m=w.innerText.match(/已选择商品：\\s*(\\d+)/);` +
    `return JSON.stringify({kinds:m?parseInt(m[1]):-1});` +
    `})()`,
  );
  if (!r5 || r5.kinds !== expectedCount) {
    throw new Error(`已选商品数验证失败：期望 ${expectedCount}，实际 ${r5 ? r5.kinds : 'N/A'}`);
  }
  return { productName, amount, kinds: r5.kinds };
}

async function confirmDialog(erpId) {
  // 找所有 footer，取 getBoundingClientRect().height > 0 的那个，点 el-button--primary
  const r = await cdp.eval(erpId,
    `(function(){var w=${FIND_SELECT_DIALOG};` +
    `if(!w)return JSON.stringify({error:'dialog not found'});` +
    `var footers=Array.from(w.querySelectorAll('.el-dialog__footer'));` +
    `var vf=footers.find(function(f){return f.getBoundingClientRect().height>0;});` +
    `if(!vf)return JSON.stringify({error:'no visible footer'});` +
    `var btn=vf.querySelector('button.el-button--primary');` +
    `if(!btn)return JSON.stringify({error:'primary button not found'});` +
    `btn.click();return JSON.stringify({clicked:true});` +
    `})()`,
  );
  if (r && r.error) throw new Error(r.error);
  await sleep(2000);

  // 验证「选择商品」弹窗关闭（此处不加 height 检测：需要找到 wrapper 来确认它已变为 height=0）
  const r2 = await cdp.eval(erpId, `(function(){
    var w = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      return (w.querySelector('.el-dialog__title')||{}).innerText === '选择商品';
    });
    if(!w) return JSON.stringify({closed:true});
    return JSON.stringify({closed: w.getBoundingClientRect().height === 0});
  })()`);
  if (!r2 || !r2.closed) throw new Error('点确定后弹窗未关闭');

  // 检查是否出现「换对应商品」弹窗（已有同比例套件时触发）
  const r3 = await cdp.eval(erpId,
    `(function(){var w=${FIND_REBIND_DIALOG};` +
    `if(!w)return JSON.stringify({appeared:false});` +
    `var rows=Array.from(w.querySelectorAll('tbody tr'));` +
    `var info=rows.slice(0,3).map(function(r){return r.innerText.replace(/\\t+/g,' ').trim().substring(0,80);});` +
    `return JSON.stringify({appeared:true,rows:info});` +
    `})()`,
  );
  console.log('[换对应商品 check]', r3);

  if (r3 && r3.appeared) {
    // 点 radio 选中第一条，再点确定
    const r4 = await cdp.eval(erpId,
      `(function(){var w=${FIND_REBIND_DIALOG};` +
      `var radio=w.querySelector('input[type=radio].el-radio__original');` +
      `if(!radio)return JSON.stringify({error:'radio not found'});` +
      `radio.click();` +
      `var label=radio.closest('.el-radio');` +
      `if(label)label.click();` +
      `return JSON.stringify({selected:true});` +
      `})()`,
    );
    console.log('[换对应商品 select]', r4);
    if (r4 && r4.error) throw new Error(r4.error);
    await sleep(300);

    const r5 = await cdp.eval(erpId,
      `(function(){var w=${FIND_REBIND_DIALOG};` +
      `var footers=Array.from(w.querySelectorAll('.el-dialog__footer'));` +
      `var vf=footers.find(function(f){return f.getBoundingClientRect().height>0;});` +
      `if(!vf)return JSON.stringify({error:'no visible footer'});` +
      `var btn=vf.querySelector('button.el-button--primary');` +
      `if(!btn)return JSON.stringify({error:'no primary btn'});` +
      `btn.click();return JSON.stringify({clicked:btn.innerText.trim()});` +
      `})()`,
    );
    console.log('[换对应商品 confirm]', r5);
    if (r5 && r5.error) throw new Error(r5.error);
    await sleep(2000);
    console.log('[换对应商品] 已换绑已有套件商品');
    return { mode: 'rebind' };
  }

  return { mode: 'new' };
}

async function main(erpId, shopName, productCode, platformCode, products) {
  // 被 cli.js 调用时传参，否则从命令行读
  if (!shopName) {
    [shopName, productCode, platformCode] = process.argv.slice(2, 5);
    products = JSON.parse(process.argv[5] || '[]');
  }
  if (!erpId) erpId = '075D3D5770F69781F17A14C418D00338';
  if (!products || !products.length) {
    console.error('用法: node copy-as-suite.js <店铺> <货号> <platformCode> \'[{"name":"...","qty":N}]\'');
    process.exit(1);
  }

  console.log(`[copy-as-suite] 店铺=${shopName} 货号=${productCode} SKU=${platformCode}`);
  console.log(`[copy-as-suite] 子品 ${products.length} 个:`, products.map(p => `${p.name}×${p.qty}`).join(', '));

  // Step1: 导航到商品对应表（必须 reload，防脏数据）
  await navigateErp(erpId, '商品对应表');
  await sleep(2000);

  // Step2: 点店铺
  const r1 = await cdp.eval(erpId, `(function(){
    var spans = Array.from(document.querySelectorAll('span'));
    var t = spans.find(function(s){ return s.innerText.trim().includes(${JSON.stringify(shopName)}) && s.className.includes('el-tooltip'); });
    if(!t) return JSON.stringify({error:${JSON.stringify(shopName)} + ' not found'});
    t.click(); return JSON.stringify({clicked:${JSON.stringify(shopName)}});
  })()`);
  console.log('[shop]', r1);
  if (r1 && r1.error) throw new Error(r1.error);
  await sleep(2000);

  // Step3: 刷新列表（空搜索回车）
  await cdp.eval(erpId,
    '(function(){' +
    '  var inputs = Array.from(document.querySelectorAll("input[type=text],input:not([type])"));' +
    '  var inp = inputs.find(function(i){ return (i.placeholder||"").includes("请输入商家编码"); });' +
    '  if(!inp) return;' +
    '  inp.value="";' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '})()'
  );
  await sleep(3000);

  // Step4: 展开货号行（精确匹配 tds[6]）
  const r3 = await cdp.eval(erpId, `(function(){
    var rows = Array.from(document.querySelectorAll('.el-table__body-wrapper .el-table__body tbody tr.el-table__row'));
    var target = rows.find(function(r){ var tds=r.querySelectorAll('td'); return tds[6]&&tds[6].innerText.trim()===${JSON.stringify(productCode)}; });
    if(!target) return JSON.stringify({error:${JSON.stringify(productCode)} + ' row not found'});
    var expand = target.querySelector('.el-table__expand-icon:not(.el-table__expand-icon--expanded)');
    if(!expand) return JSON.stringify({error:'expand icon not found'});
    expand.click(); return JSON.stringify({expanded:${JSON.stringify(productCode)}});
  })()`);
  console.log('[expand]', r3);
  if (r3 && r3.error) throw new Error(r3.error);
  await sleep(2000);

  // Step5: 点「复制为套件」
  const r4 = await clickCopyAsSuite(erpId, platformCode);
  console.log('[copy-as-suite btn]', r4);
  if (r4 && r4.error) throw new Error(r4.error);
  await sleep(1500);

  // Step6: 逐一添加子品
  for (let i = 0; i < products.length; i++) {
    const p = products[i];
    console.log(`[product ${i + 1}/${products.length}] 添加 ${p.name} × ${p.qty}`);
    const result = await addProductToDialog(erpId, p.name, p.qty, i + 1);
    console.log(`[product ${i + 1}] 已选种类=${result.kinds} ✓`);
  }

  // Step7: 点确定（可见 footer 的 primary 按钮）
  await confirmDialog(erpId);
  console.log(`[done] ${platformCode} 套件子品配置完成，共 ${products.length} 种商品`);
}

if (require.main === module) { main().catch(e => { console.error('[ERROR]', e.message); process.exit(1); }); }
module.exports = { main, addProductToDialog, confirmDialog };
