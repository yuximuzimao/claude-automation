'use strict';
/**
 * workflow.js - 退货入库核心流程
 * 每单：新建售后工单弹窗 → 原订单运单号筛选 → 填单号 → 处理三路结果
 *       → 拒收退货 → 锦福仓 → 全选 → 创建并收货
 */
const fs = require('fs');
const path = require('path');
const cdp = require('./cdp');
const { sleep, waitFor } = require('./wait');
const { erpNav } = require('./navigate');

const RESULTS_FILE = path.join(__dirname, '../data/results.txt');

// ============================================================
// 工具函数
// ============================================================

// 在弹窗内找可见按钮（按文字精确匹配）
const FIND_VISIBLE_BTN_JS = (text) => `(function(){
  var btns = Array.from(document.querySelectorAll('button'));
  return btns.find(function(b){
    var r = b.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'') === ${JSON.stringify(text)};
  });
})()`;

// 找可见按钮并点击（JS click）
async function clickVisibleBtn(targetId, text, timeoutMs = 8000) {
  await waitFor(async () => {
    const clicked = await cdp.eval(targetId, `(function(){
      var btns = Array.from(document.querySelectorAll('button'));
      var btn = btns.find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'') === ${JSON.stringify(text)};
      });
      if (btn) { btn.click(); return true; }
      return false;
    })()`);
    return clicked;
  }, { timeoutMs, intervalMs: 500, label: `clickVisibleBtn(${text})` });
}

// 物理点击可见元素（by selector in container）
async function physicalClickVisible(targetId, containerSel, itemSel) {
  const rect = await cdp.eval(targetId, `(function(){
    var container = document.querySelector(${JSON.stringify(containerSel)});
    var el = container ? container.querySelector(${JSON.stringify(itemSel)}) : document.querySelector(${JSON.stringify(itemSel)});
    if (!el) return null;
    var r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return null;
    return { x: r.left + r.width/2, y: r.top + r.height/2 };
  })()`);
  if (!rect) throw new Error(`physicalClickVisible: not found or not visible: ${itemSel}`);
  await cdp.eval(targetId, `(function(){
    var container = document.querySelector(${JSON.stringify(containerSel)});
    var el = container ? container.querySelector(${JSON.stringify(itemSel)}) : document.querySelector(${JSON.stringify(itemSel)});
    if (el) el.scrollIntoView({ block: 'center' });
  })()`);
  await sleep(200);
  const rect2 = await cdp.eval(targetId, `(function(){
    var container = document.querySelector(${JSON.stringify(containerSel)});
    var el = container ? container.querySelector(${JSON.stringify(itemSel)}) : document.querySelector(${JSON.stringify(itemSel)});
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return { x: r.left + r.width/2, y: r.top + r.height/2 };
  })()`);
  const pt = rect2 || rect;
  await cdp.eval(targetId, `(function(){
    var container = document.querySelector(${JSON.stringify(containerSel)});
    var el = container ? container.querySelector(${JSON.stringify(itemSel)}) : document.querySelector(${JSON.stringify(itemSel)});
    if (el) el.click();
  })()`);
}

// ============================================================
// Step 1: 确保弹窗已打开
// ============================================================
async function ensureDialogOpen(targetId) {
  const isOpen = await cdp.eval(targetId, `(function(){
    var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper'));
    return wrappers.some(function(w){
      var r = w.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
  })()`);
  if (isOpen) return;

  // 点"新建售后工单"按钮
  await clickVisibleBtn(targetId, '新建售后工单', 10000);
  await waitFor(async () => {
    return await cdp.eval(targetId, `(function(){
      var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper'));
      return wrappers.some(function(w){
        var r = w.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
    })()`);
  }, { timeoutMs: 10000, intervalMs: 500, label: '等待弹窗打开' });
}

