'use strict';
// 浏览器生命周期管理：reset + 健康检查 + 连接锁定
// 移植自 aftersales-automation/test/runner.js

const path = require('path');
const PROJECT_ROOT = path.join(__dirname, '../..');
const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
const { sleep, waitFor } = require(path.join(PROJECT_ROOT, 'lib/wait'));

// 测试上下文：启动时锁定连接方式
const testContext = {
  connectionMode: null,  // 'proxy' | 'direct'
  erpId: null,
  jlId: null,
};

/**
 * 初始化测试上下文：健康检查 + 锁定连接 + 获取 target IDs
 */
async function initTestContext() {
  const health = await cdp.healthCheck();
  if (!health.ok) {
    throw new Error(`CDP 连接失败: ${health.error}`);
  }
  testContext.connectionMode = health.mode;

  const targets = await cdp.getTargets();
  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  const erp = targets.find(t => t.url && t.url.includes('superboss.cc'));

  if (!jl) throw new Error('鲸灵标签页未找到，请确认 Chrome 已打开鲸灵页面');
  if (!erp) throw new Error('ERP 标签页未找到，请确认 Chrome 已打开快麦 ERP 页面');

  testContext.jlId = jl.targetId;
  testContext.erpId = erp.targetId;

  return testContext;
}

/**
 * 复原 ERP 页面（reload + 登录检查/恢复）
 * 每次测试前调用，保证页面状态干净
 */
async function resetErp(targetId) {
  // 等待上一次操作完全结束
  await sleep(5000);

  // reload：可能 ECONNRESET，retry
  for (let i = 0; i < 3; i++) {
    try {
      await cdp.eval(targetId, 'location.reload()');
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(2000);
      } else {
        throw e;
      }
    }
  }

  // reload 后等页面稳定
  await sleep(3000);

  // 检查登录状态
  const CHECK_JS = `(function(){
    var sessionExpired = !!document.querySelector('.inner-login-wrapper');
    var notErp = !document.title.includes('快麦ERP--');
    return JSON.stringify({sessionExpired, notErp, title: document.title});
  })()`;

  let status;
  for (let i = 0; i < 3; i++) {
    try {
      status = await cdp.eval(targetId, CHECK_JS);
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(1500);
      } else {
        throw e;
      }
    }
  }

  if (status.sessionExpired || status.notErp) {
    // 尝试恢复登录
    const { recoverLogin } = require(path.join(PROJECT_ROOT, 'lib/navigate'));
    if (process.stderr) process.stderr.write('[test/browser] ERP 会话过期，尝试恢复登录\n');
    await recoverLogin(targetId);
  }

  await sleep(500);
}

/**
 * 复原鲸灵页面（reload + readyState 等待）
 */
async function resetJl(targetId) {
  await sleep(5000);

  for (let i = 0; i < 3; i++) {
    try {
      await cdp.eval(targetId, 'location.reload()');
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(2000);
      } else {
        throw e;
      }
    }
  }

  await sleep(3000);
  await waitFor(
    async () => {
      try {
        const state = await cdp.eval(targetId, 'document.readyState');
        return state === 'complete';
      } catch (e) {
        if (e.message && e.message.includes('ECONNRESET')) return false;
        throw e;
      }
    },
    { timeoutMs: 15000, intervalMs: 500, label: '鲸灵页面刷新' }
  );
  await sleep(1000);

  const url = await cdp.eval(targetId, 'window.location.href');
  if (url.includes('login') || url.includes('sso')) {
    throw new Error(`鲸灵登录已失效，URL: ${url}，请手动重新登录`);
  }
}

/**
 * 清除 session cache 文件
 */
function clearSessionCache() {
  const fs = require('fs');
  const cacheFile = path.join(PROJECT_ROOT, 'data/erp-session-cache.json');
  try { fs.unlinkSync(cacheFile); } catch {}
}

module.exports = {
  testContext,
  initTestContext,
  resetErp,
  resetJl,
  clearSessionCache,
};
