'use strict';
/**
 * 自动匹配 v2：
 * Phase 1 - 组合装：
 *   a+b. 逐页展开+勾选所有未匹配组合装 SKU（当前页处理，翻页继续）
 *   c. 套件处理 → 标记套件（一次性）
 *   d. 逐个点「复制为套件」→ 填子品 → 确认（串行）
 * Phase 2 - 单品：
 *   逐个 remapSku（串行）
 */

const path = require('path');
const fs = require('fs');
const cdp = require('./cdp');
const { sleep } = require('./wait');
const { navigateErp } = require('./navigate');
const { remapSku } = require('./remap-sku');
const { addProductToDialog, confirmDialog } = require('./copy-as-suite');

const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');
const LOG_PATH = path.join(__dirname, '../data/auto-match-log.json');

function loadLog() {
  if (!fs.existsSync(LOG_PATH)) return { done: [], failed: [] };
  return JSON.parse(fs.readFileSync(LOG_PATH, 'utf8'));
}
function saveLog(log) { fs.writeFileSync(LOG_PATH, JSON.stringify(log, null, 2)); }

function getTodo(shopName) {
  const raw = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  // check.js 全量重写后是纯平铺 {platformCode→rec}；兼容旧的 {skus:{...}} 包装格式
  const records = (raw.skus && typeof raw.skus === 'object') ? raw.skus : raw;
  const log = loadLog();
  const done = new Set(log.done);
  return Object.values(records).filter(r =>
    r && typeof r === 'object' &&
    r.shopName === shopName &&
    !r.erpCode &&
    r.recognition && r.recognition.items && r.recognition.items.length > 0 &&
    !done.has(r.platformCode)
  );
}

// ── Phase 1a+b：处理当前页的展开+勾选 ──
async function processCurrentPage(erpId, productCodes, platformCodes) {
  const codes = JSON.stringify(productCodes);
  const pCodes = JSON.stringify(platformCodes);

  // 展开当前页中匹配的货号行
  const expandResult = await cdp.eval(erpId,
    '(function(){' +
    '  var codes=' + codes + ';' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  var expanded=0;' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds=rows[i].querySelectorAll("td");' +
    '    var code=tds[6]?tds[6].innerText.trim():"";' +
    '    if(codes.indexOf(code)<0) continue;' +
    '    var icon=rows[i].querySelector(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
    '    if(icon){icon.click();expanded++;}' +
    '  }' +
    '  return expanded;' +
    '})()'
  );
  console.error('[process-page] 展开了', expandResult, '个货号行');
  if (expandResult > 0) await sleep(2000);

  // 勾选当前页展开行中的目标 SKU
  const checkResult = await cdp.eval(erpId,
    '(function(){' +
    '  var targets=new Set(' + pCodes + ');' +
    '  var expCells=document.querySelectorAll(".el-table__expanded-cell");' +
    '  var checked=0, notFound=[];' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows=expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds=rows[i].querySelectorAll("td");' +
    '      if(tds.length<6) continue;' +
    '      var pCode=tds[5].innerText.trim();' +
    '      if(!targets.has(pCode)) continue;' +
    '      var cb=rows[i].querySelector("input[type=checkbox]");' +
    '      if(cb){cb.click();checked++;}' +
    '      else notFound.push(pCode);' +
    '    }' +
    '  }' +
    '  return JSON.stringify({checked:checked,notFound:notFound});' +
    '})()'
  );
  const r = typeof checkResult === 'string' ? JSON.parse(checkResult) : checkResult;
  console.error('[process-page] 勾选:', r.checked, '未找到:', r.notFound);
  return r;
}

// ── 分页辅助 ──
async function hasNextPage(erpId) {
  const result = await cdp.eval(erpId,
    '(function(){' +
    '  var btns=document.querySelectorAll(".el-pagination .btn-next");' +
    '  if(!btns.length) return false;' +
    '  var btn=btns[btns.length-1];' +
    '  return !btn.disabled && btn.getBoundingClientRect().width>0;' +
    '})()'
  );
  return !!result;
}

