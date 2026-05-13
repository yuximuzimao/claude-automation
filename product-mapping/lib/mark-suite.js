'use strict';
/**
 * 对应表操作：找到指定 SKU → 勾选 → 套件处理 → 标记套件
 *
 * 用法：node _sandbox/mark-suite.js <店铺名> <货号> <platformCode>
 * 示例：node _sandbox/mark-suite.js 澜泽 0422zp4 260422zp-12
 *
 * ⚠️ 红线：只勾选目标 SKU 那一行，严禁批量勾选整个货号所有子行
 */
const cdp = require('./cdp');
const { navigateErp } = require('./navigate');
const { sleep } = require('./wait');

const ERP_ID = '075D3D5770F69781F17A14C418D00338';

async function main(erpId, shopName, productCode, platformCode) {
  // 直接运行时从命令行参数取
  if (!shopName) [shopName, productCode, platformCode] = process.argv.slice(2);
  if (!shopName || !productCode || !platformCode) {
    console.error('用法: node mark-suite.js <店铺名> <货号> <platformCode>');
    process.exit(1);
  }
  // 被 cli.js 调用时用传入的 erpId，否则用硬编码
  if (!erpId) erpId = ERP_ID;
  console.log(`[mark-suite] 店铺=${shopName} 货号=${productCode} SKU=${platformCode}`);

  // Step1: 导航到商品对应表
  await navigateErp(erpId, '商品对应表');
  await sleep(2000);

  // Step2: 点左侧店铺
  const r1 = await cdp.eval(erpId, `(function(){
    var spans = Array.from(document.querySelectorAll('span'));
    var t = spans.find(function(s){ return s.innerText.trim().includes(${JSON.stringify(shopName)}) && s.className.includes('el-tooltip'); });
    if(!t) return JSON.stringify({error:${JSON.stringify(shopName)} + ' not found'});
    t.click(); return JSON.stringify({clicked: ${JSON.stringify(shopName)}});
  })()`);
  console.log('[shop]', r1);
  if (r1 && r1.error) throw new Error(r1.error);
  await sleep(2000);

  // Step3: 平台商家编码输入框回车刷新
  const r2 = await cdp.eval(erpId,
    '(function(){' +
    '  var inputs = Array.from(document.querySelectorAll("input[type=text],input:not([type])"));' +
    '  var inp = inputs.find(function(i){ return (i.placeholder||"").includes("请输入商家编码"); });' +
    '  if(!inp) return JSON.stringify({error:"搜索输入框不存在"});' +
    '  inp.value="";' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  return JSON.stringify({triggered:true});' +
    '})()'
  );
  console.log('[refresh]', r2);
  await sleep(3000);

  // Step4: 找货号行，展开
  const r3 = await cdp.eval(erpId, `(function(){
    var rows = Array.from(document.querySelectorAll('tr'));
    var target = rows.find(function(r){ return r.innerText.includes(${JSON.stringify(productCode)}); });
    if(!target) return JSON.stringify({error: ${JSON.stringify(productCode)} + ' row not found'});
    var expand = target.querySelector('.el-table__expand-icon, i.el-icon-arrow-right');
    if(!expand) return JSON.stringify({error:'expand icon not found'});
    expand.click(); return JSON.stringify({expanded: ${JSON.stringify(productCode)}});
  })()`);
  console.log('[expand]', r3);
  if (r3 && r3.error) throw new Error(r3.error);
  await sleep(2000);

  // Step5: 只勾选目标 platformCode 那一行（精确匹配 tds[5]，避免前缀误匹配）
  const r4 = await cdp.eval(erpId, `(function(){
    var expCells = document.querySelectorAll('.el-table__expanded-cell');
    for(var c=0;c<expCells.length;c++){
      var rows = expCells[c].querySelectorAll('tbody tr');
      for(var i=0;i<rows.length;i++){
        var tds = rows[i].querySelectorAll('td');
        if(tds.length>=6 && tds[5].innerText.trim()===${JSON.stringify(platformCode)}){
          var cb = rows[i].querySelector('input[type=checkbox]');
          if(!cb) return JSON.stringify({error:'checkbox not found'});
          cb.click(); return JSON.stringify({checked:true, platformCode:${JSON.stringify(platformCode)}});
        }
      }
    }
    return JSON.stringify({error:${JSON.stringify(platformCode)} + ' not found in expanded cells'});
  })()`);
  console.log('[checkbox]', r4);
  if (r4 && r4.error) throw new Error(r4.error);
  await sleep(500);

  // Step6: 点「套件处理」下拉
  const r5 = await cdp.eval(erpId,
    '(function(){' +
    '  var btns = Array.from(document.querySelectorAll("span, button"));' +
    '  var t = btns.find(function(b){ return b.innerText && b.innerText.includes("套件处理") && b.getBoundingClientRect().width > 0; });' +
    '  if(!t) return JSON.stringify({error:"套件处理 not found"});' +
    '  t.click(); return JSON.stringify({clicked:"套件处理"});' +
    '})()'
  );
  console.log('[suite-btn]', r5);
  if (r5 && r5.error) throw new Error(r5.error);
  await sleep(800);

  // Step7: 点「标记套件」
  const r6 = await cdp.eval(erpId,
    '(function(){' +
    '  var items = Array.from(document.querySelectorAll("li.el-dropdown-menu__item"));' +
    '  var t = items.find(function(i){ return i.innerText.trim()==="标记套件"; });' +
    '  if(!t) return JSON.stringify({error:"标记套件 not found"});' +
    '  t.click(); return JSON.stringify({clicked:"标记套件"});' +
    '})()'
  );
  console.log('[mark-suite]', r6);
  if (r6 && r6.error) throw new Error(r6.error);
  await sleep(2000);

  console.log(`[done] ${platformCode} 已标记为套件`);
}

