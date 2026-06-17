'use strict';

const fs = require('fs');
const path = require('path');
const { matchShopName, shopKeyword } = require('./login-state');

const SESSIONS_DIR = path.join(__dirname, '../../../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');

function loadDefaultSteps() {
  return {
    openLogin: require('../../scripts/jl-steps/01-open-login').openLogin,
    readShopName: require('../../scripts/jl-steps/02-read-shop-name').readShopName,
    logout: require('../../scripts/jl-steps/03-logout').logout,
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
  return {
    action: 'logout-inject',
    error: `当前店铺="${loginState.shopName || ''}" 与目标关键字="${shopKeyword(accountNote)}" 不匹配`,
  };
}

async function openAccountFlow(accountNum, options = {}) {
  if (!accountNum) return { success: false, error: '缺少 accountNum' };

  const steps = options.steps || loadDefaultSteps();
  const accountNote = options.note || getAccountNote(accountNum, options.accountsFile);
  if (!accountNote) {
    return { success: false, error: `账号 ${accountNum} 缺少 note/name，无法校验店铺名` };
  }

  const opened = await steps.openLogin();
  if (!opened || !opened.success) {
    return { success: false, error: opened && opened.error ? opened.error : '打开 login 页失败' };
  }

  const targetId = opened.targetId;
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
  if (decision.action === 'logout-inject') {
    const loggedOut = await steps.logout(targetId);
    if (!loggedOut || !loggedOut.success) {
      return { success: false, error: loggedOut && loggedOut.error ? loggedOut.error : '退出登录失败', targetId };
    }
    const injected = await steps.inject(accountNum);
    if (!injected || !injected.success) {
      return { success: false, error: injected && injected.error ? injected.error : '注入目标账号失败', targetId };
    }
    return { ...injected, success: true, action: 'logout-inject', targetId };
  }

  const injected = await steps.inject(accountNum);
  if (!injected || !injected.success) {
    return { success: false, error: injected && injected.error ? injected.error : '注入目标账号失败', targetId };
  }
  return { ...injected, success: true, action: 'inject', targetId };
}

module.exports = {
  openAccountFlow,
  decideOpenAccountAction,
  getAccountNote,
  loadDefaultSteps,
};