// ============================================================
// Step 2: 确保筛选项为"原订单运单号"
// 弹窗内有多个 el-select，index=1 才是查询维度筛选（"平台订单号"/"原订单运单号"）
// ============================================================
async function ensureFilterCorrect(targetId) {
  const current = await cdp.eval(targetId, `(function(){
    var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    if (!wrapper) return null;
    // index=1：查询维度筛选（排除 index=0 的"订单/出库单"类型 select）
    var sels = Array.from(wrapper.querySelectorAll('.el-select')).filter(function(s){
      var r = s.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var sel = sels[1]; // 第二个可见 el-select
    var inp = sel && sel.querySelector('.el-input__inner');
    return inp ? inp.value : null;
  })()`);

  if (current === '原订单运单号') return;

  // 获取 index=1 select 的坐标，物理点击展开
  const selRect = await cdp.eval(targetId, `(function(){
    var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    if (!wrapper) return null;
    var sels = Array.from(wrapper.querySelectorAll('.el-select')).filter(function(s){
      var r = s.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var sel = sels[1];
    if (!sel) return null;
    var r = sel.getBoundingClientRect();
    return { x: r.left + r.width/2, y: r.top + r.height/2 };
  })()`);
  if (!selRect) throw new Error('找不到筛选下拉框(index=1)');

  // JS click inp 展开下拉
  await cdp.eval(targetId, `(function(){
    var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var sels = Array.from(wrapper.querySelectorAll('.el-select')).filter(function(s){
      var r = s.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var sel = sels[1];
    var inp = sel && sel.querySelector('.el-input__inner');
    if (inp) inp.click();
  })()`);
  await sleep(600);

  // 等对应面板展开（包含"原订单运单号"选项，且该选项 visible）
  await waitFor(async () => {
    const clicked = await cdp.eval(targetId, `(function(){
      // 找所有 display:block 的 el-select-dropdown 面板
      var panels = Array.from(document.querySelectorAll('.el-select-dropdown')).filter(function(p){
        var s = window.getComputedStyle(p);
        return s.display !== 'none';
      });
      for (var i = 0; i < panels.length; i++) {
        var items = Array.from(panels[i].querySelectorAll('.el-select-dropdown__item'));
        var opt = items.find(function(o){ return o.textContent.includes('原订单运单号'); });
        if (opt) { opt.click(); return true; }
      }
      return false;
    })()`);
    return clicked;
  }, { timeoutMs: 5000, intervalMs: 300, label: '选择原订单运单号' });

  // 确认切换成功
  await waitFor(async () => {
    return await cdp.eval(targetId, `(function(){
      var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      var sels = Array.from(wrapper.querySelectorAll('.el-select')).filter(function(s){
        var r = s.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      var sel = sels[1];
      var inp = sel && sel.querySelector('.el-input__inner');
      return inp && inp.value === '原订单运单号';
    })()`);
  }, { timeoutMs: 5000, intervalMs: 300, label: '确认筛选已切换' });
}

// ============================================================
// Step 3: 填入快递单号并回车
// ============================================================
async function fillTracking(targetId, tracking) {
  // 找输入框并物理点击聚焦
  const inputRect = await cdp.eval(targetId, `(function(){
    var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    if (!wrapper) return null;
    // 找不是 select 内的 input（排除筛选下拉）
    var inputs = Array.from(wrapper.querySelectorAll('input[type="text"], input:not([type])'));
    var inp = inputs.find(function(i){
      var r = i.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && !i.closest('.el-select');
    });
    if (!inp) return null;
    var r = inp.getBoundingClientRect();
    return { x: r.left + r.width/2, y: r.top + r.height/2 };
  })()`);
  if (!inputRect) throw new Error('找不到快递单号输入框');

  // JS focus + select 聚焦输入框，再 insertText
  await cdp.eval(targetId, `(function(){
    var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var inputs = Array.from(wrapper.querySelectorAll('input[type="text"], input:not([type])'));
    var inp = inputs.find(function(i){
      var r = i.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && !i.closest('.el-select');
    });
    if (inp) { inp.focus(); inp.select(); }
  })()`);
  await sleep(200);

  // 用 Input.insertText 填入（必须通过 cdp typeText）
  await cdp.typeText(targetId, tracking);
  await sleep(300);

  // 回车
  await cdp.key(targetId, 'Enter');
}

