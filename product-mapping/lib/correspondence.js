'use strict';
/**
 * WHAT: 商品对应表全量读取（下载平台商品+读SKU映射+图片URL）
 * WHERE: check 流程 step 1.2/1.3 → 此模块
 * WHY: 对应表是 SKU 匹配的唯一数据源，读取不全会导致匹配遗漏
 * ENTRY: lib/check.js: readAllCorrespondence()
 */
const fs = require('fs');
const path = require('path');
const cdp = require('./cdp');
const { sleep } = require('./wait');
const { navigateErp } = require('./navigate');

// 下载标记文件：downloadPlatformProducts 完成后写入，供 downloadProducts 防止重复下载
const DOWNLOAD_MARKER_FILE = path.join(__dirname, '../data/.download-marker.json');

/**
 * 触发 ERP「下载平台商品」：选店铺 → 全量下载 → 确认 → 等待完成
 * 必须在 navigateErp('商品对应表') 之后调用
 * @param {string} erpId
 * @param {string} shopName
 */
async function downloadPlatformProducts(erpId, shopName) {
  console.error('[corr] 触发「下载平台商品」...');

  // 前置清理：关闭页面上可能残留的旧下载弹窗（避免干扰新对话框检测）
  await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  for(var i=0;i<ds.length;i++){' +
    '    if(ds[i].getBoundingClientRect().height>0){' +
    '      var btns=Array.from(ds[i].querySelectorAll("button"));' +
    '      var cancel=btns.find(function(b){return b.innerText.trim()==="取消";});' +
    '      if(cancel){cancel.click();continue;}' +
    '      var close=ds[i].querySelector(".el-dialog__headerbtn");' +
    '      if(close) close.click();' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(500);

  // 按优先级尝试多种按钮文字
  const clicked = await cdp.eval(erpId,
    '(function(){' +
    // 只在 button 里找，避免误点同名 <div>（如 .download-commodity）
    '  var candidates=["下载平台商品","下载商品","同步平台商品","同步商品"];' +
    '  var all=Array.from(document.querySelectorAll("button"));' +
    '  for(var ci=0;ci<candidates.length;ci++){' +
    '    var t=all.find(function(el){' +
    '      return el.innerText&&el.innerText.trim()===candidates[ci]&&el.getBoundingClientRect().width>0;' +
    '    });' +
    '    if(t){t.click();return "clicked:"+candidates[ci];}' +
    '  }' +
    '  var texts=all.filter(function(el){' +
    '    return el.getBoundingClientRect().width>0&&el.innerText&&el.innerText.trim().length>0&&el.innerText.trim().length<20;' +
    '  }).map(function(el){return el.innerText.trim();}).filter(function(v,i,a){return a.indexOf(v)===i;}).slice(0,40);' +
    '  return "NOT_FOUND:"+texts.join("|");' +
    '})()'
  );

  if (typeof clicked === 'string' && clicked.startsWith('NOT_FOUND:')) {
    throw new Error(`未找到「下载平台商品」按钮。页面可见元素: ${clicked.replace('NOT_FOUND:', '')}`);
  }
  console.error(`[corr] ${clicked}`);
  await sleep(3000);

  // 验证弹窗出现
  const dialogVisible = await cdp.eval(erpId,
    '(function(){var ds=document.querySelectorAll(".el-dialog__wrapper");for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0)return true;}return false;})()'
  );
  if (!dialogVisible) throw new Error('点击下载按钮后弹窗未出现');

  // 选择店铺：
  // 1. 通过 ElSelectShop vm.options 找目标店铺 value
  // 2. emit 设 ElSelectShop 自身 value
  // 3. 向上遍历找 DownLoadCommodity（有 bindShops/userIds 字段），直接设值
  //    原因：ElSelectShop 的 emit 不能自动上传到父组件
  const shopSelected = await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d=null;for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0){d=ds[i];break;}}' +
    '  if(!d)return "no-dialog";' +
    '  var sel=d.querySelector(".el-select");' +
    '  if(!sel)return "no-select";' +
    '  var vm=sel.__vue__;' +
    '  if(!vm)return "no-vue";' +
    '  var opts=vm.options||[];' +
    '  var target=opts.find(function(o){return (o.label||"").includes(' + JSON.stringify(shopName) + ');});' +
    '  if(!target)return "not-found:"+opts.map(function(o){return o.label;}).join(",");' +
    // 设 ElSelectShop 自身 value
    '  vm.visible=false;' +
    '  vm.$emit("input",[target.value]);' +
    '  vm.$emit("change",[target.value]);' +
    // 向上遍历找有 bindShops 或 userIds 的父组件（DownLoadCommodity）
    '  var parent=vm.$parent;' +
    '  for(var i=0;i<15&&parent;i++){' +
    '    if(typeof parent.bindShops!=="undefined"||typeof parent.userIds!=="undefined")break;' +
    '    parent=parent.$parent;' +
    '  }' +
    '  var result="selected:"+target.label+":"+target.value;' +
    // bindShops 是店铺对象数组（不是 ID 数组），禁止直接赋值，否则破坏数据结构
    // userIds 是已选店铺 ID 数组，通过 v-model 绑定到 el-select
    '  if(parent){' +
    '    if(typeof parent.userIds!=="undefined"){parent.userIds=[target.value];result+=" |userIds-set";}' +
    '  } else {result+=" |no-parent";}' +
    '  return result;' +
    '})()'
  );
  console.error(`[corr] 店铺选择: ${shopSelected}`);
  if (!shopSelected.startsWith('selected:')) {
    throw new Error(`下载弹窗未找到店铺「${shopName}」: ${shopSelected}`);
  }
  await sleep(300);

  // 验证：DownLoadCommodity bindShops 包含目标店铺
  const verifyParent = await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d=null;for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0){d=ds[i];break;}}' +
    '  if(!d)return "no-dialog";' +
    '  var sel=d.querySelector(".el-select");' +
    '  if(!sel||!sel.__vue__)return "no-vue";' +
    '  var vm=sel.__vue__;' +
    '  var parent=vm.$parent;' +
    '  for(var i=0;i<15&&parent;i++){' +
    '    if(typeof parent.bindShops!=="undefined"||typeof parent.userIds!=="undefined")break;' +
    '    parent=parent.$parent;' +
    '  }' +
    '  if(!parent)return "no-parent";' +
    '  return JSON.stringify({userIds:parent.userIds});' +
    '})()'
  );
  console.error(`[corr] DownLoadCommodity 验证: ${JSON.stringify(verifyParent)}`);
  if (typeof verifyParent === 'string') {
    throw new Error(`无法找到父组件 DownLoadCommodity: ${verifyParent}`);
  }
  const parentData = verifyParent;
  const hasShop = (parentData.userIds||[]).length > 0;
  if (!hasShop) {
    throw new Error(`店铺选择验证失败，userIds未更新: ${JSON.stringify(parentData)}`);
  }
  await sleep(500);

  // 勾选「全量下载」（el-checkbox 或原生 checkbox）
  await cdp.eval(erpId,
    '(function(){' +
    '  var ds=document.querySelectorAll(".el-dialog__wrapper");' +
    '  var d=null;for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0){d=ds[i];break;}}' +
    '  if(!d)return;' +
    '  var els=Array.from(d.querySelectorAll("label,span,.el-checkbox,.el-checkbox__label"));' +
    '  var target=els.find(function(el){return el.innerText&&el.innerText.includes("全量");});' +
    '  if(!target)return;' +
    '  var cb=target.querySelector("input[type=checkbox]");' +
    '  if(cb){if(!cb.checked)cb.click();return;}' +
    '  var vmEl=target.closest(".el-checkbox");' +
    '  if(vmEl&&vmEl.__vue__&&!vmEl.__vue__.isChecked){vmEl.click();}' +
    '})()'
  );
  await sleep(300);

  // 点确认
  await cdp.eval(erpId,
    '(function(){' +
    '  var footers=document.querySelectorAll(".el-dialog__footer");' +
    '  for(var i=0;i<footers.length;i++){' +
    '    if(footers[i].getBoundingClientRect().height>0){' +
    '      var btn=footers[i].querySelector(".el-button--primary");' +
    '      if(btn){btn.click();return;}' +
    '    }' +
    '  }' +
    '})()'
  );
  console.error('[corr] 已确认，等待下载完成...');

  // 等弹窗关闭（最多 60s）
  for (let i = 0; i < 60; i++) {
    await sleep(1000);
    const gone = await cdp.eval(erpId,
      '(function(){var ds=document.querySelectorAll(".el-dialog__wrapper");for(var i=0;i<ds.length;i++){if(ds[i].getBoundingClientRect().height>0)return false;}return true;})()'
    );
    if (gone) {
      console.error(`[corr] 下载完成（${i + 1}s）`);
      try { fs.writeFileSync(DOWNLOAD_MARKER_FILE, JSON.stringify({ shopName, downloadedAt: new Date().toISOString() })); } catch {}
      return;
    }
    if ((i + 1) % 10 === 0) console.error(`[corr] 下载中...（${i + 1}s）`);
  }
  throw new Error('下载平台商品超时（60s），请检查 ERP 网络');
}

