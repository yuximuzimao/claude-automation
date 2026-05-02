'use strict';
// 移植自售后工单项目 lib/erp/navigate.js
// v2: 新增 session 缓存、自动登录恢复、页面内容轮询等待
const fs = require('fs');
const path = require('path');
const cdp = require('./cdp');
const { sleep, retry } = require('./wait');

const PAGE_MAP = {
  '商品档案V2': '#/prod/parallel/',
  '商品对应表': '#/prod/prod_correspondence_next/',
};

// ── Session 缓存 ────────────────────────────────────────────────────────────
// 持久化到文件，跨进程复用（与 aftersales-automation 共享同一缓存文件）
const SESSION_TTL_MS = 6 * 60 * 60 * 1000; // 6小时
const SESSION_CACHE_FILE = path.join(__dirname, '../data/erp-session-cache.json');

function loadSessionCache() {
  try {
    return JSON.parse(fs.readFileSync(SESSION_CACHE_FILE, 'utf8'));
  } catch { return {}; }
}

function saveSessionCache(cache) {
  try {
    fs.writeFileSync(SESSION_CACHE_FILE, JSON.stringify(cache));
  } catch {}
}

// ── 登录检测 ────────────────────────────────────────────────────────────────
const CHECK_LOGIN_JS = `(function(){
  var isOut = window.location.href.includes('login') || !document.title.includes('快麦ERP--');
  var sessionExpired = !!document.querySelector('.inner-login-wrapper');
  return JSON.stringify({loggedIn: !isOut && !sessionExpired, title: document.title, url: window.location.href, sessionExpired: sessionExpired});
})()`;