async function clickNextPage(erpId) {
  await cdp.eval(erpId,
    '(function(){' +
    '  var btns=document.querySelectorAll(".el-pagination .btn-next");' +
    '  if(btns.length) btns[btns.length-1].click();' +
    '})()'
  );
  await sleep(2000);
}

// ── Phase 1b：点套件处理 → 标记套件 ──
async function clickMarkSuite(erpId) {
  await cdp.eval(erpId,
    '(function(){' +
    '  var btns=Array.from(document.querySelectorAll("span,button"));' +
    '  var t=btns.find(function(b){return b.innerText&&b.innerText.includes("套件处理")&&b.getBoundingClientRect().width>0;});' +
    '  if(t) t.click();' +
    '})()'
  );
  await sleep(800);
  await cdp.eval(erpId,
    '(function(){' +
    '  var items=Array.from(document.querySelectorAll("li.el-dropdown-menu__item"));' +
    '  var t=items.find(function(i){return i.innerText.trim()==="标记套件";});' +
    '  if(t) t.click();' +
    '})()'
  );
  await sleep(2000);
  console.error('[mark-suite] 标记套件完成');
}

// ── Phase 1c：逐个复制为套件（不离开当前页，用搜索框过滤） ──
async function closeSelectDialogIfOpen(erpId) {
  // 点关闭/取消
  const found = await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<ds.length;i++){' +
    '    var d=ds[i];' +
    '    if(d.getBoundingClientRect().height<=0)continue;' +
    '    var t=d.querySelector(".el-dialog__title");' +
    '    if(!t||t.innerText.trim()!=="选择商品")continue;' +
    '    var btns=Array.from(d.querySelectorAll("button"));' +
    '    var cancel=btns.find(function(b){var s=b.querySelector("span");return s&&(s.innerText.trim()==="取消"||s.innerText.trim()==="关闭");});' +
    '    if(cancel){cancel.click();}' +
    '    else{var close=d.querySelector(".el-dialog__headerbtn");if(close)close.click();}' +
    '    return true;' +
    '  }' +
    '  return false;' +
    '})()'
  );
  if (!found) return;
  // 等 dialog 高度真正归零（最多等 3s）
  for (let i = 0; i < 6; i++) {
    await sleep(500);
    const gone = await cdp.eval(erpId,
      '(function(){' +
      '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
      '  for(var i=0;i<ds.length;i++){' +
      '    var t=ds[i].querySelector(".el-dialog__title");' +
      '    if(t&&t.innerText.trim()==="选择商品"&&ds[i].getBoundingClientRect().height>0)return false;' +
      '  }' +
      '  return true;' +
      '})()'
    );
    if (gone) return;
  }
}