// ============================================================
// Step 4: 等待三路结果
// ============================================================
// 返回: { type: 'error' | 'association' | 'order' }
async function waitForSearchResult(targetId) {
  return await waitFor(async () => {
    return await cdp.eval(targetId, `(function(){
      // 路径1: 错误弹窗（未查询到订单）
      var msgBox = Array.from(document.querySelectorAll('.el-message-box__wrapper')).find(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      if (msgBox) return { type: 'error' };

      // 路径2: 关联弹窗（标题"提示"，有"继续关联"按钮）
      var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      var assocDialog = dialogs.find(function(d){
        var title = d.querySelector('.el-dialog__title');
        return title && title.textContent.includes('提示');
      });
      if (assocDialog) {
        var hasBtn = Array.from(assocDialog.querySelectorAll('button')).some(function(b){
          return b.textContent.replace(/\\s/g,'').includes('继续关联');
        });
        if (hasBtn) return { type: 'association', dialog: true };
      }

      // 路径3: 订单已加载（主弹窗表格有行）
      var mainDialog = dialogs.find(function(d){
        var title = d.querySelector('.el-dialog__title');
        return !title || !title.textContent.includes('提示');
      });
      if (mainDialog) {
        var rows = mainDialog.querySelectorAll('.el-table__body tbody tr');
        if (rows.length > 0) return { type: 'order' };
      }
      return null;
    })()`);
  }, { timeoutMs: 20000, intervalMs: 600, label: '等待搜索结果' });
}

// ============================================================
// Step 5: 点拒收退货
// ============================================================
async function selectRefusalType(targetId) {
  await waitFor(async () => {
    const clicked = await cdp.eval(targetId, `(function(){
      var labels = Array.from(document.querySelectorAll('.el-radio__label, label'));
      var lbl = labels.find(function(l){
        var r = l.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && l.textContent.includes('拒收退货');
      });
      if (!lbl) return false;
      var radio = lbl.closest('.el-radio') || lbl.previousElementSibling;
      if (radio) { radio.click(); return true; }
      lbl.click(); return true;
    })()`);
    return clicked;
  }, { timeoutMs: 8000, intervalMs: 500, label: '点击拒收退货' });
  await sleep(500);
}

// ============================================================
// Step 6: 改退货仓库为锦福仓
// ============================================================
async function selectWarehouse(targetId) {
  // 找"退货仓库"标签旁的 el-select 并物理点击
  const selRect = await cdp.eval(targetId, `(function(){
    // 找包含"退货仓库"文字的 label 附近的 el-select
    var labels = Array.from(document.querySelectorAll('.el-form-item__label, label'));
    var lbl = labels.find(function(l){ return l.textContent.includes('退货仓库'); });
    if (!lbl) return null;
    var formItem = lbl.closest('.el-form-item');
    if (!formItem) return null;
    var sel = formItem.querySelector('.el-select');
    if (!sel) return null;
    var r = sel.getBoundingClientRect();
    return r.width > 0 ? { x: r.left + r.width/2, y: r.top + r.height/2 } : null;
  })()`);
  if (!selRect) throw new Error('找不到退货仓库下拉框');

  // JS click 展开退货仓库下拉
  await cdp.eval(targetId, `(function(){
    var labels = Array.from(document.querySelectorAll('.el-form-item__label, label'));
    var lbl = labels.find(function(l){ return l.textContent.includes('退货仓库'); });
    var formItem = lbl && lbl.closest('.el-form-item');
    var sel = formItem && formItem.querySelector('.el-select');
    if (sel) sel.click();
  })()`);
  await sleep(600);

  // 等下拉出现后点"锦福仓"
  await waitFor(async () => {
    const clicked = await cdp.eval(targetId, `(function(){
      var options = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
      var opt = options.find(function(o){
        var r = o.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && o.textContent.includes('锦福仓');
      });
      if (opt) { opt.click(); return true; }
      return false;
    })()`);
    return clicked;
  }, { timeoutMs: 6000, intervalMs: 400, label: '选择锦福仓' });

  // 确认仓库已切换
  await waitFor(async () => {
    return await cdp.eval(targetId, `(function(){
      var labels = Array.from(document.querySelectorAll('.el-form-item__label, label'));
      var lbl = labels.find(function(l){ return l.textContent.includes('退货仓库'); });
      var formItem = lbl && lbl.closest('.el-form-item');
      var inp = formItem && formItem.querySelector('.el-select .el-input__inner');
      return inp && inp.value.includes('锦福仓');
    })()`);
  }, { timeoutMs: 5000, intervalMs: 400, label: '确认锦福仓已选中' });
}

