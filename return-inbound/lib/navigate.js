'use strict';
/**
 * navigate.js - ERP 页面导航 + 登录恢复（精简版）
 * 移植自 aftersales-automation/lib/erp/navigate.js
 * 去除：熔断器、health文件、心跳、告警通知
 * 保留：checkLogin / recoverLogin / navigateErp / erpNav / CLOSE_ALL_DIALOGS_JS
 */
const fs = require('fs');
const path = require('path');
const cdp = require('./cdp');
const { sleep, retry, waitFor } = require('./wait');
const { ok, fail } = require('./result');

const PAGE_MAP = {
  '售后工单新版': '#/aftersale/sale_handle_next/',
};

// Session 缓存（6h TTL，与 aftersales-automation 共享同一文件）
const SESSION_TTL_MS = 6 * 60 * 60 * 1000;
const SESSION_CACHE_FILE = path.join(__dirname, '../../aftersales-automation/data/erp-session-cache.json');

function loadSessionCache() {
  try { return JSON.parse(fs.readFileSync(SESSION_CACHE_FILE, 'utf8')); } catch { return {}; }
}
function saveSessionCache(cache) {
  try { fs.writeFileSync(SESSION_CACHE_FILE, JSON.stringify(cache)); } catch {}
}

// ============================================================
// 登录状态检测
// ============================================================
async function checkLogin(targetId) {
  const r = await cdp.eval(targetId, `(function(){
    var onLoginPage = location.href.includes('login');
    var titleOk = document.title.includes('快麦ERP');
    var sessionModal = !!document.querySelector('.inner-login-wrapper');
    return JSON.stringify({ loggedIn: !onLoginPage && titleOk && !sessionModal, sessionExpired: sessionModal });
  })()`);
  return r || { loggedIn: false, sessionExpired: false };
}

// ============================================================
// 登录恢复（单次，失败即抛出）
// ============================================================
async function recoverLogin(targetId) {
  const status = await checkLogin(targetId);
  if (status.loggedIn) return;

  if (status.sessionExpired) {
    // 场景A：session 过期弹窗
    await retry(async () => {
      const clicked = await cdp.eval(targetId, `(function(){
        var cb = document.querySelector('.inner-login-wrapper .iCheck-helper');
        var btn = document.querySelector('.inner-login-wrapper button');
        if (cb) cb.click();
        if (btn) btn.click();
        return !!(cb || btn);
      })()`);
      if (!clicked) throw new Error('login modal not found');
    }, { attempts: 5, delay: 2000 });
    await sleep(6000);
  } else {
    // 场景B：完全退出，触发 Chrome 自动填充
    await cdp.clickAt(targetId, 'input[type="password"]');
    await sleep(2000);
    const filled = await cdp.eval(targetId, `document.querySelector('input[type="password"]') && document.querySelector('input[type="password"]').value.length > 0`);
    if (!filled) throw new Error('Chrome autofill 未触发，需手动登录');
    const loginBtn = await cdp.eval(targetId, `(function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){ return b.textContent.includes('登录'); });
      if (btn) btn.click();
      return !!btn;
    })()`);
    if (!loginBtn) throw new Error('找不到登录按钮');
    await sleep(8000);
  }

  const after = await checkLogin(targetId);
  if (!after.loggedIn) throw new Error('登录恢复失败');
}

// ============================================================
// 等待页面内容加载
// ============================================================
async function waitForPageContent(targetId, timeoutMs = 15000) {
  await waitFor(async () => {
    const r = await cdp.eval(targetId, `(function(){
      var table = document.querySelector('.el-table');
      if (!table) return false;
      var loading = Array.from(document.querySelectorAll('.el-loading-mask')).filter(function(m){
        return window.getComputedStyle(m).display !== 'none';
      });
      return loading.length === 0;
    })()`);
    return r;
  }, { timeout: timeoutMs, interval: 500 });
}

// ============================================================
// 关闭所有可见 Element UI 弹窗
// ============================================================
const CLOSE_ALL_DIALOGS_JS = `(function(){
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(e){
    return window.getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  });
  wrappers.forEach(function(w) {
    var btn = w.querySelector('.el-dialog__closeBtn');
    if (!btn) btn = w.querySelector('button.el-dialog__headerbtn');
    if (btn) btn.click();
  });
  // 清除 v-modal 遮罩
  Array.from(document.querySelectorAll('.v-modal')).forEach(function(m){ m.remove(); });
  return wrappers.length;
})()`;

// ============================================================
// 导航到指定 ERP 页面
// ============================================================
async function navigateErp(targetId, pageName) {
  const hash = PAGE_MAP[pageName];
  if (!hash) throw new Error(`未知页面: ${pageName}`);

  const cache = loadSessionCache();
  const cacheOk = cache.ts && (Date.now() - cache.ts < SESSION_TTL_MS);

  if (cacheOk) {
    const status = await checkLogin(targetId);
    if (status.loggedIn) {
      const currentHash = await cdp.eval(targetId, 'location.hash');
      if (currentHash === hash) {
        return; // 已在目标页面，无需操作
      }
      // 切换标签页
      await retry(async () => {
        await cdp.eval(targetId, `(function(){
          var tabs = Array.from(document.querySelectorAll('li.fix-tab'));
          var target = tabs.find(function(t){ return t.textContent.includes('${pageName}'); });
          if (target) target.click();
        })()`);
        await sleep(1000);
        const h = await cdp.eval(targetId, 'location.hash');
        if (!h.includes(hash.replace('#', ''))) throw new Error('tab switch pending');
      }, { attempts: 6, delay: 500 });
      await waitForPageContent(targetId);
      return;
    }
  }

  // 需要 reload
  await cdp.eval(targetId, 'location.reload()');
  await sleep(3000);
  await waitFor(async () => {
    const r = await cdp.eval(targetId, 'document.readyState === "complete"');
    return r;
  }, { timeout: 20000, interval: 500 });

  const statusAfterReload = await checkLogin(targetId);
  if (!statusAfterReload.loggedIn) {
    await recoverLogin(targetId);
  }

  await retry(async () => {
    await cdp.eval(targetId, `(function(){
      var tabs = Array.from(document.querySelectorAll('li.fix-tab'));
      var target = tabs.find(function(t){ return t.textContent.includes('${pageName}'); });
      if (target) target.click();
    })()`);
    await sleep(1000);
    const h = await cdp.eval(targetId, 'location.hash');
    if (!h.includes(hash.replace('#', ''))) throw new Error('tab switch pending');
  }, { attempts: 6, delay: 500 });

  await waitForPageContent(targetId);
  saveSessionCache({ ts: Date.now(), page: pageName });
}

// ============================================================
// 公共入口（含登录检测）
// ============================================================
async function erpNav(targetId, pageName) {
  try {
    await navigateErp(targetId, pageName);
    return ok({ page: pageName, hash: PAGE_MAP[pageName] });
  } catch (e) {
    return fail(e.message || String(e));
  }
}

module.exports = { erpNav, checkLogin, recoverLogin, navigateErp, waitForPageContent, CLOSE_ALL_DIALOGS_JS };