async function copyOneSku(erpId, shopName, productCode, platformCode, products) {
  // 先关掉上次失败残留的弹窗（如有）
  await closeSelectDialogIfOpen(erpId);
  await sleep(300);

  // 搜索货号过滤表格（用 .el-input-popup-editor input，无 placeholder，INDEX.md §5）
  await cdp.eval(erpId,
    '(function(){' +
    '  var inp=document.querySelector(".el-input-popup-editor input");' +
    '  if(!inp) return;' +
    '  inp.value=' + JSON.stringify(productCode) + ';' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '})()'
  );
  await sleep(2000);

  // 展开目标货号行（精确匹配）
  await cdp.eval(erpId,
    '(function(){' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds=rows[i].querySelectorAll("td");' +
    '    if(tds[6]&&tds[6].innerText.trim()===' + JSON.stringify(productCode) + '){' +
    '      var icon=rows[i].querySelector(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
    '      if(icon) icon.click();' +
    '      return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(1500);

  // 点复制为套件（精确匹配 tds[5]）
  const r = await cdp.eval(erpId,
    '(function(){' +
    '  var expCells=document.querySelectorAll(".el-table__expanded-cell");' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows=expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds=rows[i].querySelectorAll("td");' +
    '      if(tds.length>=6&&tds[5].innerText.trim()===' + JSON.stringify(platformCode) + '){' +
    '        var links=Array.from(rows[i].querySelectorAll("a"));' +
    '        var btn=links.find(function(a){return a.innerText.trim()==="复制为套件";});' +
    '        if(!btn) return "no-btn";' +
    '        btn.click(); return "clicked";' +
    '      }' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (r !== 'clicked') throw new Error(`复制为套件 not found for ${platformCode}: ${r}`);
  await sleep(1500);

  // 验证弹窗
  const title = await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0){var t=ds[i].querySelector(".el-dialog__title");return t?t.innerText:"no-title";}}' +
    '  return "no-dialog";' +
    '})()'
  );
  if (!title.includes('选择商品')) throw new Error(`Expected 选择商品 dialog, got: ${title}`);

  // 取消勾选 dialog 内所有已选中的 checkbox（防止 Vue 组件保留上次的选中状态）
  await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<ds.length;i++){' +
    '    if(ds[i].getBoundingClientRect().height<=0)continue;' +
    '    var cbs=ds[i].querySelectorAll("input[type=checkbox]:checked");' +
    '    for(var j=0;j<cbs.length;j++){cbs[j].click();}' +
    '    return;' +
    '  }' +
    '})()'
  );
  await sleep(300);

  // 清空主商家编码输入框（防止残留内容干扰搜索，不点清空按钮避免触发全量刷新）
  await cdp.eval(erpId,
    '(function(){' +
    '  var FIND_SELECT_DIALOG=' + JSON.stringify(
      'Array.from(document.querySelectorAll(\'.el-dialog__wrapper\')).find(function(d){' +
      'var t=d.querySelector(\'.el-dialog__title\');' +
      'return t&&t.innerText.trim()===\'选择商品\'&&d.getBoundingClientRect().height>0;})'
    ) + ';' +
    '  var w=eval(FIND_SELECT_DIALOG);' +
    '  if(!w)return;' +
    '  var inputs=Array.from(w.querySelectorAll("input[type=text],input:not([type])"));' +
    '  inputs.forEach(function(inp){' +
    '    if(inp.getAttribute("role")==="spinbutton")return;' +
    '    if(inp.placeholder&&inp.placeholder.includes("商品名称"))return;' +
    '    inp.value="";' +
    '    inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  });' +
    '})()'
  );
  await sleep(300);

  // 选择商品类型为「普通商品(包含组合/加工)」（直接设 Vue 实例值，不打开 dropdown 避免触发 close-on-click-modal）
  await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<ds.length;i++){' +
    '    if(ds[i].getBoundingClientRect().height<=0)continue;' +
    '    var t=ds[i].querySelector(".el-dialog__title");' +
    '    if(!t||t.innerText.trim()!=="选择商品")continue;' +
    '    var selects=Array.from(ds[i].querySelectorAll(".el-select"));' +
    '    for(var j=0;j<selects.length;j++){' +
    '      var vm=selects[j].__vue__;' +
    '      if(!vm)continue;' +
    '      var opts=(vm.$children||[]).filter(function(c){return c.$options&&c.$options.name==="ElOption";});' +
    '      var target=opts.find(function(o){return (o.label||"").includes("普通商品");});' +
    '      if(target){vm.$emit("input",target.value);vm.$emit("change",target.value);}' +
    '      return;' +
    '    }' +
    '    return;' +
    '  }' +
    '})()'
  );
  await sleep(300);

  // 逐个添加子品
  for (let i = 0; i < products.length; i++) {
    const p = products[i];
    console.error(`  [${i + 1}/${products.length}] ${p.name}×${p.qty}`);
    await addProductToDialog(erpId, p.name, p.qty, i + 1);
  }

  // 确认
  await confirmDialog(erpId);
  console.error(`[copy] ${platformCode} 完成`);
}

