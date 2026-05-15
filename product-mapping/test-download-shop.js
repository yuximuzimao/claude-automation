'use strict';
/**
 * 测试：下载平台商品弹窗完整流程
 * 1. 打开弹窗
 * 2. 打开下拉 → 取消所有已选 → 选目标店铺 → 关闭下拉
 * 3. 验证（只有1个正确店铺），不对则重置
 * 4. 选全量下载
 * 5. 点确认 → 等完成
 */
const cdp = require('./lib/cdp');
const { getTargetIds } = require('./lib/targets');
const { sleep } = require('./lib/wait');

async function getVisibleDialog(erpId) {
  return cdp.eval(erpId, `(function(){
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].getBoundingClientRect().height > 0 && ds[i].innerText.indexOf('取消') >= 0)
        return true;
    }
    return false;
  })()`);
}

async function openDropdownAndSelect(erpId, shopName) {
  // 打开下拉
  await cdp.eval(erpId, `(function(){
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].getBoundingClientRect().height > 0 && ds[i].innerText.indexOf('取消') >= 0) {
        var sel = ds[i].querySelector('.el-select');
        if (sel) sel.click();
        return;
      }
    }
  })()`);
  await sleep(600);

  // 检查下拉是否展开
  const dropdownVisible = await cdp.eval(erpId, `(function(){
    var dds = document.querySelectorAll('.el-select-dropdown');
    for (var i = 0; i < dds.length; i++) {
      if (dds[i].getBoundingClientRect().height > 0) return true;
    }
    return false;
  })()`);
  if (!dropdownVisible) throw new Error('下拉未展开');

  // 列出所有选项和其选中状态
  const optState = await cdp.eval(erpId, `(function(){
    var dds = document.querySelectorAll('.el-select-dropdown');
    for (var i = 0; i < dds.length; i++) {
      if (dds[i].getBoundingClientRect().height > 0) {
        var items = Array.from(dds[i].querySelectorAll('li.el-select-dropdown__item'));
        return items.map(function(li) {
          return { label: li.innerText.trim(), selected: li.classList.contains('selected') };
        });
      }
    }
    return [];
  })()`);
  console.log('下拉选项状态:', optState.filter(o => o.selected).map(o => o.label));

  // 取消所有已选（除目标店铺外）
  for (const opt of optState) {
    if (opt.selected && !opt.label.includes(shopName)) {
      console.log('取消:', opt.label);
      await cdp.eval(erpId, `(function(){
        var dds = document.querySelectorAll('.el-select-dropdown');
        for (var i = 0; i < dds.length; i++) {
          if (dds[i].getBoundingClientRect().height > 0) {
            var items = Array.from(dds[i].querySelectorAll('li.el-select-dropdown__item'));
            var t = items.find(function(li){ return li.innerText.trim() === ${JSON.stringify(opt.label)}; });
            if (t) t.click();
            return;
          }
        }
      })()`);
      await sleep(200);
    }
  }

  // 选目标店铺（如果还没选中）
  const targetSelected = optState.find(o => o.label.includes(shopName) && o.selected);
  if (!targetSelected) {
    console.log('选中:', shopName);
    await cdp.eval(erpId, `(function(){
      var dds = document.querySelectorAll('.el-select-dropdown');
      for (var i = 0; i < dds.length; i++) {
        if (dds[i].getBoundingClientRect().height > 0) {
          var items = Array.from(dds[i].querySelectorAll('li.el-select-dropdown__item'));
          var t = items.find(function(li){ return li.innerText.trim().indexOf(${JSON.stringify(shopName)}) >= 0; });
          if (t) t.click();
          return;
        }
      }
    })()`);
    await sleep(200);
  }

  // 关闭下拉（按Escape）
  await cdp.eval(erpId, `document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',keyCode:27,bubbles:true}))`);
  await sleep(300);
}