// ============================================================
// Step 7: 勾选"继续创建下一笔单据"（仅首次，每次都检查）
// ============================================================
async function ensureContinueNextChecked(targetId) {
  const checked = await cdp.eval(targetId, `(function(){
    var labels = Array.from(document.querySelectorAll('label, .el-checkbox__label'));
    var lbl = labels.find(function(l){ return l.textContent.includes('继续创建下一笔'); });
    if (!lbl) return true; // 找不到就跳过
    var checkbox = lbl.closest('.el-checkbox') || lbl.previousElementSibling;
    if (checkbox) {
      var input = checkbox.querySelector('input[type="checkbox"]');
      return input ? input.checked : false;
    }
    return false;
  })()`);
  if (checked) return;

  await cdp.eval(targetId, `(function(){
    var labels = Array.from(document.querySelectorAll('label, .el-checkbox__label'));
    var lbl = labels.find(function(l){ return l.textContent.includes('继续创建下一笔'); });
    if (!lbl) return;
    var checkbox = lbl.closest('.el-checkbox') || lbl;
    checkbox.click();
  })()`);
  await sleep(300);
}

// ============================================================
// Step 8: 全选商品
// ============================================================
async function selectAllItems(targetId) {
  await waitFor(async () => {
    const clicked = await cdp.eval(targetId, `(function(){
      // 找表头全选 checkbox（el-table 的 header checkbox）
      var headerCbs = Array.from(document.querySelectorAll('.el-table__header .el-checkbox, .el-table__header input[type="checkbox"]'));
      var cb = headerCbs.find(function(c){
        var r = c.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      if (cb) { cb.click(); return true; }
      // fallback: "全部勾选"按钮
      var btns = Array.from(document.querySelectorAll('button'));
      var btn = btns.find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && b.textContent.includes('全部勾选');
      });
      if (btn) { btn.click(); return true; }
      return false;
    })()`);
    return clicked;
  }, { timeoutMs: 8000, intervalMs: 500, label: '全选商品' });
  await sleep(300);
}

// ============================================================
// Step 9: 点"创建并收货" + 等成功信号
// ============================================================
async function createAndReceive(targetId) {
  // 找按钮坐标（物理点击）
  const btnRect = await cdp.eval(targetId, `(function(){
    var btns = Array.from(document.querySelectorAll('button'));
    var btn = btns.find(function(b){
      var r = b.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'').includes('创建并收货');
    });
    if (!btn) return null;
    var r = btn.getBoundingClientRect();
    return { x: r.left + r.width/2, y: r.top + r.height/2 };
  })()`);
  if (!btnRect) throw new Error('找不到"创建并收货"按钮');

  // 物理点击
  await cdp.eval(targetId, `(function(){
    var btns = Array.from(document.querySelectorAll('button'));
    var btn = btns.find(function(b){
      var r = b.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'').includes('创建并收货');
    });
    if (btn) btn.click();
  })()`);

  // 短暂等待，可能弹出二次确认框
  await sleep(1500);

  // 处理可能的确认弹窗（"该快递单号被工单xxx关联过N次，确定继续创建工单吗？"）
  const hasConfirm = await cdp.eval(targetId, `(function(){
    var boxes = Array.from(document.querySelectorAll('.el-message-box__wrapper')).filter(function(w){
      var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    return boxes.some(function(b){
      return b.textContent.includes('关联过') || b.textContent.includes('确定继续');
    });
  })()`);
  if (hasConfirm) {
    await clickVisibleBtn(targetId, '确定', 5000);
    await sleep(500);
  }

  // 等成功信号：输入框为空 + 表格行数=0（弹窗重置为空白状态）
  await waitFor(async () => {
    return await cdp.eval(targetId, `(function(){
      var wrapper = Array.from(document.querySelectorAll('.el-dialog__wrapper')).find(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      if (!wrapper) return false; // 弹窗关闭了 = 也算成功（继续下一笔未勾选时）
      var inputs = Array.from(wrapper.querySelectorAll('input[type="text"], input:not([type])'));
      var inp = inputs.find(function(i){
        var r = i.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !i.closest('.el-select');
      });
      var inputEmpty = !inp || inp.value === '';
      var rows = wrapper.querySelectorAll('.el-table__body tbody tr');
      return inputEmpty && rows.length === 0;
    })()`);
  }, { timeoutMs: 30000, intervalMs: 800, label: '等待创建成功' });
}

