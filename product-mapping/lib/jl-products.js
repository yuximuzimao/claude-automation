'use strict';
const cdp = require('./cdp');
const { sleep } = require('./wait');

/**
 * 筛选「特卖在售中」并抓取全部商品，返回货号+SPU名称列表
 * @param {string} jlId - 鲸灵标签页 targetId
 * @returns {Promise<Array<{code: string, name: string, productId: string}>>}
 */
async function listActiveProducts(jlId) {
  // 确保在商品列表页
  const url = await cdp.eval(jlId, 'location.href');
  if (!url.includes('goodsList')) {
    await cdp.navigate(jlId, 'https://scrm.jlsupp.com/micro-goods/business/goodsList');
    await sleep(3000);
  }

  // 打开在售状态下拉
  const opened = await cdp.eval(jlId,
    'var fi=document.querySelector("[attr-field-id*=onSaleStatus]");' +
    'var inp=fi?fi.querySelector("input"):null;' +
    'if(inp){inp.click();"ok"}else{"notfound"}'
  );
  if (opened !== 'ok') throw new Error('在售状态筛选器未找到');
  await sleep(600);

  // 选「特卖在售中」
  const selected = await cdp.eval(jlId,
    'var items=document.querySelectorAll(".el-select-dropdown__item");' +
    'var r="notfound";' +
    'for(var i=0;i<items.length;i++){' +
    '  if(items[i].innerText.trim()==="特卖在售中"){items[i].click();r="ok";break;}' +
    '}' +
    'r'
  );
  if (selected !== 'ok') throw new Error('未找到「特卖在售中」选项');
  await sleep(400);

  // 点查询
  const queried = await cdp.eval(jlId,
    'var btns=document.querySelectorAll("button");' +
    'var r="notfound";' +
    'for(var i=0;i<btns.length;i++){' +
    '  if(btns[i].innerText.trim()==="查询"){btns[i].click();r="ok";break;}' +
    '}' +
    'r'
  );
  if (queried !== 'ok') throw new Error('未找到查询按钮');
  await sleep(2000);

  // 检查总条数
  const totalText = await cdp.eval(jlId,
    'var p=document.querySelector(".el-pagination");p?p.innerText.replace(/\\s+/g," "):"no pager"'
  );
  const totalMatch = totalText.match(/共\s*(\d+)\s*条/);
  const total = totalMatch ? parseInt(totalMatch[1]) : 0;

  // 如果超过单页容量（默认10），切换到100条/页
  const rowCount = await cdp.eval(jlId, 'document.querySelectorAll("table tbody tr").length');
  if (total > rowCount) {
    // 找页数选择器，切换到100条/页
    const pageSizes = await cdp.eval(jlId,
      'var items=document.querySelectorAll(".el-select-dropdown__item");' +
      'var r="notfound";' +
      'for(var i=0;i<items.length;i++){' +
      '  if(items[i].innerText.trim()==="100条/页"){items[i].click();r="ok";break;}' +
      '}' +
      'r'
    );
    await sleep(2000);
  }

  // 提取所有货号
  const all = [];
  let page = 1;
  while (true) {
    const extracted = await extractFromCurrentPage(jlId);
    all.push(...extracted);

    // 检查是否有下一页
    const hasNext = await cdp.eval(jlId,
      'var btn=document.querySelector(".el-pagination .btn-next");' +
      'btn&&!btn.disabled?"yes":"no"'
    );
    if (hasNext !== 'yes') break;
    await cdp.eval(jlId, 'document.querySelector(".el-pagination .btn-next").click()');
    await sleep(2000);
    page++;
    if (page > 20) break; // 防止死循环
  }

  return all;
}

async function extractFromCurrentPage(jlId) {
  const raw = await cdp.eval(jlId,
    'var rows=document.querySelectorAll("table tbody tr");' +
    'var result=[];' +
    'for(var i=0;i<rows.length;i++){' +
    '  var td=rows[i].querySelector("td:nth-child(2)");' +
    '  if(!td)continue;' +
    '  var spans=td.querySelectorAll("span[target]");' +
    '  var name="",code="",pid="";' +
    '  for(var j=0;j<spans.length;j++){' +
    '    var t=spans[j].innerText.trim();' +
    '    if(!name&&!t.startsWith("商品")&&!t.startsWith("货号"))name=t;' +
    '    if(t.startsWith("货号："))code=t.replace("货号：","").trim();' +
    '    if(t.startsWith("商品ID："))pid=t.replace("商品ID：","").trim();' +
    '  }' +
    '  if(code)result.push(code+"|||"+name+"|||"+pid);' +
    '}' +
    'result.join("~~~")'
  );
  if (!raw) return [];
  return raw.split('~~~').filter(Boolean).map(function(item) {
    var parts = item.split('|||');
    return { code: parts[0], name: parts[1] || '', productId: parts[2] || '' };
  });
}

module.exports = { listActiveProducts };
