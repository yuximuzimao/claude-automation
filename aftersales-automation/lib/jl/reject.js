'use strict';
const { execSync } = require('child_process');
const fs = require('fs');
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 打开物流弹窗（复用 logistics.js 逻辑）
const OPEN_LOGISTICS_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(function(b){
    return b.textContent.trim() === '查看物流' && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到查看物流按钮'});
  btn.click();
  return JSON.stringify({clicked: true});
})()`;

// 切到指定包裹 tab（多包裹时使用）
function makeClickLogisticsTabJS(tabName) {
  return `(function(){
    var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
      return window.getComputedStyle(d).display !== 'none';
    });
    if (!dialogs.length) return JSON.stringify({error:'弹窗未打开'});
    var tab = Array.from(dialogs[0].querySelectorAll('.el-tabs__item')).find(function(t){
      return t.textContent.trim() === '${tabName}';
    });
    if (!tab) return JSON.stringify({error:'tab not found: ${tabName}'});
    tab.click();
    return JSON.stringify({clicked: true});
  })()`;
}

// 获取可见弹窗（el-dialog）的边界坐标
const GET_DIALOG_RECT_JS = `(function(){
  var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!dialogs.length) return JSON.stringify({error:'弹窗未打开'});
  var inner = dialogs[0].querySelector('.el-dialog');
  if (!inner) return JSON.stringify({error:'el-dialog not found'});
  var r = inner.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
})()`;

// 关闭弹窗
const CLOSE_DIALOG_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('.el-dialog__headerbtn, .el-icon-close')).find(function(b){
    return b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error: '未找到关闭按钮'});
  btn.click();
  return JSON.stringify({closed: true});
})()`;

// 检查弹窗是否已关闭（无可见 el-dialog__wrapper）
const CHECK_DIALOG_CLOSED_JS = `(function(){
  var open = Array.from(document.querySelectorAll('.el-dialog__wrapper')).some(function(d){
    return d.getBoundingClientRect().width > 0;
  });
  return JSON.stringify({closed: !open});
})()`;

// 截图 → PIL 裁剪 → 返回裁剪文件路径
async function screenshotDialog(targetId, rect) {
  const fullPath = '/tmp/jl_full.png';
  const cropPath = '/tmp/jl_crop.png';
  const pyPath = '/tmp/jl_crop.py';
  await cdp.screenshot(targetId, fullPath);

  const script = [
    'from PIL import Image',
    `img = Image.open('${fullPath}')`,
    `img.crop((${rect.x}, ${rect.y}, ${rect.x + rect.w}, ${rect.y + rect.h})).save('${cropPath}')`,
  ].join('\n');
  fs.writeFileSync(pyPath, script);
  execSync(`python3 ${pyPath}`, { timeout: 10000 });
  return cropPath;
}

// 获取 鲸灵 cookies（用于图片上传）
const GET_COOKIES_JS = `document.cookie`;

// 上传图片到鲸灵 CDN，返回 image URL
function uploadImage(cookie, filePath) {
  const cmd = `curl -s -b "${cookie.replace(/"/g, '\\"')}" -F "fileUpload=@${filePath};type=image/png" "https://seller-portal.jlsupp.com/base-service/imgUpload"`;
  const raw = execSync(cmd, { timeout: 30000 }).toString();
  const parsed = JSON.parse(raw);
  const url = parsed.entry && parsed.entry[0];
  if (!url) throw new Error(`图片上传失败: ${raw}`);
  return url;
}

// 点「拒绝退款」或「拒绝退货」
const CLICK_REJECT_BTN_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(function(b){
    var txt = b.innerText.trim();
    return (txt === '拒绝退款' || txt === '拒绝退货') && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到拒绝退款/退货按钮'});
  btn.click();
  return JSON.stringify({clicked: true});
})()`;

// 查找「拒绝原因」下拉 input 的 CSS selector（用于 cdp.clickAt 真实点击）
// JS .click() 只触发 click 事件，不触发 mousedown，El-Select 用 mousedown 监听展开
const FIND_REASON_SELECT_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
    var r = i.getBoundingClientRect(); return r.width > 0 && r.height > 0;
  });
  var reasonInp = inputs.find(function(i){ return i.readOnly && i.placeholder === '请选择'; });
  if (!reasonInp) return JSON.stringify({error:'未找到拒绝原因下拉（请选择），可见inputs: ' + inputs.map(function(i){return i.placeholder;}).join('|')});
  return JSON.stringify({found: true});
})()`;

// 验证下拉是否已展开（有可见选项）
const CHECK_SELECT_OPEN_JS = `(function(){
  var items = Array.from(document.querySelectorAll('li.el-select-dropdown__item')).filter(function(li){
    return li.getBoundingClientRect().width > 0;
  });
  var allOptions = Array.from(document.querySelectorAll('li.el-select-dropdown__item')).map(function(li){ return li.textContent.trim(); });
  return JSON.stringify({open: items.length > 0, visibleCount: items.length, allOptions: allOptions});
})()`;

