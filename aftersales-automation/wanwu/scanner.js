'use strict';

const cdp = require('../lib/cdp');
const {
  HOME_URL,
  LOGIN_BUTTON_SELECTOR,
  COUNTER_DEFINITIONS,
  READ_PAGE_STATE_JS,
} = require('./selectors');

const OPEN_SETTLE_MS = 5000;
const LOGIN_SETTLE_MS = 5000;
const LANDING_TIMEOUT_MS = 10000;
const HOME_READY_TIMEOUT_MS = 10000;
const STABLE_READ_INTERVAL_MS = 3000;
const CLOSE_VERIFY_DELAY_MS = 500;
const POLL_INTERVAL_MS = 500;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function assertSafePage(state) {
  if (state && state.riskSignal) {
    throw new Error(`万物页面出现风控提示：${state.riskSignal}`);
  }
}

function assertReadySnapshot(state) {
  assertSafePage(state);
  if (!state || state.kind !== 'home') {
    throw new Error('万物首页状态异常，无法读取待办');
  }
  if (!state.ready) {
    const detail = state.issues && state.issues.length ? state.issues.join('；') : '业务角标尚未就绪';
    throw new Error(`万物首页待办数据不完整：${detail}`);
  }
  for (const definition of COUNTER_DEFINITIONS) {
    const value = state.counts && state.counts[definition.key];
    if (!Number.isInteger(value) || value < 0) {
      throw new Error(`万物${definition.label}角标读取异常`);
    }
  }
  return state;
}

function sameCounts(first = {}, second = {}) {
  return COUNTER_DEFINITIONS.every(definition => first[definition.key] === second[definition.key]);
}

async function readPageState(targetId, dependencies) {
  const state = await dependencies.eval(targetId, READ_PAGE_STATE_JS);
  assertSafePage(state);
  return state;
}

async function waitForLanding(targetId, dependencies, timeoutMs = LANDING_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() <= deadline) {
    dependencies.assertNotAborted();
    latest = await readPageState(targetId, dependencies);
    if (latest.kind === 'home' || latest.kind === 'login') return latest;
    await dependencies.sleep(POLL_INTERVAL_MS);
  }
  throw new Error(`万物后台打开后页面状态未知${latest && latest.title ? `（${latest.title}）` : ''}`);
}

async function waitForReadyHome(targetId, dependencies, timeoutMs = HOME_READY_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() <= deadline) {
    dependencies.assertNotAborted();
    latest = await readPageState(targetId, dependencies);
    if (latest.kind === 'login' && latest.loginError) {
      throw new Error(`万物登录失败：${latest.loginError}`);
    }
    if (latest.kind === 'home' && latest.ready) return assertReadySnapshot(latest);
    await dependencies.sleep(POLL_INTERVAL_MS);
  }
  if (latest && latest.kind === 'login') throw new Error('万物登录后未进入首页');
  const detail = latest && latest.issues && latest.issues.length ? `：${latest.issues.join('；')}` : '';
  throw new Error(`万物首页待办数据等待超时${detail}`);
}

async function closeOwnedTarget(targetId, dependencies) {
  if (!targetId) return null;
  try {
    await dependencies.closeTarget(targetId);
    await dependencies.sleep(CLOSE_VERIFY_DELAY_MS);
    const targets = await dependencies.getTargets();
    if ((targets || []).some(target => target.id === targetId || target.targetId === targetId)) {
      return new Error(`万物扫描标签页关闭后仍存在（${targetId}）`);
    }
    return null;
  } catch (error) {
    return new Error(`万物扫描标签页清理失败：${error.message}`);
  }
}

async function scanWanwu(customDependencies = {}) {
  const dependencies = {
    createTarget: customDependencies.createTarget || cdp.createTarget,
    activateTarget: customDependencies.activateTarget || cdp.activateTarget,
    closeTarget: customDependencies.closeTarget || cdp.closeTarget,
    getTargets: customDependencies.getTargets || cdp.getTargets,
    eval: customDependencies.eval || cdp.eval,
    clickAt: customDependencies.clickAt || cdp.clickAt,
    sleep: customDependencies.sleep || sleep,
    assertNotAborted: customDependencies.assertNotAborted || (() => {}),
    onStage: customDependencies.onStage || (() => {}),
  };

  let targetId = null;
  let result = null;
  let primaryError = null;

  try {
    dependencies.assertNotAborted();
    dependencies.onStage('opening');
    const created = await dependencies.createTarget(HOME_URL);
    targetId = created && (created.id || created.targetId);
    if (!targetId) throw new Error('万物后台标签页创建失败：未返回 targetId');

    await dependencies.activateTarget(targetId);
    await dependencies.sleep(OPEN_SETTLE_MS);
    dependencies.assertNotAborted();

    let landing = await waitForLanding(targetId, dependencies);
    let loggedInDuringScan = false;
    if (landing.kind === 'login') {
      if (!landing.loginButtonVisible) throw new Error('万物登录页未找到“登陆”按钮');
      if (landing.loginError) throw new Error(`万物登录页异常：${landing.loginError}`);
      dependencies.onStage('login');
      await dependencies.clickAt(targetId, LOGIN_BUTTON_SELECTOR);
      loggedInDuringScan = true;
      await dependencies.sleep(LOGIN_SETTLE_MS);
      dependencies.assertNotAborted();
      landing = await waitForReadyHome(targetId, dependencies);
    } else {
      landing = await waitForReadyHome(targetId, dependencies);
    }

    dependencies.onStage('reading');
    const first = assertReadySnapshot(await readPageState(targetId, dependencies));
    await dependencies.sleep(STABLE_READ_INTERVAL_MS);
    dependencies.assertNotAborted();
    const second = assertReadySnapshot(await readPageState(targetId, dependencies));
    if (!sameCounts(first.counts, second.counts)) {
      throw new Error('万物待办数字两次读取不一致，已停止本轮判断');
    }

    result = {
      ok: true,
      targetId,
      loggedInDuringScan,
      counts: second.counts,
      checkedAt: new Date().toISOString(),
    };
  } catch (error) {
    primaryError = error;
  }

  dependencies.onStage('closing');
  const cleanupError = await closeOwnedTarget(targetId, dependencies);
  if (cleanupError) {
    primaryError = primaryError
      ? new Error(`${primaryError.message}；${cleanupError.message}`)
      : cleanupError;
  }
  if (primaryError) throw primaryError;
  return result;
}

module.exports = {
  OPEN_SETTLE_MS,
  LOGIN_SETTLE_MS,
  LANDING_TIMEOUT_MS,
  HOME_READY_TIMEOUT_MS,
  STABLE_READ_INTERVAL_MS,
  CLOSE_VERIFY_DELAY_MS,
  POLL_INTERVAL_MS,
  assertReadySnapshot,
  sameCounts,
  waitForLanding,
  waitForReadyHome,
  closeOwnedTarget,
  scanWanwu,
};
