'use strict';
/**
 * 公共表格 DOM 读取：内置等待 + expectedProductCode 绑定校验
 *
 * 调用方只需传 fields 和 expectedProductCode，不负责等待。
 * 关键防线：读取首行 productCode 与 expectedProductCode 比对，
 * 不一致直接抛 TABLE_DATA_MISMATCH，是数据正确性的最后防线。
 *
 * @param {string} erpId
 * @param {{ fields: string[], expectedProductCode: string }} opts
 * @returns {Promise<Array<object>>} - 按 platformCode 索引的子行数据
 */
const cdp = require('../cdp');
const { waitFor, sleep } = require('../wait');

// 主行列索引
const MAIN_ROW_PRODUCT_CODE_COL = 6;
// 子行列索引
const SUB_COL = { skuName: 4, platformCode: 5, erpName: 10, erpCode: 11 };

async function readTableRows(erpId, { fields, expectedProductCode }) {
  if (!expectedProductCode) throw new Error('readTableRows: expectedProductCode 必传');

  // 1. 等主行出现（最多 10s）
  await waitFor(async () => {
    const count = await cdp.eval(erpId,
      '(function(){return document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row").length;})()'
    );
    return count > 0;
  }, { timeoutMs: 10000, intervalMs: 500, label: '等主行出现' });

  // 2. 验证首行 productCode = expectedProductCode（最后防线）
  const firstRowCode = await cdp.eval(erpId,
    '(function(){' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  if(!rows.length) return "";' +
    '  var tds=rows[0].querySelectorAll("td");' +
    '  return tds[' + MAIN_ROW_PRODUCT_CODE_COL + ']?tds[' + MAIN_ROW_PRODUCT_CODE_COL + '].innerText.trim():"";' +
    '})()'
  );
  if (firstRowCode !== expectedProductCode) {
    throw new Error(`TABLE_DATA_MISMATCH: 期望货号 ${expectedProductCode}，表格首行显示 ${firstRowCode}`);
  }

  // 3. 展开目标行（若未展开）
  const expandResult = await cdp.eval(erpId,
    '(function(){' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds=rows[i].querySelectorAll("td");' +
    '    if(tds[' + MAIN_ROW_PRODUCT_CODE_COL + ']&&tds[' + MAIN_ROW_PRODUCT_CODE_COL + '].innerText.trim()===' + JSON.stringify(expectedProductCode) + '){' +
    '      var expandedIcon=rows[i].querySelector(".el-table__expand-icon--expanded");' +
    '      if(expandedIcon) return "already-expanded";' +
    '      var icon=rows[i].querySelector(".el-table__expand-icon");' +
    '      if(icon){icon.click();return "expanded";}' +
    '      return "no-icon";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (expandResult === 'not-found') throw new Error(`TABLE_DATA_MISMATCH: 展开时未找到货号 ${expectedProductCode}`);
  if (expandResult === 'no-icon') throw new Error(`展开失败：展开图标不存在（货号 ${expectedProductCode}）`);
  if (expandResult === 'expanded') await sleep(1500);

  // 4. 等展开完成（等 expanded-cell 出现，最多 8s）
  await waitFor(async () => {
    const count = await cdp.eval(erpId,
      '(function(){return document.querySelectorAll(".el-table__expanded-cell").length;})()'
    );
    return count > 0;
  }, { timeoutMs: 8000, intervalMs: 400, label: '等展开完成' });

  // 5. 等子行出现
  await waitFor(async () => {
    const count = await cdp.eval(erpId,
      '(function(){' +
      '  var ec=document.querySelector(".el-table__expanded-cell");' +
      '  if(!ec) return 0;' +
      '  return ec.querySelectorAll("tbody tr").length;' +
      '})()'
    );
    return count > 0;
  }, { timeoutMs: 8000, intervalMs: 400, label: '等子行出现' });

  // 6. 读取子行数据
  const needsImg = fields.includes('imgUrl');
  if (needsImg) {
    // 滚动到展开区域，触发图片懒加载
    await cdp.eval(erpId,
      '(function(){var ec=document.querySelector(".el-table__expanded-cell");if(ec){ec.scrollIntoView({block:"center"});}})()'
    );
    await sleep(1500);
  }

  const rows = await cdp.eval(erpId,
    '(function(){' +
    '  var ec=document.querySelector(".el-table__expanded-cell");' +
    '  if(!ec) return JSON.stringify([]);' +
    '  var rows=ec.querySelectorAll("tbody tr");' +
    '  var result=[];' +
    '  for(var i=0;i<rows.length;i++){' +
    '    var tds=rows[i].querySelectorAll("td");' +
    '    if(tds.length<12) continue;' +
    '    var sku={};' +
    '    sku.platformCode=tds[5].innerText.trim();' +
    '    sku.skuName=tds[4].innerText.trim();' +
    '    var erpCodeInp=tds[11].querySelector("input");' +
    '    sku.erpCode=erpCodeInp?erpCodeInp.value:"";' +
    '    var erpNameInp=tds[10].querySelector("input");' +
    '    sku.erpName=erpNameInp?erpNameInp.value:"";' +
    '    var imgs=rows[i].querySelectorAll("img");' +
    '    sku.imgUrl=(imgs[0]&&imgs[0].src&&imgs[0].src.indexOf("http")===0)?imgs[0].src:"";' +
    '    result.push(sku);' +
    '  }' +
    '  return JSON.stringify(result);' +
    '})()'
  );

  const all = Array.isArray(rows) ? rows : [];

  // 过滤只返回请求的字段
  return all.map(row => {
    const out = {};
    for (const f of fields) out[f] = row[f] !== undefined ? row[f] : '';
    return out;
  });
}

module.exports = { readTableRows };