// 点击下拉选项「包裹未退回」
function makeClickReasonOptionJS(optionText) {
  return `(function(){
    var li = Array.from(document.querySelectorAll('li.el-select-dropdown__item')).find(function(e){
      var r = e.getBoundingClientRect();
      return e.textContent.trim().includes('${optionText}') && r.width > 0;
    });
    if (!li) {
      // fallback: span
      var span = Array.from(document.querySelectorAll('span')).find(function(e){
        var r = e.getBoundingClientRect();
        return e.textContent.trim() === '${optionText}' && e.children.length === 0 && r.width > 0;
      });
      if (!span) return JSON.stringify({error:'选项未找到: ${optionText}'});
      span.click();
      return JSON.stringify({clicked: true, via: 'span'});
    }
    li.click();
    return JSON.stringify({clicked: true, via: 'li'});
  })()`;
}

// 填写详细原因 textarea（execCommand 输入）
function makeFillRejectDetailJS(text) {
  const escaped = text.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  return `(function(){
    var ta = Array.from(document.querySelectorAll('textarea')).find(function(t){
      var r = t.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    if (!ta) return JSON.stringify({error:'textarea 未找到'});
    ta.focus();
    document.execCommand('selectAll');
    document.execCommand('insertText', false, '${escaped}');
    return JSON.stringify({filled: ta.value.length > 0, preview: ta.value.substring(0, 50)});
  })()`;
}

// 注入图片 URL 到 WorkOrderStateForm Vue 组件
function makeInjectImageJS(imgUrl) {
  return `(function(){
    function findComp(vm, name, d) {
      if (d > 20 || !vm) return null;
      if ((vm.$options||{}).name === name) return vm;
      for (var i=0; i<(vm.$children||[]).length; i++) {
        var r = findComp(vm.$children[i], name, d+1);
        if (r) return r;
      }
      return null;
    }
    var comp = findComp(document.querySelector('#app').__vue__, 'WorkOrderStateForm', 0);
    if (!comp) return JSON.stringify({error:'WorkOrderStateForm not found'});
    comp.$set(comp.formInfo, 'operaterEvidencePegUrl', ['${imgUrl}']);
    comp.$set(comp, 'templateRefusePictureList', ['${imgUrl}']);
    return JSON.stringify({injected: true, url: '${imgUrl}'});
  })()`;
}