async function verifySelection(erpId, shopName) {
  const text = await cdp.eval(erpId, `(function(){
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].getBoundingClientRect().height > 0 && ds[i].innerText.indexOf('取消') >= 0) {
        var sel = ds[i].querySelector('.el-select');
        if (!sel || !sel.__vue__) return 'no-vue';
        var val = sel.__vue__.value || [];
        var opts = sel.__vue__.options || [];
        var selected = opts.filter(function(o){ return val.indexOf(o.value) >= 0; });
        return JSON.stringify(selected.map(function(o){ return o.label; }));
      }
    }
    return 'no-dialog';
  })()`);
  const labels = typeof text === 'string' ? JSON.parse(text) : text;
  console.log('已选店铺:', labels);
  return Array.isArray(labels) && labels.length === 1 && labels[0].includes(shopName);
}

async function selectFullDownload(erpId) {
  await cdp.eval(erpId, `(function(){
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].getBoundingClientRect().height > 0 && ds[i].innerText.indexOf('取消') >= 0) {
        var labels = Array.from(ds[i].querySelectorAll('.el-radio, .el-radio__label'));
        var t = labels.find(function(l){ return l.innerText && l.innerText.trim().indexOf('全量') >= 0; });
        if (t) t.click();
        return;
      }
    }
  })()`);
}

async function clickConfirm(erpId) {
  await cdp.eval(erpId, `(function(){
    var footers = document.querySelectorAll('.el-dialog__footer');
    for (var i = 0; i < footers.length; i++) {
      if (footers[i].getBoundingClientRect().height > 0) {
        var btn = footers[i].querySelector('.el-button--primary');
        if (btn) { btn.click(); return; }
      }
    }
  })()`);
}

async function main() {
  const { erpId } = await getTargetIds();
  const shopName = '上海绰绰';

  // 关闭残留弹窗
  await cdp.eval(erpId, `(function(){
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].getBoundingClientRect().height > 0) {
        var cancel = Array.from(ds[i].querySelectorAll('button')).find(function(b){ return b.innerText.trim() === '取消'; });
        if (cancel) { cancel.click(); continue; }
        var close = ds[i].querySelector('.el-dialog__headerbtn');
        if (close) close.click();
      }
    }
  })()`);
  await sleep(500);

  // 打开弹窗
  await cdp.eval(erpId, `(function(){
    var b = Array.from(document.querySelectorAll('button')).find(function(b){
      return b.getBoundingClientRect().width > 0 && b.innerText.trim() === '下载平台商品';
    });
    if (b) b.click();
  })()`);
  await sleep(1500);

  if (!await getVisibleDialog(erpId)) throw new Error('弹窗未出现');
  console.log('✓ 弹窗已出现');

  // 最多重试3次选店铺
  let ok = false;
  for (let attempt = 1; attempt <= 3; attempt++) {
    console.log(`\n选店铺 (第${attempt}次)...`);
    await openDropdownAndSelect(erpId, shopName);
    ok = await verifySelection(erpId, shopName);
    if (ok) { console.log('✓ 店铺验证通过'); break; }
    console.log('✗ 店铺验证失败，重试...');
  }
  if (!ok) throw new Error('3次重试后店铺选择仍失败');

  // 选全量下载
  await selectFullDownload(erpId);
  await sleep(300);
  console.log('✓ 已选全量下载');

  // 点确认
  await clickConfirm(erpId);
  console.log('✓ 已点确认，等待下载...');

  // 等弹窗关闭（最多120s）
  for (let i = 0; i < 120; i++) {
    await sleep(1000);
    const gone = await cdp.eval(erpId, `(function(){
      var ds = document.querySelectorAll('.el-dialog__wrapper');
      for (var i = 0; i < ds.length; i++) { if (ds[i].getBoundingClientRect().height > 0) return false; }
      return true;
    })()`);
    if (gone) { console.log(`✓ 下载完成 (${i+1}s)`); return; }
    
    // 显示进度
    const progress = await cdp.eval(erpId, `(function(){
      var ds = document.querySelectorAll('.el-dialog__wrapper');
      for (var i = 0; i < ds.length; i++) {
        if (ds[i].getBoundingClientRect().height > 0) {
          var t = ds[i].innerText.replace(/\\s+/g,' ').substring(0, 80);
          return t;
        }
      }
      return '';
    })()`);
    if ((i+1) % 10 === 0 || i < 5) console.log(`  ${i+1}s: ${progress}`);
  }
  throw new Error('下载超时(120s)');
}

main().then(() => process.exit(0)).catch(e => { console.error('FAIL:', e.message); process.exit(1); });