// ============================================================
// 单条处理主流程
// ============================================================
async function processOne(targetId, tracking) {
  process.stdout.write(`[${tracking}] 开始处理\n`);

  await ensureDialogOpen(targetId);
  await ensureFilterCorrect(targetId);
  await fillTracking(targetId, tracking);

  const result = await waitForSearchResult(targetId);
  process.stdout.write(`[${tracking}] 搜索结果: ${result.type}\n`);

  if (result.type === 'error') {
    // 关闭错误弹窗
    await clickVisibleBtn(targetId, '关闭', 5000).catch(() =>
      clickVisibleBtn(targetId, '确定', 5000)
    );
    await sleep(500);
    return '未出库无需入库';
  }

  if (result.type === 'association') {
    // 物理点击"继续关联"
    const assocRect = await cdp.eval(targetId, `(function(){
      var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      var d = dialogs.find(function(d){
        var title = d.querySelector('.el-dialog__title');
        return title && title.textContent.includes('提示');
      });
      if (!d) return null;
      var btns = Array.from(d.querySelectorAll('button'));
      var btn = btns.find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'').includes('继续关联');
      });
      if (!btn) return null;
      var r = btn.getBoundingClientRect();
      return { x: r.left + r.width/2, y: r.top + r.height/2 };
    })()`);

    if (!assocRect) throw new Error('找不到继续关联按钮坐标');
    // 物理点击
    await cdp.eval(targetId, `(function(){
      var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(w){
        var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
      });
      var d = dialogs.find(function(d){
        var title = d.querySelector('.el-dialog__title');
        return title && title.textContent.includes('提示');
      });
      if (!d) return;
      var btns = Array.from(d.querySelectorAll('button'));
      var btn = btns.find(function(b){
        var r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && b.textContent.replace(/\\s/g,'').includes('继续关联');
      });
      if (btn) btn.click();
    })()`);

    // 等关联弹窗消失 + 订单加载
    await waitFor(async () => {
      return await cdp.eval(targetId, `(function(){
        var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(w){
          var r = w.getBoundingClientRect(); return r.width > 0 && r.height > 0;
        });
        var hasAssoc = dialogs.some(function(d){
          var title = d.querySelector('.el-dialog__title');
          return title && title.textContent.includes('提示');
        });
        if (hasAssoc) return false;
        var mainDialog = dialogs[0];
        if (!mainDialog) return false;
        var rows = mainDialog.querySelectorAll('.el-table__body tbody tr');
        return rows.length > 0;
      })()`);
    }, { timeoutMs: 12000, intervalMs: 600, label: '等关联弹窗消失+订单加载' });
  }

  // 订单已加载
  await selectRefusalType(targetId);
  await selectWarehouse(targetId);
  await ensureContinueNextChecked(targetId);
  await selectAllItems(targetId);
  await createAndReceive(targetId);

  return '已入库';
}

// ============================================================
// ERP target 查找（供外部调用方复用）
// ============================================================
async function findErpTarget() {
  const targets = await cdp.getTargets();
  const erpTarget = targets.find(t => t.url && t.url.includes('superboss.cc') && t.type === 'page');
  if (!erpTarget) throw new Error('未找到快麦ERP标签页，请先在Chrome中打开ERP');
  return erpTarget.id;
}

// ============================================================
// 批量入口（CLI 兼容）
// ============================================================
async function processAll(trackingNumbers) {
  // 清空 results
  fs.writeFileSync(RESULTS_FILE, '');

  const targetId = await findErpTarget();
  process.stdout.write(`[init] ERP tab: ${targetId}\n`);

  // 导航到售后工单新版
  const navResult = await erpNav(targetId, '售后工单新版');
  if (!navResult.success) throw new Error(`导航失败: ${navResult.error}`);
  process.stdout.write(`[init] 导航成功\n`);

  for (const tracking of trackingNumbers) {
    const t = tracking.trim();
    if (!t) continue;
    try {
      const status = await processOne(targetId, t);
      const line = `${t}\t${status}\n`;
      fs.appendFileSync(RESULTS_FILE, line);
      process.stdout.write(`[${t}] → ${status}\n`);
    } catch (e) {
      const line = `${t}\t错误:${e.message}\n`;
      fs.appendFileSync(RESULTS_FILE, line);
      process.stderr.write(`[${t}] 失败: ${e.message}\n`);
    }
  }

  process.stdout.write(`\n全部完成，结果写入 data/results.txt\n`);
}

module.exports = { processAll, processOne, findErpTarget };