// 点「确认拒绝退款」或「确认拒绝退货」
const CLICK_CONFIRM_REJECT_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(function(b){
    var txt = b.innerText.trim();
    return (txt === '确认拒绝退款' || txt === '确认拒绝退货') && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到确认拒绝退款/退货按钮'});
  btn.click();
  return JSON.stringify({clicked: true});
})()`;

/**
 * 拒绝退款
 * @param {string} targetId   - 鲸灵页面 target
 * @param {string} workOrderNum - 工单号
 * @param {string} reason       - 拒绝原因文字（如"包裹未退回"）
 * @param {string} detail       - 详细原因文案
 * @param {string} [imageUrl]   - 已上传的凭证图片 URL（可选，为空则自动截图上传）
 * @param {string} [packageTab] - 多包裹时指定截图的包裹 tab 名（如"包裹2"）
 */
async function rejectTicket(targetId, workOrderNum, reason, detail, imageUrl, packageTab) {
  try {
    await navigate(targetId, '/business/after-sale-detail', { workOrderNum });
    await sleep(2000);

    // ── Step 1: 截图取证（物流弹窗）──────────────────────────────
    let imgUrl = imageUrl;
    if (!imgUrl) {
      // 打开物流弹窗
      await retry(async () => {
        const openRes = await cdp.eval(targetId, OPEN_LOGISTICS_JS);
        if (openRes.error) throw new Error(`打开物流弹窗: ${openRes.error}`);
      }, { maxRetries: 3, delayMs: 1500, label: `reject-open-logistics ${workOrderNum}` });
      await sleep(2500);

      // 多包裹时切换到对应 tab
      if (packageTab) {
        await retry(async () => {
          const tabRes = await cdp.eval(targetId, makeClickLogisticsTabJS(packageTab));
          if (tabRes.error) throw new Error(tabRes.error);
        }, { maxRetries: 3, delayMs: 1000, label: `reject-tab ${packageTab}` });
        await sleep(1500);
      }

      // 获取弹窗坐标
      const rect = await retry(async () => {
        const r = await cdp.eval(targetId, GET_DIALOG_RECT_JS);
        if (r.error) throw new Error(`获取弹窗坐标: ${r.error}`);
        return r;
      }, { maxRetries: 3, delayMs: 1000, label: `reject-dialog-rect ${workOrderNum}` });

      // 截图并裁剪
      const cropPath = await screenshotDialog(targetId, rect);

      // 关闭弹窗，等待其消失
      await retry(async () => {
        const closeRes = await cdp.eval(targetId, CLOSE_DIALOG_JS);
        if (closeRes.error) throw new Error(`关闭物流弹窗: ${closeRes.error}`);
        await sleep(800);
        const checkRes = await cdp.eval(targetId, CHECK_DIALOG_CLOSED_JS);
        if (!checkRes.closed) throw new Error('物流弹窗未关闭');
      }, { maxRetries: 3, delayMs: 1000, label: `reject-close-dialog ${workOrderNum}` });
      await sleep(800);

      // 上传图片（带重试）
      imgUrl = await retry(async () => {
        const cookie = await cdp.eval(targetId, GET_COOKIES_JS);
        return uploadImage(cookie, cropPath);
      }, { maxRetries: 3, delayMs: 2000, label: `reject-upload-image ${workOrderNum}` });
    }

    // ── Step 2: 打开拒绝表单 ─────────────────────────────────────
    // 若已显示「确认拒绝退款」则表单已打开（前次操作残留），否则点「拒绝退款」
    const alreadyOpen = await cdp.eval(targetId, `
      !!Array.from(document.querySelectorAll('button')).find(function(b){
        var txt = b.innerText.trim();
        return (txt === '确认拒绝退款' || txt === '确认拒绝退货') && b.getBoundingClientRect().width > 0;
      })
    `);

    if (!alreadyOpen) {
      await retry(async () => {
        const rejectRes = await cdp.eval(targetId, CLICK_REJECT_BTN_JS);
        if (rejectRes.error) throw new Error(`点拒绝退款: ${rejectRes.error}`);
      }, { maxRetries: 3, delayMs: 1500, label: `reject-open-form ${workOrderNum}` });
      await sleep(2000);
    }

    // ── Step 3: 选拒绝原因下拉（可选，部分表单无此下拉）────────
    const findSelRes = await cdp.eval(targetId, FIND_REASON_SELECT_JS);
    if (!findSelRes.error) {
      // 用 cdp.clickAt 发送真实 mousedown/mouseup/click（JS .click() 只触发 click，El-Select 用 mousedown，不会展开）
      await retry(async () => {
        await cdp.clickAt(targetId, 'input.el-input__inner[placeholder="请选择"]');
        await sleep(800);
        // 验证下拉确实展开了
        const checkRes = await cdp.eval(targetId, CHECK_SELECT_OPEN_JS);
        if (!checkRes.open) throw new Error(`下拉未展开，可用选项: ${(checkRes.allOptions || []).join('|')}`);
      }, { maxRetries: 3, delayMs: 1000, label: `reject-open-select ${workOrderNum}` });

      await retry(async () => {
        const clickOptRes = await cdp.eval(targetId, makeClickReasonOptionJS(reason));
        if (clickOptRes.error) {
          // 选项不存在时尝试"其他"兜底
          const fallbackRes = await cdp.eval(targetId, makeClickReasonOptionJS('其他'));
          if (fallbackRes.error) throw new Error(`选拒绝原因: ${clickOptRes.error}，可用: ${reason}`);
        }
      }, { maxRetries: 3, delayMs: 800, label: `reject-select-reason ${workOrderNum}` });
      await sleep(800);
    }
    // 若无下拉框则跳过，直接填详细原因

    // ── Step 4: 填详细原因 ────────────────────────────────────────
    await retry(async () => {
      const fillRes = await cdp.eval(targetId, makeFillRejectDetailJS(detail));
      if (fillRes.error) throw new Error(`填详细原因: ${fillRes.error}`);
    }, { maxRetries: 3, delayMs: 1000, label: `reject-fill-detail ${workOrderNum}` });
    await sleep(500);

    // ── Step 5: 注入凭证图片 URL ─────────────────────────────────
    await retry(async () => {
      const injectRes = await cdp.eval(targetId, makeInjectImageJS(imgUrl));
      if (injectRes.error) throw new Error(`注入图片: ${injectRes.error}`);
    }, { maxRetries: 3, delayMs: 1000, label: `reject-inject-image ${workOrderNum}` });
    await sleep(800);

    // ── Step 6: 确认拒绝 ─────────────────────────────────────────
    await retry(async () => {
      const confirmRes = await cdp.eval(targetId, CLICK_CONFIRM_REJECT_JS);
      if (confirmRes.error) throw new Error(`确认拒绝退款: ${confirmRes.error}`);
    }, { maxRetries: 3, delayMs: 1500, label: `reject-confirm ${workOrderNum}` });
    await sleep(3000);

    return ok({ workOrderNum, rejected: true, reason, imageUrl: imgUrl });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { rejectTicket };
