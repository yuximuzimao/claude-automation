'use strict';
/**
 * 第六步：重读验证 ERP 编码
 *
 * 只更新 matchStatus=unmatched 的 SKU，不碰 matched-original（历史正确绑定不可覆盖）
 * 结果写回 sku-records.json（stage=matched）
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');
const { sleep } = require('../wait');
const { ensureCorrPage } = require('./ensure-corr-page');
const { readTableRows } = require('./read-table-rows');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * 在主页（非 dialog）的 el-select 中选值
 */
async function _setMainPageSelect(erpId, selectIdx, optionText) {
  const currentVal = await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(!sel) return "";' +
    '  var inp=sel.querySelector("input");' +
    '  return inp?inp.value:"";' +
    '})()'
  );
  if (currentVal === optionText) return;

  await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(sel) sel.click();' +
    '})()'
  );
  await sleep(400);

  await cdp.eval(erpId,
    '(function(){' +
    '  var items=document.querySelectorAll(".el-select-dropdown__item");' +
    '  for(var i=0;i<items.length;i++){' +
    '    if(items[i].innerText.trim()===' + JSON.stringify(optionText) + '&&items[i].getBoundingClientRect().height>0){' +
    '      items[i].click();return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(300);
}

/**
 * @param {string} erpId
 * @param {string} shopName
 * @param {string} productCode
 * @returns {Promise<{ok: true, data: {matched, failed}}>}
 */
async function readErpCodes(erpId, shopName, productCode) {
  // stage 只从文件读（要求 matched 或 verified，不允许 annotated 及之前）
  const record = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const VALID_STAGES = ['matched', 'verified'];
  if (!VALID_STAGES.includes(record.stage)) {
    throw new Error(`read-erp-codes: stage=${record.stage}，要求 matched 或 verified`);
  }

  await ensureCorrPage(erpId);

  // 设搜索下拉：精确搜索 + 平台商家编码（与 readSkus 一致）
  await _setMainPageSelect(erpId, 4, '精确搜索');
  await _setMainPageSelect(erpId, 5, '平台商家编码');

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

  // 读取最新 erpCode（readTableRows 内置等待+展开+校验）
  const subRows = await readTableRows(erpId, {
    fields: ['platformCode', 'erpCode'],
    expectedProductCode: productCode,
  });

  // 更新 matchStatus（只动 unmatched，不碰 matched-original）
  // stage 只从文件读，每次都重新读文件
  const freshRecord = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  let matched = 0;
  let failed = 0;

  for (const row of subRows) {
    const sku = freshRecord.skus[row.platformCode];
    if (!sku) continue;

    // 重新验证 unmatched 和 matched-ai（乐观标记需最终确认），不碰 matched-original
    if (sku.matchStatus !== 'unmatched' && sku.matchStatus !== 'matched-ai') continue;

    if (row.erpCode) {
      sku.matchStatus = 'matched-ai';
      sku.erpCode = row.erpCode;
      matched++;
    } else {
      sku.matchStatus = 'failed-ai';
      failed++;
    }
  }

  freshRecord.stage = 'matched';
  safeWriteJson(SKU_RECORDS_PATH, freshRecord);

  console.error(`[read-erp-codes] ${productCode}：matched-ai ${matched}，failed-ai ${failed}`);
  return { ok: true, data: { matched, failed } };
}

module.exports = { readErpCodes };