/**
 * 原子操作：在已展开的对应表中，勾选目标 SKU → 套件处理 → 标记套件
 * 调用方须已完成：navigateErp + 点店铺 + 搜索展开
 *
 * @param {string} erpId
 * @param {string} platformCode
 */
async function markOneSuite(erpId, platformCode) {
  // Step5-pre: 清除展开行中所有已勾选状态（只清 tbody tr 内，不碰表头全选框）
  await cdp.eval(erpId,
    '(function(){' +
    '  var cbs=document.querySelectorAll(".el-table__expanded-cell tbody tr input[type=checkbox]:checked");' +
    '  for(var i=0;i<cbs.length;i++){cbs[i].click();}' +
    '})()'
  );
  await sleep(300);

  // Step5: 只勾选目标 platformCode 那一行
  const r4 = await cdp.eval(erpId, `(function(){
    var expCells = document.querySelectorAll('.el-table__expanded-cell');
    for(var c=0;c<expCells.length;c++){
      var rows = expCells[c].querySelectorAll('tbody tr');
      for(var i=0;i<rows.length;i++){
        var tds = rows[i].querySelectorAll('td');
        if(tds.length>=6 && tds[5].innerText.trim()===${JSON.stringify(platformCode)}){
          var cb = rows[i].querySelector('input[type=checkbox]');
          if(!cb) return JSON.stringify({error:'checkbox not found'});
          cb.click(); return JSON.stringify({checked:true, platformCode:${JSON.stringify(platformCode)}});
        }
      }
    }
    return JSON.stringify({error:${JSON.stringify(platformCode)} + ' not found in expanded cells'});
  })()`);
  if (r4 && r4.error) throw new Error(r4.error);

  // 验证只有 1 行被选中（只计 tbody tr，排除表头全选框联动）
  const selectedCount = await cdp.eval(erpId,
    '(function(){return document.querySelectorAll(".el-table__expanded-cell tbody tr input[type=checkbox]:checked").length;})()'
  );
  if (selectedCount !== 1) {
    throw new Error(`markOneSuite: 期望选中 1 行，实际选中 ${selectedCount} 行`);
  }
  await sleep(500);

  // Step6: 点「套件处理」下拉
  const r5 = await cdp.eval(erpId,
    '(function(){' +
    '  var btns = Array.from(document.querySelectorAll("span, button"));' +
    '  var t = btns.find(function(b){ return b.innerText && b.innerText.includes("套件处理") && b.getBoundingClientRect().width > 0; });' +
    '  if(!t) return JSON.stringify({error:"套件处理 not found"});' +
    '  t.click(); return JSON.stringify({clicked:"套件处理"});' +
    '})()'
  );
  if (r5 && r5.error) throw new Error(r5.error);
  await sleep(800);

  // Step7: 点「标记套件」
  const r6 = await cdp.eval(erpId,
    '(function(){' +
    '  var items = Array.from(document.querySelectorAll("li.el-dropdown-menu__item"));' +
    '  var t = items.find(function(i){ return i.innerText.trim()==="标记套件"; });' +
    '  if(!t) return JSON.stringify({error:"标记套件 not found"});' +
    '  t.click(); return JSON.stringify({clicked:"标记套件"});' +
    '})()'
  );
  if (r6 && r6.error) throw new Error(r6.error);
  await sleep(2000);

  console.log(`[markOneSuite] ${platformCode} 已标记为套件`);
}

if (require.main === module) { main().catch(e => { console.error("[ERROR]", e.message); process.exit(1); }); }
module.exports = { main, markOneSuite };
