'use strict';

const fs = require('fs');
const path = require('path');
const { matchShopName, shopKeyword } = require('./login-state');

const SESSIONS_DIR = path.join(__dirname, '../../../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');

function loadDefaultSteps() {
  return {
    countJlTabs: require('../../scripts/jl-steps/05-count-jl-tabs').countJlTabs,
    closeExtraJlTabs: require('../../scripts/jl-steps/06-close-extra-jl-tabs').closeExtraJlTabs,
    openLogin: require('../../scripts/jl-steps/01-open-login').openLogin,
    readShopName: require('../../scripts/jl-steps/02-read-shop-name').readShopName,
    clearJlData: require('../../scripts/jl-steps/07-clear-jl-data').clearJlData,
    inject: require('../../scripts/jl-steps/04-inject').inject,
  };
}

function getAccountNote(accountNum, accountsFile = ACCOUNTS_FILE) {
  try {
    const accounts = JSON.parse(fs.readFileSync(accountsFile, 'utf8'));
    const account = accounts[String(accountNum)];
    return account ? (account.note || account.name || '') : '';
  } catch {
    return '';
  }
}

function decideOpenAccountAction(loginState, accountNote) {
  if (!loginState || !loginState.success) {
    return { action: 'error', error: loginState && loginState.error ? loginState.error : '读取登录态失败' };
  }
  if (loginState.state === 'logged-out') {
    return { action: 'inject' };
  }
  if (loginState.state !== 'logged-in') {
    return { action: 'error', error: `未知登录态: ${loginState.state || 'empty'}` };
  }

  if (matchShopName(loginState.shopName, accountNote)) {
    return { action: 'reuse' };
  }
  // 错号：不再用破坏性"退出登录"（会让原账号服务端 session 失效），
  // 统一走 inject 分支——先清 cookie 再注入目标账号（2026-06-17）
  return {
    action: 'inject',
    error: `当前店铺="${loginState.shopName || ''}" 与目标关键字="${shopKeyword(accountNote)}" 不匹配`,
  };
}

async function resolveJlTab(steps) {
  const counted = await steps.countJlTabs();
  if (!counted || !counted.success) {
    return { success: false, error: counted && counted.error ? counted.error : '统计鲲灵 tab 失败' };
  }

  if (counted.count === 0) {
    const opened = await steps.openLogin();
    if (!opened || !opened.success) {
      return { success: false, error: opened && opened.error ? opened.error : '打开 login 页失败' };
    }
    return { success: true, targetId: opened.targetId, opened: true };
  }

  if (counted.count === 1) {
    const targetId = counted.tabs && counted.tabs[0] && counted.tabs[0].id;
    if (!targetId) return { success: false, error: '唯一鲲灵 tab 缺少 targetId' };
    return { success: true, targetId, opened: false };
  }

  const closed = await steps.closeExtraJlTabs();
  if (!closed || !closed.success) {
    return { success: false, error: closed && closed.error ? closed.error : '关闭多余鲲灵 tab 失败' };
  }
  if (!closed.keptTargetId) {
    return { success: false, error: '关闭多余鲲灵 tab 后缺少 keptTargetId' };
  }
  return { success: true, targetId: closed.keptTargetId, opened: false };
}

async function openAccountFlow(accountNum, options = {}) {
  if (!accountNum) return { success: false, error: '缺少 accountNum' };

  const steps = options.steps || loadDefaultSteps();
  const accountNote = options.note || getAccountNote(accountNum, options.accountsFile);
  if (!accountNote) {
    return { success: false, error: `账号 ${accountNum} 缺少 note/name，无法校验店铺名` };
  }

  const resolved = await resolveJlTab(steps);
  if (!resolved || !resolved.success) {
    return { success: false, error: resolved && resolved.error ? resolved.error : '解析鲲灵 tab 失败' };
  }

  const targetId = resolved.targetId;
  const loginState = await steps.readShopName(targetId);
  const decision = decideOpenAccountAction(loginState, accountNote);

  if (decision.action === 'error') {
    return { success: false, error: decision.error, targetId };
  }
  if (decision.action === 'reuse') {
    return {
      success: true,
      action: 'reuse',
      targetId,
      accountNum: String(accountNum),
      shopName: loginState.shopName,
      matchedNote: accountNote,
    };
  }
  // inject 分支（未登录 / 错号）：先清当前 tab 旧账号 cookie/storage，再注入目标账号。
  // 清场保证传给平台的只有新账号认证信息，不混旧账号（替代破坏性的退出登录）。
  const cleared = await steps.clearJlData(targetId);
  if (!cleared || !cleared.success) {
    return { success: false, error: cleared && cleared.error ? cleared.error : '注入前清理失败', targetId };
  }
  const injected = await steps.inject(accountNum);
  if (!injected || !injected.success) {
    return { success: false, error: injected && injected.error ? injected.error : '注入目标账号失败', targetId };
  }
  return { ...injected, success: true, action: 'inject', targetId };
}

module.exports = {
  openAccountFlow,
  resolveJlTab,
  decideOpenAccountAction,
  getAccountNote,
  loadDefaultSteps,
};
