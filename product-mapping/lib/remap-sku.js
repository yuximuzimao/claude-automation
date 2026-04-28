'use strict';
/**
 * 换绑 SKU 对应商品
 *
 * 流程：
 * 1. 从 data/sku-records.json 查出 platformCode 对应的 productCode（货号）
 * 2. navigateErp → 商品对应表
 * 3. 点左侧店铺
 * 4. 用货号搜索定位行（搜索框按货号有效，按 platformCode 无效）并展开
 * 5. 找到目标 platformCode 那行，点「换」链接
 * 6. 弹窗设筛选（精确搜索 | 商品名称 | 普通商品/组合装）
 * 7. 输入 ERP 商品名称搜索
 * 8. 确认结果唯一，勾选单选
 * 9. 点确认（需调用方传 confirm:true，默认不点）
 */

const path = require('path');
const fs = require('fs');
const cdp = require('./cdp');
const { sleep } = require('./wait');
const { navigateErp } = require('./navigate');

const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');

/**
 * @param {string} erpId        - ERP 标签页 targetId
 * @param {string} platformCode - 要换绑的 SKU 平台商家编码，如 260422-37
 * @param {string} erpName      - 要换绑到的 ERP 商品精确名称（精确匹配，与 features.json erpName 一致）
 * @param {object} opts
 * @param {boolean} opts.confirm    - true 才点确认按钮，默认 false（仅勾选，等人工确认）
 * @param {'普通商品'|'组合装商品'} opts.itemType - 商品类型筛选，默认「普通商品」
 * @returns {Promise<{ok:boolean, erpCode:string, erpName:string, message:string}>}
 */