/**
 * 纯读取：读取对应表数据（不触发平台商品下载）。
 * 假设调用方已 navigateErp 到商品对应表页面。
 * 副作用：点击店铺、空搜索、展开所有行、滚动页面。
 * @private
 */
async function _readCorrData(erpId, shopName) {

  // 点击左侧树对应店铺
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

  // 重置搜索筛选条件：清空 select 过滤（精确搜索→默认第一项）+ 清空搜索输入框
  // 必要性：navigateErp 在 session 新鲜时跳过 reload，前次 read-skus 的精确搜索/平台商家编码筛选会残留
  await cdp.eval(erpId,
    '(function(){' +
    // 重置 select[4]（搜索方式）+ select[5]（搜索字段）为第一个选项（最宽松，覆盖全量）
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  [4,5].forEach(function(idx){' +
    '    var sel=sels[idx];' +
    '    if(!sel) return;' +
    '    var vm=sel.__vue__;' +
    '    if(!vm) return;' +
    '    var opts=vm.options||[];' +
    '    if(opts.length>0){vm.$emit("input",opts[0].value);vm.$emit("change",opts[0].value);}' +
    '  });' +
    // 清空 el-input-popup-editor 搜索框（正确 selector，非 placeholder 匹配——以前的代码找不到此输入框）
    '  var editor=document.querySelector(".el-input-popup-editor");' +
    '  if(!editor) return;' +
    '  var inp=editor.querySelector("input");' +
    '  if(!inp) return;' +
    '  inp.value="";' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '})()'
  );
  await sleep(800);
  // 触发全量搜索（空条件回车）
  await cdp.eval(erpId,
    '(function(){' +
    '  var editor=document.querySelector(".el-input-popup-editor");' +
    '  if(!editor) return;' +
    '  var inp=editor.querySelector("input");' +
    '  if(!inp) return;' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '})()'
  );
  await sleep(2000);

  // 展开所有未展开的行
  await cdp.eval(erpId,
    'var icons=document.querySelectorAll(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
    'for(var i=0;i<icons.length;i++) icons[i].click();'
  );
  await sleep(2000);

  // 验证展开数量，补展开（mainCount只数主表的 el-table__row，不含子行）
  const expandedCount = await cdp.eval(erpId,
    '(function(){return document.querySelectorAll(".el-table__expand-icon--expanded").length;})()'
  );
  const mainCount = await cdp.eval(erpId,
    '(function(){' +
    '  var tb=document.querySelector(".el-table__body-wrapper .el-table__body>tbody");' +
    '  if(!tb) return 0;' +
    '  var rows=tb.children;' +
    '  var n=0;' +
    '  for(var i=0;i<rows.length;i++){if(rows[i].classList.contains("el-table__row"))n++;}' +
    '  return n;' +
    '})()'
  );
  if (expandedCount < mainCount) {
    await cdp.eval(erpId,
      'var icons=document.querySelectorAll(".el-table__expand-icon:not(.el-table__expand-icon--expanded)");' +
      'for(var i=0;i<icons.length;i++) icons[i].click();'
    );
    await sleep(1500);
  }
  console.error(`[corr] 展开行: ${expandedCount}/${mainCount}`);

  // 第一步：读取文字数据（不含图片，不依赖列名）
  const results = await cdp.eval(erpId,
    '(function(){' +
    '  var mainTbody=document.querySelector(".el-table__body-wrapper .el-table__body>tbody");' +
    '  if(!mainTbody) return JSON.stringify([]);' +
    '  var children=mainTbody.children;' +
    '  var results=[];' +
    '  var lastCode="";' +
    '  for(var i=0;i<children.length;i++){' +
    '    var row=children[i];' +
    '    if(row.classList.contains("el-table__row")){' +
    '      var tds=row.querySelectorAll("td");' +
    '      lastCode=tds[6]?tds[6].innerText.trim():"";' +
    '    } else {' +
    '      var expCell=row.querySelector(".el-table__expanded-cell");' +
    '      if(!expCell||!lastCode) continue;' +
    '      var tables=expCell.querySelectorAll("table");' +
    '      var tbl=null;' +
    '      for(var t=0;t<tables.length;t++){' +
    '        var srs=tables[t].querySelectorAll("tbody tr");' +
    '        if(srs.length>0&&srs[0].querySelectorAll("td").length>11){tbl=tables[t];break;}' +
    '      }' +
    '      if(!tbl) continue;' +
    '      var skus=[];' +
    '      var srs2=tbl.querySelectorAll("tbody tr");' +
    '      for(var s=0;s<srs2.length;s++){' +
    '        var sc=srs2[s].querySelectorAll("td");' +
    '        if(sc.length<12) continue;' +
    '        var ei=sc[11].querySelector("input");' +
    '        var en=sc[10].querySelector("input");' +
    '        skus.push({skuName:sc[4].innerText.trim(),platformCode:sc[5].innerText.trim(),erpCode:ei?ei.value:"",erpName:en?en.value:"",imgUrl:""});' +
    '      }' +
    '      if(lastCode) results.push({productCode:lastCode,skus:skus});' +
    '    }' +
    '  }' +
    '  return JSON.stringify(results);' +
    '})()'
  );

  const data = Array.isArray(results) ? results : [];
  console.error(`[corr] 读取产品数: ${data.length}, SKU数: ${data.reduce((n,p)=>n+p.skus.length,0)}`);

  // 第二步：动态探测图片列的class名（每次导航后会变）
  const imgColClass = await cdp.eval(erpId,
    '(function(){' +
    '  var expCell=document.querySelector(".el-table__expanded-cell");' +
    '  if(!expCell) return "";' +
    '  var img=expCell.querySelector("img");' +
    '  if(!img) return "";' +
    '  var td=img.closest("td");' +
    '  if(!td) return "";' +
    '  var cls=Array.from(td.classList).find(function(c){return c.indexOf("column_")>-1;});' +
    '  return cls||"";' +
    '})()'
  );
  console.error(`[corr] 图片列class: ${imgColClass || '未探测到（可能需要滚动触发）'}`);

  // 第三步：逐段滚动触发懒加载，用 platformCode 作为 key 收集图片URL
  // 每个展开行内的子表行：通过同行中的 platformCode input 来关联图片
  const imgMap = {}; // platformCode -> imgUrl

  const scrollHeight = await cdp.eval(erpId, 'document.body.scrollHeight');
  const STEPS = 12; // 每次滚动约1/12页，停留1s等懒加载
  console.error(`[corr] 开始逐段滚动收集图片(scrollHeight=${scrollHeight})...`);

  for (let i = 0; i <= STEPS; i++) {
    const pos = Math.floor(scrollHeight * i / STEPS);
    await cdp.eval(erpId, `window.scrollTo(0, ${pos})`);
    await sleep(1000);

    // 收集当前DOM中已加载的图片，用同行的platformCode作为key
    const batch = await cdp.eval(erpId,
      '(function(){' +
      '  var expCells=document.querySelectorAll(".el-table__expanded-cell");' +
      '  var map={};' +
      '  for(var i=0;i<expCells.length;i++){' +
      '    var rows=expCells[i].querySelectorAll("tbody tr");' +
      '    for(var j=0;j<rows.length;j++){' +
      '      var tds=rows[j].querySelectorAll("td");' +
      '      if(tds.length<6) continue;' +
      // platformCode在cells[5]的innerText
      '      var pCode=tds[5]?tds[5].innerText.trim():"";' +
      '      if(!pCode) continue;' +
      // 只取 td[3]（平台 SKU 图片列，2026-05-07 inspect 验证）
      '      var imgTds=rows[j].querySelectorAll("td");' +
      '      var imgEl=imgTds[3]?imgTds[3].querySelector("img"):null;' +
      '      if(imgEl&&imgEl.src&&imgEl.src.indexOf("http")===0){' +
      '        map[pCode]=imgEl.src;' +
      '      }' +
      '    }' +
      '  }' +
      '  return JSON.stringify(map);' +
      '})()'
    );

    if (batch && typeof batch === 'object') {
      let newCount = 0;
      for (const [k, v] of Object.entries(batch)) {
        if (!imgMap[k]) { imgMap[k] = v; newCount++; }
      }
      if (newCount > 0) process.stderr.write(`+${newCount}`);
    }
  }
  console.error('');

  // 统计图片覆盖率
  const totalSkus = data.reduce((n, p) => n + p.skus.length, 0);
  const coveredImgs = Object.keys(imgMap).length;
  console.error(`[corr] 图片收集: ${coveredImgs}/${totalSkus} SKU`);

  // 第四步：将图片URL合并回数据
  for (const product of data) {
    for (const sku of product.skus) {
      if (imgMap[sku.platformCode]) {
        sku.imgUrl = imgMap[sku.platformCode];
      }
    }
  }

  // 检查未覆盖的SKU（兜底日志）
  const missing = data.flatMap(p => p.skus).filter(s => !s.imgUrl);
  if (missing.length > 0) {
    console.error(`[corr] ⚠️ 仍有 ${missing.length} 个SKU无图片:`);
    missing.slice(0, 5).forEach(s => console.error(`  - ${s.skuName} (${s.platformCode})`));
  }

  return data;
}

/**
 * 读取对应表（含下载刷新）：navigate + 下载平台商品 + 读取数据。
 * check.js 使用——需要获取最新 SKU 映射时调用。
 */
async function readAllCorrespondence(erpId, shopName) {
  await navigateErp(erpId, '商品对应表');
  await downloadPlatformProducts(erpId, shopName);
  console.error('[corr] 页面就绪');
  return _readCorrData(erpId, shopName);
}

/**
 * 只读对应表（不触发下载）：navigate + 读取数据。
 * 当天已下载过、只需查询数据时使用。
 */
async function readCorrWithoutDownload(erpId, shopName) {
  await navigateErp(erpId, '商品对应表');
  return _readCorrData(erpId, shopName);
}

/**
 * 查询特定货号的对应关系（不触发下载）
 */
async function readCorrespondence(erpId, shopName, productCode) {
  const all = await readCorrWithoutDownload(erpId, shopName);
  return all.find(r => r.productCode === productCode) || null;
}

module.exports = { readAllCorrespondence, readCorrWithoutDownload, readCorrespondence, downloadPlatformProducts };
