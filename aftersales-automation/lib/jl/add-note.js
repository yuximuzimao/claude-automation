'use strict';
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 三步独立执行，每步之间 sleep 1s（见 RULES 3.7）
// Step 1：点「致内部」按钮（精确匹配工单号，找最近的按钮）
function makeClickNoteButtonJS(workOrderNum) {
  return `(function(){
    var ticketNum = '${workOrderNum}';
    var spans = Array.from(document.querySelectorAll('span'));
    var ticket = spans.filter(function(el){
      return el.innerText && el.innerText.includes(ticketNum);
    })[0];
    if (!ticket) return JSON.stringify({error:'未找到工单号 ' + ticketNum});
    var ticketY = ticket.getBoundingClientRect().top;
    var btns = Array.from(document.querySelectorAll('button')).filter(function(b){
      return b.innerText.trim() === '致内部' && b.getBoundingClientRect().width > 0;
    });
    if (!btns.length) return JSON.stringify({error:'未找到致内部按钮'});
    var btn = btns.reduce(function(a, b){
      return Math.abs(b.getBoundingClientRect().top - ticketY) < Math.abs(a.getBoundingClientRect().top - ticketY) ? b : a;
    });
    ['mousedown','mouseup','click'].forEach(function(t){
      btn.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true}));
    });
    return JSON.stringify({clicked: true, btnY: btn.getBoundingClientRect().top, ticketY: ticketY});
  })()`;
}

// Step 2：填写 textarea
function makeFillTextareaJS(text) {
  // 转义单引号
  const escaped = text.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  return `(function(){
    var ta = document.querySelector('textarea[placeholder="添加内部备注"]');
    if (!ta) return JSON.stringify({error:'备注输入框未找到，弹窗可能未打开'});
    ta.focus();
    document.execCommand('selectAll');
    document.execCommand('insertText', false, '${escaped}');
    return JSON.stringify({filled: ta.value.length > 0, value: ta.value.substring(0, 50)});
  })()`;
}

// Step 3：提交「添加」按钮
const SUBMIT_NOTE_JS = `(function(){
  var addBtn = Array.from(document.querySelectorAll('button')).filter(function(b){
    return b.innerText.trim() === '添加' && b.getBoundingClientRect().width > 0;
  })[0];
  if (!addBtn) return JSON.stringify({error:'未找到添加按钮'});
  ['mousedown','mouseup','click'].forEach(function(t){
    addBtn.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true}));
  });
  return JSON.stringify({submitted: true});
})()`;

async function addNote(targetId, workOrderNum, text) {
  try {
    // 确保在列表页（致内部按钮在列表行上）
    const currentUrl = await cdp.eval(targetId, 'window.location.href');
    if (!currentUrl.includes('after-sale-list')) {
      await navigate(targetId, '/business/after-sale-list');
    }

    // Step 1
    await retry(async () => {
      const step1 = await cdp.eval(targetId, makeClickNoteButtonJS(workOrderNum));
      if (step1.error) throw new Error(`Step1: ${step1.error}`);
    }, { maxRetries: 3, delayMs: 1500, label: `add-note-step1 ${workOrderNum}` });
    await sleep(1500);

    // Step 2
    await retry(async () => {
      const step2 = await cdp.eval(targetId, makeFillTextareaJS(text));
      if (step2.error) throw new Error(`Step2: ${step2.error}`);
      if (!step2.filled) throw new Error('Step2: 填写备注失败，textarea 为空');
    }, { maxRetries: 3, delayMs: 1000, label: `add-note-step2 ${workOrderNum}` });
    await sleep(800);

    // Step 3
    await retry(async () => {
      const step3 = await cdp.eval(targetId, SUBMIT_NOTE_JS);
      if (step3.error) throw new Error(`Step3: ${step3.error}`);
    }, { maxRetries: 3, delayMs: 1000, label: `add-note-step3 ${workOrderNum}` });
    await sleep(2000);
    return ok({ workOrderNum, note: text });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { addNote };