async function remapSku(erpId, platformCode, erpName, opts = {}) {
  const { confirm = false, itemType = '普通商品', skipNav = false } = opts;

  // Step 1: 从 sku-records.json 查出 productCode（货号）和 shopName
  // 支持新格式（{stage, skus:{...}}）和旧格式（{platformCode:{...}}）
  const rawRecords = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const records = rawRecords.skus || rawRecords;
  const skuRecord = records[platformCode];
  if (!skuRecord) throw new Error(`platformCode ${platformCode} not found in sku-records.json`);
  const { productCode, shopName } = skuRecord;
  console.error(`[remap] ${platformCode} → productCode=${productCode}, shop=${shopName}`);

  // Step 2: 导航到商品对应表（skipNav=true 时跳过，调用方已就绪）
  if (!skipNav) await navigateErp(erpId, '商品对应表');

  // Step 3: 点击左侧店铺
  await cdp.eval(erpId,
    '(function(){' +
    '  var spans=document.querySelectorAll("span");' +
    '  for(var i=0;i<spans.length;i++){' +
    '    if(spans[i].innerText.trim()===' + JSON.stringify(shopName) + '&&spans[i].className.includes("el-tooltip")){' +
    '      spans[i].click();return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(1500);

  // Step 4: 用货号在搜索框中定位并展开
  // 对应表搜索框按「货号」有效，输入 productCode 可过滤到目标行，避免分页问题
  await cdp.eval(erpId,
    '(function(){' +
    '  var inputs=document.querySelectorAll("input");' +
    '  for(var i=0;i<inputs.length;i++){' +
    '    var ph=inputs[i].placeholder||"";' +
    '    if(ph.includes("商家编码")){' +
    '      inputs[i].value=' + JSON.stringify(productCode) + ';' +
    '      inputs[i].dispatchEvent(new Event("input",{bubbles:true}));' +
    '      inputs[i].dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '      inputs[i].dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '      return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(2000);

  // Step 5: 展开目标货号行
  // Step 5: 展开目标货号行
  const expandResult = await cdp.eval(erpId,
    '(function(){' +
    '  var rows = document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds = rows[i].querySelectorAll("td");' +
    '    var code = tds[6]?tds[6].innerText.trim():"";' +
    '    if(code===' + JSON.stringify(productCode) + '){' +
    '      var icon = rows[i].querySelector(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
    '      if(icon){icon.click();return "expanded";}' +
    '      return "already-expanded";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (expandResult === 'not-found') throw new Error(`productCode ${productCode} not found in table`);
  await sleep(1500);

  // Step 6: 找到 platformCode 那行，点「换」链接
  const clickResult = await cdp.eval(erpId,
    '(function(){' +
    '  var expCells = document.querySelectorAll(".el-table__expanded-cell");' +
    '  if(!expCells.length) return "no-expanded-cell";' +
    '  // 找包含目标productCode展开行的那个expCell（取最后展开的）' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows = expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds = rows[i].querySelectorAll("td");' +
    '      if(tds.length<6) continue;' +
    '      if(tds[5].innerText.trim()===' + JSON.stringify(platformCode) + '){' +
    '        var links = rows[i].querySelectorAll("a.mr_5");' +
    '        for(var j=0;j<links.length;j++){' +
    '          if(links[j].innerText.trim()==="换"){links[j].click();return "clicked";}' +
    '        }' +
    '        return "no-换-link";' +
    '      }' +
    '    }' +
    '  }' +
    '  return "platformCode-not-found";' +
    '})()'
  );
  if (clickResult !== 'clicked') throw new Error(`Cannot click 换 for ${platformCode}: ${clickResult}`);
  await sleep(1500);

  // Step 7: 验证弹窗出现
  const dialogTitle = await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<dialogs.length;i++){' +
    '    if(dialogs[i].getBoundingClientRect().height>0){' +
    '      var t = dialogs[i].querySelector(".el-dialog__title");' +
    '      return t?t.innerText:"no-title";' +
    '    }' +
    '  }' +
    '  return "no-dialog";' +
    '})()'
  );
  if (!dialogTitle.includes('换对应商品')) throw new Error(`Expected 换对应商品 dialog, got: ${dialogTitle}`);

  // Step 8: 设置筛选条件——精确搜索 | 商品名称 | itemType
  // 精确搜索（select[0]）和商品名称（select[1]）通常已默认，先检查再改
  const selRaw = await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var sels = d.querySelectorAll(".el-select");' +
    '  var vals = [];' +
    '  for(var i=0;i<sels.length;i++){var inp=sels[i].querySelector("input");vals.push(inp?inp.value:"");}' +
    '  return JSON.stringify(vals);' +
    '})()'
  );
  // cdp.eval 已自动 JSON.parse，selRaw 可能是数组也可能是字符串
  const selVals = Array.isArray(selRaw) ? selRaw : JSON.parse(selRaw);

  // 确保精确搜索
  if (selVals[0] !== '精确搜索') {
    await _clickSelectOption(erpId, 0, '精确搜索');
    await sleep(500);
  }
  // 确保商品名称
  if (selVals[1] !== '商品名称') {
    await _clickSelectOption(erpId, 1, '商品名称');
    await sleep(500);
  }
  // 设置商品类型
  if (selVals[2] !== itemType) {
    await _clickSelectOption(erpId, 2, itemType);
    await sleep(500);
  }

  // Step 7: 输入搜索词 + 回车
  await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var inputs = d.querySelectorAll("input");' +
    '  var textInput = null;' +
    '  for(var i=0;i<inputs.length;i++){' +
    '    if(!inputs[i].readOnly&&inputs[i].getBoundingClientRect().height>0){' +
    '      var ph=inputs[i].placeholder||"";' +
    '      if(!ph.includes("请选择")){textInput=inputs[i];break;}' +
    '    }' +
    '  }' +
    '  if(!textInput) return;' +
    '  textInput.value=' + JSON.stringify(erpName) + ';' +
    '  textInput.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  textInput.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  textInput.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '})()'
  );
  await sleep(2000);

  // Step 8: 验证结果唯一
  const searchResult = await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var rows = d.querySelectorAll(".el-table__body tbody tr");' +
    '  var total = d.querySelector(".el-pagination__total");' +
    '  var items = [];' +
    '  for(var i=0;i<rows.length;i++) items.push(rows[i].innerText.trim().replace(/\\s+/g," ").substring(0,80));' +
    '  return (total?total.innerText:"") + "|" + rows.length + "|" + items.join("||");' +
    '})()'
  );
  const [totalText, rowCount] = searchResult.split('|');
  if (parseInt(rowCount) !== 1) {
    throw new Error(`Search result not unique: ${searchResult}`);
  }

  // Step 9: 勾选单选框
  await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var radio = d.querySelector(".el-table__body tbody tr .el-radio__input");' +
    '  if(radio) radio.click();' +
    '})()'
  );
  await sleep(800);

  // 验证勾选
  const isChecked = await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var radio = d.querySelector(".el-table__body tbody tr .el-radio__input");' +
    '  return radio?radio.classList.contains("is-checked"):false;' +
    '})()'
  );
  if (!isChecked) throw new Error('Radio button not checked after click');

  if (!confirm) {
    return { ok: true, confirmed: false, message: `已勾选 ${erpName}，等待人工确认` };
  }

  // Step 10: 点确认
  await cdp.eval(erpId,
    '(function(){' +
    '  var footers = document.querySelectorAll(".el-dialog__footer");' +
    '  for(var i=0;i<footers.length;i++){' +
    '    if(footers[i].getBoundingClientRect().height>0){' +
    '      var btn=footers[i].querySelector(".el-button--primary");' +
    '      if(btn){btn.click();return;}' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(2500);

  // Step 11: 验证换绑成功（erpCode 已更新）
  const verifyResult = await cdp.eval(erpId,
    '(function(){' +
    '  var expCells = document.querySelectorAll(".el-table__expanded-cell");' +
    '  for(var c=0;c<expCells.length;c++){' +
    '    var rows = expCells[c].querySelectorAll("tbody tr");' +
    '    for(var i=0;i<rows.length;i++){' +
    '      var tds = rows[i].querySelectorAll("td");' +
    '      if(tds.length>=6 && tds[5].innerText.trim()===' + JSON.stringify(platformCode) + '){' +
    '        var inp = tds[11]?tds[11].querySelector("input"):null;' +
    '        var nameInp = tds[10]?tds[10].querySelector("input"):null;' +
    '        return (inp?inp.value:"") + "|" + (nameInp?nameInp.value:"");' +
    '      }' +
    '    }' +
    '  }' +
    '  return "row-not-found";' +
    '})()'
  );

  const [newErpCode, newErpName] = verifyResult.split('|');
  if (!newErpCode) throw new Error(`Verify failed: ${verifyResult}`);

  return { ok: true, confirmed: true, erpCode: newErpCode, erpName: newErpName, message: '换绑成功' };
}

/**
 * 辅助：点开指定 select（按 dialog 内的顺序 idx），选中目标选项文本
 */
async function _clickSelectOption(erpId, selectIdx, optionText) {
  await cdp.eval(erpId,
    '(function(){' +
    '  var dialogs = document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d = null;' +
    '  for(var i=0;i<dialogs.length;i++){if(dialogs[i].getBoundingClientRect().height>0){d=dialogs[i];break;}}' +
    '  var sels = d.querySelectorAll(".el-select");' +
    '  if(sels.length>' + selectIdx + ') sels[' + selectIdx + '].click();' +
    '})()'
  );
  await sleep(400);
  await cdp.eval(erpId,
    '(function(){' +
    '  var items = document.querySelectorAll(".el-select-dropdown__item");' +
    '  for(var i=0;i<items.length;i++){' +
    '    if(items[i].innerText.trim()===' + JSON.stringify(optionText) + '&&items[i].getBoundingClientRect().height>0){' +
    '      items[i].click();return;' +
    '    }' +
    '  }' +
    '})()'
  );
}

module.exports = { remapSku };
