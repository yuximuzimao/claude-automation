'use strict';
const cdp = require('./cdp');
const { sleep, waitFor } = require('./wait');
const path = require('path');

const EDIT_BASE = 'https://scrm.jlsupp.com/micro-goods/business/itemPublish/update';

/**
 * 进入商品编辑页，提取所有 SKU 名称和商品条码
 * @param {string} jlId - 鲸灵标签页 targetId
 * @param {string} spuId - 商品ID（从商品列表获取的 productId）
 * @returns {Promise<Array<{skuName: string, barcode: string}>>}
 */
async function getSkuDetails(jlId, spuId) {
  const editUrl = `${EDIT_BASE}?spuId=${spuId}&editFlag=1`;
  await cdp.navigate(jlId, editUrl);
  await sleep(4000);

  // 确认已到编辑页
  const url = await cdp.eval(jlId, 'location.href');
  if (!url.includes('itemPublish/update')) {
    throw new Error(`编辑页导航失败，当前URL: ${url}`);
  }

  // 等待页面内容加载（等「价格及库存」出现）
  await waitFor(
    async () => {
      const text = await cdp.eval(jlId, 'document.body.innerText.indexOf("价格及库存") >= 0');
      return text === true;
    },
    { timeoutMs: 10000, label: '等待价格及库存加载' }
  );
  await sleep(1000);

  // 提取所有 input 值
  // cdp.eval 已自动 JSON.parse，直接使用返回的数组
  const inputs = await cdp.eval(jlId,
    'var inputs=document.querySelectorAll("input");' +
    'var r=[];' +
    'for(var i=0;i<inputs.length;i++){' +
    '  r.push({idx:i,val:inputs[i].value,ph:inputs[i].placeholder||""});' +
    '}' +
    'JSON.stringify(r)'
  );

  // 直接从表格 DOM 中按行读取 SKU 名称 + 商品条码
  // 价格及库存表格每行：口味名(td) + 净含量 + 原价(input) + 供货价(input) + 终端价(input) + 库存(input) + 商品条码(input)
  const skus = await cdp.eval(jlId,
    'var rows=document.querySelectorAll("table tr");' +
    'var result=[];' +
    'for(var i=0;i<rows.length;i++){' +
    '  var tds=rows[i].querySelectorAll("td");' +
    '  if(tds.length<4)continue;' +
    '  var skuName="";' +
    '  var barcode="";' +
    '  var firstTd=tds[0].innerText.replace(/\\s+/g," ").trim();' +
    '  if(!firstTd)continue;' +
    '  skuName=firstTd;' +
    '  var inputs=rows[i].querySelectorAll("input");' +
    '  for(var j=0;j<inputs.length;j++){' +
    '    var v=inputs[j].value;' +
    '    if(v&&v.length>=5&&v.length<=20&&!v.includes(".")&&(/\\d+-\\d+/.test(v)||/^\\d{6,}$/.test(v))){' +
    '      barcode=v;break;' +
    '    }' +
    '  }' +
    '  if(skuName&&barcode)result.push({skuName:skuName,barcode:barcode});' +
    '}' +
    'JSON.stringify(result)'
  );

  // 关闭编辑页，返回商品列表
  await cdp.navigate(jlId, 'https://scrm.jlsupp.com/micro-goods/business/goodsList');
  await sleep(1000);
  // 处理「是否离开此网站」弹窗
  const dialog = await cdp.eval(jlId,
    'var btns=document.querySelectorAll("button");' +
    'var r="no dialog";' +
    'for(var i=0;i<btns.length;i++){' +
    '  if(btns[i].innerText.trim()==="离开"){btns[i].click();r="left";break;}' +
    '}' +
    'r'
  );
  await sleep(2000);

  return skus;
}

/**
 * 截取 SKU 主销售属性图片
 * @param {string} jlId
 * @param {string} spuId
 * @param {string} screenshotDir - 保存目录
 * @returns {Promise<Array<{skuName: string, imagePath: string}>>}
 */
async function getSkuImages(jlId, spuId, screenshotDir) {
  const editUrl = `${EDIT_BASE}?spuId=${spuId}&editFlag=1`;
  await cdp.navigate(jlId, editUrl);
  await sleep(4000);

  await waitFor(
    async () => {
      const text = await cdp.eval(jlId, 'document.body.innerText.indexOf("主销售属性") >= 0');
      return text === true;
    },
    { timeoutMs: 10000, label: '等待主销售属性加载' }
  );
  await sleep(1000);

  // 找主销售属性区域的 SKU 图片（缩略图）
  const imgData = await cdp.eval(jlId,
    'var allText=document.body.innerText;' +
    'var idx=allText.indexOf("主销售属性");' +
    'var idx2=allText.indexOf("副销售属性");' +
    'var section=idx>=0?allText.substring(idx,idx2>0?idx2:idx+3000):"";' +
    'section.substring(0,200)'
  );
  console.log('主销售属性区域:', imgData);

  // TODO: 具体截图逻辑（按 SKU 逐一截图）
  // 当前版本先截全页面的销售属性区域
  const screenshotPath = path.join(screenshotDir, `spu-${spuId}-sales.png`);
  await cdp.screenshot(jlId, screenshotPath);

  // 关闭编辑页
  await cdp.navigate(jlId, 'https://scrm.jlsupp.com/micro-goods/business/goodsList');
  await sleep(1000);
  await cdp.eval(jlId,
    'var btns=document.querySelectorAll("button");' +
    'for(var i=0;i<btns.length;i++){if(btns[i].innerText.trim()==="离开"){btns[i].click();break;}}'
  );
  await sleep(2000);

  return [{ screenshotPath }];
}

module.exports = { getSkuDetails, getSkuImages };
