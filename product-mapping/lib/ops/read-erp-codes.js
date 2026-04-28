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

  // 点左侧店铺
  const shopClicked = await cdp.eval(erpId,
    '(function(){' +
    '  var spans=document.querySelectorAll("span");' +
    '  for(var i=0;i<spans.length;i++){' +
    '    if(spans[i].innerText.trim()===' + JSON.stringify(shopName) + '&&spans[i].className.includes("el-tooltip")){' +
    '      spans[i].click();return "clicked";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (shopClicked !== 'clicked') throw new Error(`左侧店铺「${shopName}」未找到`);
  await sleep(1500);

  // 输入货号 + 回车
  const inputResult = await cdp.eval(erpId,
    '(function(){' +
    '  var inputs=document.querySelectorAll("input[type=text],input:not([type])");' +
    '  for(var i=0;i<inputs.length;i++){' +
    '    var ph=inputs[i].placeholder||"";' +
    '    if(ph.includes("商家编码")){' +
    '      inputs[i].value=' + JSON.stringify(productCode) + ';' +
    '      inputs[i].dispatchEvent(new Event("input",{bubbles:true}));' +
    '      inputs[i].dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '      inputs[i].dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '      return "triggered";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (inputResult !== 'triggered') throw new Error('搜索输入框未找到');
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
