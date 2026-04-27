'use strict';
/**
 * 从商品档案V2读取「普通商品」全列表，输出商品名称 + 主商家编码
 * 用途：为 features.json 补全精确 ERP 名称
 *
 * 技术路线：读 Vue 组件 sv.dataList（与 archive.js queryArchive 同源）
 * 筛选：sv.searchData.itemType = "0"（普通商品），再调 sv.handleQuery()
 * 翻页：修改 sv.pageData.pageNo，再调 sv.handleQuery()
 */
const cdp = require('../lib/cdp');
const { navigateErp } = require('../lib/navigate');
const { sleep } = require('../lib/wait');

const ERP_ID = '075D3D5770F69781F17A14C418D00338';

// 找 Vue 组件（与 archive.js 同一套）并返回关键属性
const GET_SV_INFO_JS =
  '(function(){' +
  '  var el=document.querySelector(".el-input__inner[placeholder=\'主商家编码\']");' +
  '  if(!el) return JSON.stringify({error:"未找到输入框"});' +
  '  var v=el;var sv=null;' +
  '  for(var i=0;i<12;i++){if(!v)break;var vm=v.__vue__;if(vm&&vm.dataList){sv=vm;break;}v=v.parentElement;}' +
  '  if(!sv) return JSON.stringify({error:"未找到dataList组件"});' +
  '  return JSON.stringify({' +
  '    total: sv.pageData.total,' +
  '    pageNo: sv.pageData.pageNo,' +
  '    pageSize: sv.pageData.pageSize,' +
  '    itemType: sv.searchData.itemType,' +
  '    count: sv.dataList.length' +
  '  });' +
  '})()';

// 设置 itemType="0"（普通商品）并触发查询（第1页）
const SET_TYPE_AND_QUERY_JS =
  '(function(){' +
  '  var el=document.querySelector(".el-input__inner[placeholder=\'主商家编码\']");' +
  '  if(!el) return JSON.stringify({error:"未找到输入框"});' +
  '  var v=el;var sv=null;' +
  '  for(var i=0;i<12;i++){if(!v)break;var vm=v.__vue__;if(vm&&vm.dataList){sv=vm;break;}v=v.parentElement;}' +
  '  if(!sv) return JSON.stringify({error:"未找到dataList组件"});' +
  '  sv.searchData.itemType="0";' +
  '  sv.handleQuery();' +
  '  return JSON.stringify({set:true,itemType:sv.searchData.itemType});' +
  '})()';

// 翻到指定页并触发查询
function makeGoPageJS(pageNo) {
  return '(function(){' +
    '  var el=document.querySelector(".el-input__inner[placeholder=\'主商家编码\']");' +
    '  if(!el) return JSON.stringify({error:"未找到输入框"});' +
    '  var v=el;var sv=null;' +
    '  for(var i=0;i<12;i++){if(!v)break;var vm=v.__vue__;if(vm&&vm.dataList){sv=vm;break;}v=v.parentElement;}' +
    '  if(!sv) return JSON.stringify({error:"未找到dataList组件"});' +
    '  sv.pageData.pageNo=' + pageNo + ';' +
    '  sv.handleQuery();' +
    '  return JSON.stringify({goPage:' + pageNo + '});' +
    '})()';
}

// 读当前页 dataList（普通商品：type=="0"）
const READ_DATALIST_JS =
  '(function(){' +
  '  var el=document.querySelector(".el-input__inner[placeholder=\'主商家编码\']");' +
  '  if(!el) return JSON.stringify({error:"未找到输入框"});' +
  '  var v=el;var sv=null;' +
  '  for(var i=0;i<12;i++){if(!v)break;var vm=v.__vue__;if(vm&&vm.dataList){sv=vm;break;}v=v.parentElement;}' +
  '  if(!sv||!sv.dataList) return JSON.stringify({error:"dataList为空"});' +
  '  var items=sv.dataList.map(function(item){' +
  '    return {outerId:item.outerId,title:item.title,shortTitle:item.shortTitle||"",type:item.type};' +
  '  });' +
  '  return JSON.stringify({pageNo:sv.pageData.pageNo,total:sv.pageData.total,items:items});' +
  '})()';

async function main() {
  console.log('[fetch-archive-names] Step1: navigateErp...');
  await navigateErp(ERP_ID, '商品档案V2');
  console.log('[fetch-archive-names] 页面就绪');
  await sleep(2000);

  // Step2: 确认 sv 可读
  const info = await cdp.eval(ERP_ID, GET_SV_INFO_JS);
  console.log('[sv info]', info);
  if (info && info.error) throw new Error('sv 不可用: ' + info.error);

  // Step3: 筛选「普通商品」（span.ui-datalist_cell-filter-icon → div.ui-datalist_filters-list-item）
  console.log('[fetch-archive-names] Step3: 筛选普通商品...');
  const click1 = await cdp.eval(ERP_ID,
    '(function(){' +
    '  var icon = document.querySelector("span.ui-datalist_cell-filter-icon");' +
    '  if (!icon) return JSON.stringify({error: "filter icon not found"});' +
    '  icon.click(); return JSON.stringify({clicked: true});' +
    '})()'
  );
  console.log('[filter icon]', click1);
  if (click1 && click1.error) throw new Error('点筛选图标失败: ' + click1.error);
  await sleep(500);

  const click2 = await cdp.eval(ERP_ID,
    '(function(){' +
    '  var items = Array.from(document.querySelectorAll("div.ui-datalist_filters-list-item"));' +
    '  var target = items.find(function(el){ return el.textContent.trim() === "普通商品"; });' +
    '  if (!target) return JSON.stringify({error: "普通商品 item not found", count: items.length});' +
    '  target.click(); return JSON.stringify({clicked: true});' +
    '})()'
  );
  console.log('[filter normal]', click2);
  if (click2 && click2.error) throw new Error('点普通商品失败: ' + click2.error);
  await sleep(3000);

  // 读总条数
  const info2 = await cdp.eval(ERP_ID, GET_SV_INFO_JS);
  console.log('[after filter]', info2);
  if (info2 && info2.error) throw new Error('筛选后sv不可用');

  const total = info2.total;
  const pageSize = info2.pageSize || 50;
  const totalPages = Math.ceil(total / pageSize);
  console.log(`[pages] 普通商品共 ${total} 条，${totalPages} 页`);

  // Step4: 翻页读取全部
  const allItems = [];
  for (let page = 1; page <= totalPages; page++) {
    if (page > 1) {
      const gp = await cdp.eval(ERP_ID, makeGoPageJS(page));
      console.log(`[go page ${page}]`, gp);
      await sleep(3000);
    }

    const d = await cdp.eval(ERP_ID, READ_DATALIST_JS);
    if (d && d.error) {
      console.error(`[page ${page}] 读取失败:`, d.error);
      break;
    }
    console.log(`[page ${d.pageNo}] 读到 ${d.items.length} 条`);
    allItems.push(...d.items);
  }

  console.log(`\n===== 普通商品全列表（共 ${allItems.length} 条）=====`);
  allItems.forEach((item, i) => {
    console.log(`${String(i + 1).padStart(3, ' ')}. [${item.outerId}] ${item.title}${item.shortTitle ? ' | 简称:' + item.shortTitle : ''} (type:${item.type})`);
  });
}

if (require.main === module) { main(null).catch(e => { console.error("[ERROR]", e.message); process.exit(1); }); }
module.exports = { main };
