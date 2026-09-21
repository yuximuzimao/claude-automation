'use strict';
/**
 * 从商品档案V2读取「普通商品」全列表，输出商品名称 + 主商家编码
 * 用途：为 features.json 补全精确 ERP 名称
 *
 * 新版页面：
 * - 查询由 .search-wrap Vue 组件的 search() 触发；
 * - 当前页数据从可见 .el-table 的 Vue store.states.data 读取；
 * - 旧表头“普通商品”筛选入口已移除，因此按 ERP 行 type==="0" 精确过滤普通商品；
 * - 翻页使用可见 Element UI 分页控件。
 */
const cdp = require('../lib/cdp');
const { navigateErp } = require('../lib/navigate');
const { sleep } = require('../lib/wait');

const ERP_ID = '075D3D5770F69781F17A14C418D00338';

const CLEAR_AND_QUERY_JS = `
(function(){
  function visible(el){ if(!el) return false; var r=el.getBoundingClientRect(); return r.width>0&&r.height>0; }
  var clearBtn=Array.from(document.querySelectorAll('.common-query-condition button')).find(function(b){
    return visible(b)&&b.innerText.trim()==='清空条件';
  });
  if(clearBtn) clearBtn.click();
  var wrap=document.querySelector('.search-wrap');
  var vm=wrap&&wrap.__vue__;
  if(!vm||typeof vm.search!=='function') return JSON.stringify({error:'未找到 search'});
  vm.search();
  return JSON.stringify({queried:true,cleared:!!clearBtn});
})()
`;

const READ_PAGE_JS = `
(function(){
  function visible(el){ if(!el) return false; var r=el.getBoundingClientRect(); return r.width>0&&r.height>0; }
  var table=Array.from(document.querySelectorAll('.el-table')).find(visible);
  var vm=table&&table.__vue__;
  var data=vm&&vm.store&&vm.store.states&&vm.store.states.data;
  if(!Array.isArray(data)) return JSON.stringify({error:'table store 不可用'});

  var totalEl=Array.from(document.querySelectorAll('.el-pagination__total')).find(visible);
  var totalText=totalEl?totalEl.innerText.trim():'';
  var total=parseInt(totalText.replace(/[^0-9]/g,''),10)||0;

  var sizeInput=Array.from(document.querySelectorAll('.el-pagination .el-select .el-input__inner')).find(visible);
  var pageSize=sizeInput?parseInt(sizeInput.value,10):0;

  var active=Array.from(document.querySelectorAll('.el-pager li.active')).find(visible);
  var pageNo=active?parseInt(active.innerText.trim(),10):1;

  var items=data.filter(function(item){return String(item.type)==='0';}).map(function(item){
    return {outerId:item.outerId,title:item.title,shortTitle:item.shortTitle||'',type:item.type};
  });
  return JSON.stringify({pageNo:pageNo,total:total,pageSize:pageSize,count:data.length,items:items});
})()
`;

const NEXT_PAGE_JS = `
(function(){
  function visible(el){ if(!el) return false; var r=el.getBoundingClientRect(); return r.width>0&&r.height>0; }
  var btn=Array.from(document.querySelectorAll('button.btn-next')).find(visible);
  if(!btn) return JSON.stringify({error:'下一页按钮不存在'});
  if(btn.disabled||btn.classList.contains('disabled')) return JSON.stringify({done:true});
  btn.click();
  return JSON.stringify({clicked:true});
})()
`;

async function main(erpId = ERP_ID) {
  console.log('[fetch-archive-names] Step1: navigateErp...');
  await navigateErp(erpId, '商品档案V2');
  console.log('[fetch-archive-names] 页面就绪');
  await sleep(1200);

  const start = await cdp.eval(erpId, CLEAR_AND_QUERY_JS);
  if (start && start.error) throw new Error(start.error);
  await sleep(1800);

  const first = await cdp.eval(erpId, READ_PAGE_JS);
  if (first && first.error) throw new Error(first.error);
  if (!first.total || !first.pageSize) {
    throw new Error(`分页信息不可用: total=${first.total}, pageSize=${first.pageSize}`);
  }

  const totalPages = Math.ceil(first.total / first.pageSize);
  console.log(`[pages] 全部商品共 ${first.total} 条，${totalPages} 页；逐页按 type=0 保留普通商品`);

  const allItems = [];
  for (let page = 1; page <= totalPages; page++) {
    const d = page === 1 ? first : await cdp.eval(erpId, READ_PAGE_JS);
    if (d && d.error) throw new Error(`第 ${page} 页读取失败: ${d.error}`);
    console.log(`[page ${d.pageNo}] 当前页 ${d.count} 条，其中普通商品 ${d.items.length} 条`);
    allItems.push(...d.items);

    if (page < totalPages) {
      const next = await cdp.eval(erpId, NEXT_PAGE_JS);
      if (next && next.error) throw new Error(next.error);
      if (next && next.done) throw new Error(`分页提前结束: 当前 ${page}/${totalPages}`);
      await sleep(1800);
    }
  }

  console.log(`\n===== 普通商品全列表（共 ${allItems.length} 条）=====`);
  allItems.forEach((item, i) => {
    console.log(`${String(i + 1).padStart(3, ' ')}. [${item.outerId}] ${item.title}${item.shortTitle ? ' | 简称:' + item.shortTitle : ''} (type:${item.type})`);
  });
  return allItems;
}

if (require.main === module) {
  main().then(() => process.exit(0)).catch(e => { console.error('[ERROR]', e.message); process.exit(1); });
}
module.exports = { main };