async function checkLogin(targetId) {
  const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

// ── 自动登录恢复 ────────────────────────────────────────────────────────────
// 两种场景：
//   A. Session 超时弹窗（.inner-login-wrapper）：勾协议 → 点登录
//   B. 完全退出到登录页（URL 含 login / title 变化）：点密码框触发自动填充 → 点登录 → 协议弹窗
async function recoverLogin(targetId) {
  if (process.env.VERBOSE) process.stderr.write('[navigate] 尝试恢复登录\n');
  await cdp.eval(targetId, 'location.reload()');

  // 轮询等待页面就绪：登录页+密码框出现，或 session 弹窗出现（最多 20s）
  let hasModal = false;
  let isLoginPage = false;
  let pwdFieldReady = false;
  for (let i = 0; i < 20; i++) {
    await sleep(1000);
    const st = await checkLogin(targetId);
    hasModal = st.sessionExpired;
    isLoginPage = !st.loggedIn && !st.sessionExpired;
    if (hasModal) break;
    if (isLoginPage) {
      const hasPwd = await cdp.eval(targetId, '!!document.querySelector("input[type=password]")');
      if (hasPwd) { pwdFieldReady = true; break; }
    }
  }

  if (isLoginPage && pwdFieldReady) {
    // 场景 B：完全退出到登录页
    await sleep(2000); // 等 Chrome 密码管理器注册表单

    // Step 1: 点密码框触发浏览器自动填充
    await cdp.clickAt(targetId, 'input[type="password"]');
    await sleep(2000);

    const passwordFilled = await cdp.eval(targetId, `(function(){
      var pwd = document.querySelector('input[type="password"]');
      return !!(pwd && pwd.value && pwd.value.length > 0);
    })()`);
    if (!passwordFilled) {
      throw new Error('ERP已完全退出登录且密码未自动填充，请手动重新登录ERP后重试');
    }

    // Step 2: 点登录按钮（不提前勾协议，让弹窗自然出现）
    await cdp.eval(targetId, `(function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){
        return b.textContent.indexOf('登') >= 0;
      });
      if (btn) btn.click();
    })()`);
    await sleep(2000);

    // Step 3: 若出现协议确认弹窗（.rc-kmui-com-dlg），点「同意」
    const hasDlg = await cdp.eval(targetId, '!!document.querySelector(".rc-kmui-com-dlg")');
    if (hasDlg) {
      await cdp.eval(targetId, `(function(){
        var btn = document.querySelector('input.rc-btn-ok');
        if (btn) btn.click();
      })()`);
    }

    await sleep(8000);
    const status = await checkLogin(targetId);
    if (!status.loggedIn) throw new Error('ERP登录失败，请手动登录后重试');
    if (process.env.VERBOSE) process.stderr.write('[navigate] 场景B 登录恢复成功\n');
    return;
  }

  // 场景 A：Session 超时弹窗，勾选协议 + 点登录
  await retry(async () => {
    const hasWrapper = await cdp.eval(targetId, '!!document.querySelector(".inner-login-wrapper")');
    if (!hasWrapper) throw new Error('登录弹窗未出现');
    await cdp.clickAt(targetId, '.iCheck-helper');
    await sleep(500);
  }, { maxRetries: 8, delayMs: 6000, label: 'recover-login: wait wrapper' });

  // 点登录按钮（精确匹配弹窗内的按钮）
  const clickBtn = `(function(){
    var wrapper = document.querySelector('.inner-login-wrapper');
    var btn = wrapper && Array.from(wrapper.querySelectorAll('button')).find(function(b){
      return b.textContent.replace(/\\s/g,'').includes('登录') || b.textContent.replace(/\\s/g,'').includes('登陆');
    });
    if (!btn) btn = Array.from(document.querySelectorAll('button')).find(function(b){
      return b.textContent.trim().includes('登');
    });
    if (btn) { btn.click(); return 'clicked'; }
    return 'not found';
  })()`;
  await cdp.eval(targetId, clickBtn);
  await sleep(8000);

  const status = await checkLogin(targetId);
  if (!status.loggedIn) throw new Error('登录恢复失败');
  if (process.env.VERBOSE) process.stderr.write('[navigate] 场景A 登录恢复成功\n');
}

// ── 页面内容轮询等待 ────────────────────────────────────────────────────────
// 检测：el-table 存在 且 loading 遮罩不可见（最多 15s）
async function waitForPageContent(targetId, pageName) {
  const CHECK_JS = `(function(){
    var table = document.querySelector('.el-table');
    if (!table) return JSON.stringify({ ready: false, reason: 'no-table' });
    var masks = Array.from(document.querySelectorAll('.el-loading-mask'));
    var isLoading = masks.some(function(m) {
      var s = window.getComputedStyle(m);
      return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
    });
    return JSON.stringify({ ready: !isLoading, isLoading: isLoading });
  })()`;

  for (let i = 0; i < 30; i++) { // 最多 15s（30 x 500ms）
    await sleep(500);
    const raw = await cdp.eval(targetId, CHECK_JS);
    const st = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (st.ready) {
      if (process.env.VERBOSE) process.stderr.write(`[waitForPageContent] ${pageName} 内容就绪（${(i + 1) * 500}ms）\n`);
      return;
    }
  }
  if (process.env.VERBOSE) process.stderr.write(`[waitForPageContent] ${pageName} 等待超时（15s），继续执行\n`);
}

// ── 导航到 ERP 指定页面 ────────────────────────────────────────────────────
// 优化：6 小时内 session 有效时跳过 location.reload()，只做轻量 DOM 检测
// 只在 session 过期 或 切换到不同页面 时才做完整刷新
async function navigateErp(targetId, pageName) {
  const targetHash = PAGE_MAP[pageName];
  if (!targetHash) throw new Error(`未知页面: ${pageName}，可用: ${Object.keys(PAGE_MAP).join(', ')}`);

  const cache = loadSessionCache();
  const entry = cache[targetId];
  const now = Date.now();
  const sessionFresh = entry && (now - entry.time < SESSION_TTL_MS);

  if (sessionFresh) {
    // Session 新鲜：只做轻量检测，不刷新页面
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) {
      // Session 已过期，清缓存走完整流程
      delete cache[targetId]; saveSessionCache(cache);
      if (process.env.VERBOSE) process.stderr.write('[navigateErp] Session 已过期，执行完整刷新\n');
      return navigateErp(targetId, pageName);
    }

    // 已在目标页且 session 有效，直接返回
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新（session 新鲜，已在目标页 ${pageName}）\n`);
      cache[targetId] = { time: now, page: pageName }; saveSessionCache(cache);
      return;
    }

    // 在不同页，切换标签（无需刷新）
    if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新，切换到 ${pageName}\n`);
  } else {
    // Session 过期或首次：完整刷新流程
    if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 执行完整刷新（${sessionFresh === false ? 'TTL过期' : '首次'}）\n`);
    await cdp.eval(targetId, 'location.reload(); "ok"');

    // 轮询等待页面加载：title 出现 或 登录弹窗出现（最多 20s）
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const st = await checkLogin(targetId);
      if (st.loggedIn || st.sessionExpired || (st.title && st.title.includes('快麦ERP--'))) break;
      if (st.url && st.url.includes('login')) break;
    }

    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) {
      if (process.env.VERBOSE) process.stderr.write('[navigateErp] ERP 已掉线，尝试恢复登录\n');
      await recoverLogin(targetId);
    }
  }

  await retry(async () => {
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      await waitForPageContent(targetId, pageName);
      return;
    }

    const clickTabJS = `(function(){
      var li = Array.from(document.querySelectorAll('li.fix-tab')).find(function(el){
        return el.textContent.trim() === '${pageName}';
      });
      if (!li) return 'not found';
      li.click();
      return 'clicked';
    })()`;
    const result = await cdp.eval(targetId, clickTabJS);
    if (result === 'not found') throw new Error(`顶部标签未找到: ${pageName}`);

    // 等待 hash 切换（最多 3s）
    for (let i = 0; i < 6; i++) {
      await sleep(500);
      const h = await cdp.eval(targetId, 'window.location.hash');
      if (h === targetHash) break;
    }

    const hash = await cdp.eval(targetId, 'window.location.hash');
    if (hash !== targetHash) throw new Error(`导航失败: 期望 ${targetHash}，实际 ${hash}`);

    await waitForPageContent(targetId, pageName);
  }, { maxRetries: 3, delayMs: 6000, label: `erp-nav ${pageName}` });

  // 更新 session 缓存
  cache[targetId] = { time: Date.now(), page: pageName };
  saveSessionCache(cache);
}

// 关闭所有可见的 Element UI 弹窗（档案V2子品弹窗等）
const CLOSE_ALL_DIALOGS_JS = `(function(){
  var closed = 0;
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(e){
    return window.getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  });
  wrappers.forEach(function(w) {
    var btn = w.querySelector('.el-dialog__closeBtn');
    if (btn) { btn.click(); closed++; }
  });
  return closed;
})()`;

module.exports = { navigateErp, checkLogin, recoverLogin, waitForPageContent, CLOSE_ALL_DIALOGS_JS };
