'use strict';
/**
 * 分支 B：套件标记+复制（matchStatus=unmatched, itemType=suite）
 *
 * 三层保护：
 * 1. 执行前幂等检查（已有正确 erpCode → 跳过）
 * 2. 执行中单选确认（DOM 验证勾选数 = 1）
 * 3. 执行后验证（erpCode 已生成）
 *
 * 成功后立即更新 matchStatus=matched-ai（让 while 循环不重复处理）
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');
const { sleep } = require('../wait');
const { ensureCorrPage } = require('./ensure-corr-page');
const { navigateErp } = require('../navigate');

const SESSION_CACHE_PATH = path.join(__dirname, '../../data/erp-session-cache.json');
const { markOneSuite } = require('../mark-suite');
const { addProductToDialog, confirmDialog } = require('../copy-as-suite');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * 搜索并展开指定货号（套件流程自己管导航）
 */
async function _searchAndExpand(erpId, shopName, productCode) {
  // 点左侧店铺
  const shopClicked = await cdp.eval(erpId,
    '(function(){' +
    '  var spans=document.querySelectorAll("span");' +
    '  for(var i=0;i<spans.length;i++){' +
    '    if(spans[i].innerText.trim().includes(' + JSON.stringify(shopName) + ')&&spans[i].className.includes("el-tooltip")){' +
    '      spans[i].click();return "clicked";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (shopClicked !== 'clicked') throw new Error(`左侧店铺「${shopName}」未找到`);
  await sleep(1500);

  // 输入货号 + 回车（搜索输入框在 el-input-popup-editor 内）
  const inputResult = await cdp.eval(erpId,
    '(function(){' +
    '  var editor=document.querySelector(".el-input-popup-editor");' +
    '  if(!editor) return "editor-not-found";' +
    '  var inp=editor.querySelector("input");' +
    '  if(!inp) return "input-not-found";' +
    '  inp.value=' + JSON.stringify(productCode) + ';' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  return "triggered";' +
    '})()'
  );
  if (inputResult !== 'triggered') throw new Error('搜索输入框未找到: ' + inputResult);
  await sleep(2500);

  // 展开货号行
  const expandResult = await cdp.eval(erpId,
    '(function(){' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds=rows[i].querySelectorAll("td");' +
    '    if(tds[6]&&tds[6].innerText.trim()===' + JSON.stringify(productCode) + '){' +
    '      var icon=rows[i].querySelector(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
    '      if(icon){icon.click();return "expanded";}' +
    '      return "already-expanded";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (expandResult === 'not-found') throw new Error(`未找到货号「${productCode}」行`);
  if (expandResult === 'expanded') await sleep(2000);
}

/**
 * 点击「复制为套件」按钮
 */
async function _clickCopyAsSuite(erpId, platformCode) {
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
    '        if(!btn) return JSON.stringify({error:"复制为套件 not found"});' +
    '        btn.click();return JSON.stringify({clicked:true});' +
    '      }' +
    '    }' +
    '  }' +
    '  return JSON.stringify({error:' + JSON.stringify(platformCode) + '+" not found in expanded cells"});' +
    '})()'
  );
  if (r && r.error) throw new Error(r.error);
  await sleep(1500);
}

/**
 * 读取展开行中指定 platformCode 的 erpCode（执行后验证用）
 */
async function _readErpCodeFromRow(erpId, platformCode) {
  return await cdp.eval(erpId,
    '(function(){' +
    '  var expCells=document.querySelectorAll(".el-table__expanded-cell");' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows=expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds=rows[i].querySelectorAll("td");' +
    '      if(tds.length>=12&&tds[5].innerText.trim()===' + JSON.stringify(platformCode) + '){' +
    '        var inp=tds[11].querySelector("input");' +
    '        return inp?inp.value:"";' +
    '      }' +
    '    }' +
    '  }' +
    '  return "";' +
    '})()'
  );
}

/**
 * @param {string} erpId
 * @param {object} sku - sku-records.json 中的单个 SKU 对象
 * @returns {Promise<{ok: true, skipped?: true}>}
 */
async function createSuite(erpId, sku) {
  const { platformCode, erpCode, matchStatus, recognition, productCode, shopName } = sku;

  // 层1：幂等检查（基于结果，不基于字段存在）
  if (erpCode && (matchStatus === 'matched-original' || matchStatus === 'matched-ai')) {
    console.error(`[create-suite] ${platformCode} 已匹配（${matchStatus}），跳过`);
    return { ok: true, skipped: true };
  }

  if (!recognition || !recognition.items || !recognition.items.length) {
    throw new Error(`create-suite: ${platformCode} recognition 为空，请先完成识图`);
  }

  console.error(`[create-suite] ${platformCode} 开始，子品 ${recognition.items.length} 个`);

  // 强制 reload 对应表页面，清除 Vue 弹窗组件状态（防止上次失败的「选择商品」子品状态残留）
  // 删除 session 缓存条目，让 navigateErp 走完整刷新流程而非 hash 短路
  try {
    const cache = JSON.parse(fs.readFileSync(SESSION_CACHE_PATH, 'utf8'));
    delete cache[erpId];
    fs.writeFileSync(SESSION_CACHE_PATH, JSON.stringify(cache));
  } catch {}
  await navigateErp(erpId, '商品对应表');

  // 搜索并展开货号行
  await _searchAndExpand(erpId, shopName, productCode);

  // 层2（执行中）：标记套件（markOneSuite 内部已验证选中数=1）
  await markOneSuite(erpId, platformCode);

  // 验证「复制为套件」按钮已出现
  const hasCopyBtn = await cdp.eval(erpId,
    '(function(){' +
    '  var expCells=document.querySelectorAll(".el-table__expanded-cell");' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows=expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds=rows[i].querySelectorAll("td");' +
    '      if(tds.length>=6&&tds[5].innerText.trim()===' + JSON.stringify(platformCode) + '){' +
    '        var links=Array.from(rows[i].querySelectorAll("a"));' +
    '        return links.some(function(a){return a.innerText.trim()==="复制为套件";});' +
    '      }' +
    '    }' +
    '  }' +
    '  return false;' +
    '})()'
  );
  if (!hasCopyBtn) throw new Error(`标记套件后「复制为套件」按钮未出现（${platformCode}）`);

  // 关闭任何遗留的「选择商品」弹窗（上一次失败运行可能留下未关闭的弹窗带旧数据）
  await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs=Array.from(document.querySelectorAll(".el-dialog__wrapper"));' +
    '  dialogs.forEach(function(d){' +
    '    var t=d.querySelector(".el-dialog__title");' +
    '    if(t&&t.innerText.trim()==="选择商品"&&d.getBoundingClientRect().height>0){' +
    '      var btn=d.querySelector(".el-dialog__headerbtn");' +
    '      if(btn)btn.click();' +
    '    }' +
    '  });' +
    '})()'
  );
  await sleep(600);

  // 点击「复制为套件」
  await _clickCopyAsSuite(erpId, platformCode);

  // 逐一添加子品（来自 recognition.items）
  for (let i = 0; i < recognition.items.length; i++) {
    const item = recognition.items[i];
    console.error(`[create-suite] 添加子品 [${i + 1}/${recognition.items.length}]: ${item.name} × ${item.qty}`);
    await addProductToDialog(erpId, item.name, item.qty, i + 1);
  }

  // 确认弹窗
  await confirmDialog(erpId);
  await sleep(1000);

  // 层3（执行后）：验证 erpCode 已生成
  const newErpCode = await _readErpCodeFromRow(erpId, platformCode);
  if (!newErpCode) {
    throw new Error(`create-suite 执行后验证失败：${platformCode} erpCode 未生成`);
  }

  // 立即写回 sku-records.json（乐观标记，readErpCodes 会最终验证）
  const freshRecord = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const skuToUpdate = freshRecord.skus[platformCode];
  if (skuToUpdate) {
    skuToUpdate.matchStatus = 'matched-ai';
    skuToUpdate.erpCode = newErpCode;
  }
  safeWriteJson(SKU_RECORDS_PATH, freshRecord);

  console.error(`[create-suite] ${platformCode} 套件创建成功 → ${newErpCode}`);
  return { ok: true };
}

module.exports = { createSuite };
