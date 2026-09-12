'use strict';

const HOME_URL = 'https://pop.bbtkids.cn/1.0/uipop/homepage';
const LOGIN_PATH = '/1.0/uipop/login';
const HOME_PATH = '/1.0/uipop/homepage';
const LOGIN_BUTTON_SELECTOR = '#btn-login';

// 只读取明确的叶子待办角标，避免把父级汇总和子项重复相加。
const COUNTER_DEFINITIONS = Object.freeze([
  { key: 'pendingShip', label: '待发货', shortLabel: '待发货', selector: '.ordersendtodo' },
  { key: 'pendingAudit', label: '待审核', shortLabel: '待审核', selector: '.orderexporttodo' },
  { key: 'pendingReissue', label: '待发货补发', shortLabel: '补发', selector: '.reissuetodo' },
  { key: 'shippingWarning', label: '发货超时预警', shortLabel: '发货预警', selector: '.overtimenewtodo' },
  { key: 'logisticsAbnormal', label: '物流异常', shortLabel: '物流异常', selector: '.abnormaltrackingtodo' },
  { key: 'punishment', label: '异常赔付', shortLabel: '异常赔付', selector: '.punishtodo' },
  { key: 'pendingIntercept', label: '待拦截', shortLabel: '待拦截', selector: '.blockordertodo' },
  { key: 'pendingTicket', label: '待处理工单', shortLabel: '工单', selector: '.ticketdealtodo' },
  { key: 'returnAcceptance', label: '退货待验收', shortLabel: '退货验收', selector: '.returntodo' },
  { key: 'addressChange', label: '修改地址', shortLabel: '改地址', selector: '.modifyaddresstodo' },
  { key: 'rejectedDelivery', label: '拒收', shortLabel: '拒收', selector: '.unreturntodo' },
  { key: 'pendingInvoice', label: '待处理发票', shortLabel: '待开票', selector: '.invoicetodo' },
  { key: 'settlementAppeal', label: '待申诉结算调整', shortLabel: '结算申诉', selector: '.adjustmenttodo' },
]);

const READ_PAGE_STATE_JS = `(() => {
  const definitions = ${JSON.stringify(COUNTER_DEFINITIONS)};
  const bodyText = document.body ? document.body.innerText || '' : '';
  const url = location.href;
  const riskTerms = ['captcha', 'anti-bot', '访问过于频繁', '操作频率过高', '人机验证', '安全验证'];
  const lowerText = bodyText.toLowerCase();
  const riskSignal = riskTerms.find(term => lowerText.includes(term.toLowerCase())) || null;
  const visible = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const loginButton = document.querySelector(${JSON.stringify(LOGIN_BUTTON_SELECTOR)});
  const isLogin = url.includes(${JSON.stringify(LOGIN_PATH)}) || visible(loginButton);
  const isHome = url.includes(${JSON.stringify(HOME_PATH)}) && bodyText.includes('供应商名');
  const counts = {};
  const issues = [];

  if (isHome) {
    for (const definition of definitions) {
      const values = Array.from(document.querySelectorAll(definition.selector))
        .map(el => String(el.textContent || '').trim())
        .filter(Boolean);
      if (values.length === 0) {
        issues.push(definition.label + '角标缺失');
        continue;
      }
      if (values.some(value => !/^\\d+$/.test(value))) {
        issues.push(definition.label + '角标不是整数');
        continue;
      }
      const unique = Array.from(new Set(values.map(Number)));
      if (unique.length !== 1) {
        issues.push(definition.label + '重复角标数值不一致');
        continue;
      }
      counts[definition.key] = unique[0];
    }
  }

  const loginErrors = Array.from(document.querySelectorAll('.alert, .error, .help-block, .control-group.error'))
    .filter(visible)
    .map(el => String(el.innerText || el.textContent || '').trim())
    .filter(Boolean)
    .join('；');

  return {
    url,
    title: document.title,
    kind: isHome ? 'home' : (isLogin ? 'login' : 'unknown'),
    ready: isHome && issues.length === 0 && Object.keys(counts).length === definitions.length,
    counts,
    issues,
    riskSignal,
    loginButtonVisible: visible(loginButton),
    loginError: loginErrors || null,
  };
})()`;

module.exports = {
  HOME_URL,
  HOME_PATH,
  LOGIN_PATH,
  LOGIN_BUTTON_SELECTOR,
  COUNTER_DEFINITIONS,
  READ_PAGE_STATE_JS,
};