async function main(erpId, shopName = '澜泽', limit = Infinity) {
  const log = loadLog();
  // 每次新任务开始前清空 failed[]，避免历史失败记录干扰本次统计和排查
  log.failed = [];
  saveLog(log);

  const todo = getTodo(shopName);
  const bundles = todo.filter(r => r.recognition.type === '组合装').slice(0, limit);
  const singles = todo.filter(r => r.recognition.type === '单品').slice(0, bundles.length < limit ? limit - bundles.length : 0);

  console.error(`[auto-match2] 组合装: ${bundles.length}, 单品: ${singles.length}`);

  // ══ Phase 1：组合装（每个 bundle 独立走：搜索→勾选→标记套件→复制为套件）══
  if (bundles.length > 0) {
    await navigateErp(erpId, '商品对应表');

    for (let i = 0; i < bundles.length; i++) {
      const r = bundles[i];
      console.error(`\n── Phase 1 [${i + 1}/${bundles.length}] ${r.platformCode} ──`);

      // Step A: 用货号搜索，定位到目标行所在页
      await cdp.eval(erpId,
        '(function(){' +
        '  var inp=document.querySelector(".el-input-popup-editor input");' +
        '  if(!inp) return;' +
        '  inp.value=' + JSON.stringify(r.productCode) + ';' +
        '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
        '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
        '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
        '})()'
      );
      await sleep(2000);

      // Step B: 展开目标货号行并勾选目标 SKU（只在当前页操作，不翻页）
      const pageResult = await processCurrentPage(erpId, [r.productCode], [r.platformCode]);
      if (pageResult.checked === 0) {
        const err = `展开+勾选失败: productCode=${r.productCode} platformCode=${r.platformCode}`;
        log.failed.push({ platformCode: r.platformCode, type: '组合装', error: err, time: new Date().toISOString() });
        saveLog(log);
        throw new Error(err);
      }
      console.error(`[Phase1] 勾选成功，立即标记套件`);

      // Step C: 标记套件（在当前页勾选状态未丢失时立即执行）
      console.error(`\n── Phase 1c：套件处理 → 标记套件 ──`);
      await sleep(500);
      await clickMarkSuite(erpId);

      // Step D: 复制为套件
      console.error(`\n── Phase 1d：复制为套件 ──`);
      try {
        await copyOneSku(erpId, shopName, r.productCode, r.platformCode,
          r.recognition.items.map(it => ({ name: it.name, qty: it.qty })));
        log.done.push(r.platformCode);
        saveLog(log);
      } catch (e) {
        console.error(`[${r.platformCode}] ❌ ${e.message}`);
        log.failed.push({ platformCode: r.platformCode, type: '组合装', error: e.message, time: new Date().toISOString() });
        saveLog(log);
        console.error(`\n[STOP] 匹配异常，已停止。已完成: ${log.done.length}, 失败: ${log.failed.length}`);
        console.error(`[STOP] 失败 SKU: ${r.platformCode}, 原因: ${e.message}`);
        console.error('[STOP] 请人工处理后重跑（已完成的 SKU 会自动跳过）');
        throw e;
      }
    }
  }

  // ══ Phase 2：单品 ══
  console.error(`\n── Phase 2：单品 ${singles.length} 个 ──`);
  for (let i = 0; i < singles.length; i++) {
    const r = singles[i];
    const erpName = r.recognition.items[0].name;
    console.error(`[${i + 1}/${singles.length}] ${r.platformCode} → ${erpName}`);
    try {
      await remapSku(erpId, r.platformCode, erpName, { confirm: true });
      log.done.push(r.platformCode);
      saveLog(log);
      console.error(`[${r.platformCode}] ✅`);
    } catch (e) {
      console.error(`[${r.platformCode}] ❌ ${e.message}`);
      log.failed.push({ platformCode: r.platformCode, type: '单品', error: e.message, time: new Date().toISOString() });
      saveLog(log);
      console.error(`\n[STOP] 匹配异常，已停止。已完成: ${log.done.length}, 失败: ${log.failed.length}`);
      console.error(`[STOP] 失败 SKU: ${r.platformCode}, 原因: ${e.message}`);
      console.error('[STOP] 请人工处理后重跑（已完成的 SKU 会自动跳过）');
      throw e;
    }
    await sleep(2000);
  }

  console.error(`\n[完成] done=${log.done.length} failed=${log.failed.length}`);
  if (log.failed.length) {
    console.error('失败列表:');
    log.failed.forEach(f => console.error(`  ${f.platformCode}: ${f.error}`));
  }
}

module.exports = { main };

if (require.main === module) {
  console.error('请使用 cli.js 调用: node cli.js match --shop <店铺> [--limit N]');
  process.exit(1);
}
