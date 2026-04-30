'use strict';
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { sleep, retry, waitFor } = require('../wait');
const { ok, fail } = require('../result');

const CLICK_APPROVE_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(function(b){
    return b.innerText.trim() === '同意退款' && b.getBoundingClientRect().width > 0;
  });
  if (!btn) {
    // 读取页面状态文字，提供有意义的错误信息
    var bodyText = document.body.innerText || '';
    var statusHint = '';
    if (bodyText.includes('系统同意')) statusHint = '工单已被系统自动同意，无需再操作';
    else if (bodyText.includes('等待供应商签收')) statusHint = '等待供应商签收退货中，非待审批状态';
    else if (bodyText.includes('已关闭') || bodyText.includes('工单关闭')) statusHint = '工单已关闭';
    else if (bodyText.includes('已退款') || bodyText.includes('退款成功')) statusHint = '退款已完成';
    else if (bodyText.includes('审核中')) statusHint = '工单审核中，非待操作状态';
    return JSON.stringify({error: statusHint ? ('未找到同意退款按钮：' + statusHint) : '未找到同意退款按钮（工单可能已处理或状态已变更）'});
  }
  btn.click();
  return JSON.stringify({clicked: true});
})()`;

const CLICK_CONFIRM_JS = `(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(function(b){
    return b.innerText.trim() === '确认同意退款' && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到确认同意退款按钮'});
  btn.click();
  return JSON.stringify({clicked: true});
})()`;

// 第三层风险提示弹窗（仅退款-已发货时出现）：
// "若您的货物已经发出，且订单无法拦截，点击同意后将有资损的风险？"
// 按钮文字为 "确 认"（含空格），必须精确匹配
const CLICK_RISK_CONFIRM_JS = `(function(){
  var box = document.querySelector('.el-message-box__wrapper');
  if (!box || box.getBoundingClientRect().width === 0) return JSON.stringify({skipped: 'no risk dialog'});
  var btn = Array.from(box.querySelectorAll('button')).find(function(b){
    return b.innerText.trim() === '确 认' && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到确 认按钮'});
  btn.click();
  return JSON.stringify({clicked: true, riskConfirmed: true});
})()`;

async function approveTicket(targetId, workOrderNum) {
  try {
    await navigate(targetId, '/business/after-sale-detail', { workOrderNum });

    // ── 轮询核验页面是否正确加载了对应工单（最多 10.5s）────────────
    const verifyJS = `(function(){
      var bodyText = document.body.innerText || '';
      if (!bodyText.includes('${workOrderNum}')) {
        return JSON.stringify({notFound: true, error: '工单页面未找到工单号 ${workOrderNum}，可能账号未切换到对应店铺或页面加载失败，请检查账号注入'});
      }
      var hasOrderInfo = bodyText.includes('售后工单信息') || bodyText.includes('售后类型') || bodyText.includes('售后原因');
      if (!hasOrderInfo) {
        return JSON.stringify({error: '工单详情内容未加载，账号可能不匹配（当前店铺无此工单权限）'});
      }
      return JSON.stringify({verified: true});
    })()`;
    try {
      await waitFor(async () => {
        const v = await cdp.eval(targetId, verifyJS);
        if (v.verified) return v;
        // 账号错误是确定性失败，不需要继续轮询
        if (v.notFound) throw new Error(v.error);
        return null;
      }, { timeoutMs: 10500, intervalMs: 1500, label: `verify-ticket ${workOrderNum}` });
    } catch (e) {
      // 工单未找到时反查列表区分"已处理"vs"切错店铺"
      if (e.message && e.message.includes('页面未找到')) {
        await navigate(targetId, '/business/after-sale-list');
        await sleep(2000);
        const listText = await cdp.eval(targetId, 'document.body.innerText || ""');
        if (listText.includes(workOrderNum)) {
          return fail(`工单 ${workOrderNum} 在列表中可见但详情页加载失败，请重试`);
        }
        return fail(`工单 ${workOrderNum} 已不在待处理列表（可能已处理或已关闭）`);
      }
      return fail(e.message.startsWith('waitFor 超时') ? '工单详情未加载超时，账号可能不匹配' : e.message);
    }

    await retry(async () => {
      const step1 = await cdp.eval(targetId, CLICK_APPROVE_JS);
      if (step1.error) throw new Error(`点同意退款: ${step1.error}`);
    }, { maxRetries: 3, delayMs: 1500, label: `approve-step1 ${workOrderNum}` });
    await sleep(1500);

    await retry(async () => {
      const step2 = await cdp.eval(targetId, CLICK_CONFIRM_JS);
      if (step2.error) throw new Error(`点确认同意退款: ${step2.error}`);
    }, { maxRetries: 3, delayMs: 1500, label: `approve-step2 ${workOrderNum}` });
    await sleep(2000);

    // 处理「已发货风险提示」弹窗（出现则点确认，不出现则跳过）
    const step3 = await cdp.eval(targetId, CLICK_RISK_CONFIRM_JS);
    if (step3.error) throw new Error(`点风险确认: ${step3.error}`);
    await sleep(3000);

    return ok({ workOrderNum, approved: true, riskConfirmed: !!step3.riskConfirmed });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { approveTicket };
