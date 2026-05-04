'use strict';
/**
 * WHAT: ERP 页面导航 + 登录状态检测与恢复
 * WHERE: 所有 ERP 操作的前置步骤，erpNav() / checkLogin() / recoverLogin()
 * WHY: 跳过 reload 直接导航会读到上次页面残留数据；密码框需 cdp.clickAt 触发 Chrome 自动填充
 * ENTRY: 所有 lib/erp/*.js 的第一步调用
 */
const fs = require('fs');
const path = require('path');
const cdp = require('../cdp');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

const PAGE_MAP = {
  '订单管理':   '#/tradeNew/manage/',
  '售后工单新版': '#/aftersale/sale_handle_next/',
  '商品档案V2': '#/prod/parallel/',
  '商品对应表': '#/prod/prod_correspondence_next/',
};

// Session 缓存：持久化到文件，跨进程复用（collect.js 每次是新进程）
const SESSION_TTL_MS = 6 * 60 * 60 * 1000; // 6小时
const SESSION_CACHE_FILE = path.join(__dirname, '../../data/erp-session-cache.json');

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

// 关闭所有残留的 trade-detail-dialog（可能堆叠多层）
// 供 search.js / aftersale.js 在 navigateErp 前调用
const CLOSE_ALL_DIALOGS_JS = `(function(){
  var closed = 0;
  // 关闭所有可见的 Element UI 弹窗（不限 trade-detail-dialog，档案V2子品弹窗等也覆盖）
  // 使用 DOM 移除而非 btn.click()：Vue 的 fade 动画可能卡在中途不完成，导致弹窗残留
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(e){
    return window.getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  });
  wrappers.forEach(function(w) {
    // 优先 DOM 强制移除（绕过 Vue 动画），fallback 点关闭按钮
    if (w.parentNode) { w.parentNode.removeChild(w); closed++; }
    else {
      var btn = w.querySelector('.el-dialog__closeBtn');
      if (btn) { btn.click(); closed++; }
    }
  });
  return closed;
})()`;

// 检查登录状态
// 会话超时时 ERP 会弹出登录框但 title/URL 不变，需额外检测 .inner-login-wrapper
const CHECK_LOGIN_JS = `(function(){
  var isOut = window.location.href.includes('login') || !document.title.includes('快麦ERP--');
  var sessionExpired = !!document.querySelector('.inner-login-wrapper');
  return JSON.stringify({loggedIn: !isOut && !sessionExpired, title: document.title, url: window.location.href, sessionExpired: sessionExpired});
})()`;

async function checkLogin(targetId) {
  const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

// 自动恢复登录（浏览器已记住密码，禁止填密码框）
// 两种场景：
//   A. Session 超时弹窗（.inner-login-wrapper）：勾协议 → 点登录
//   B. 完全退出到登录页（URL 含 login / title 变化）：点密码框触发自动填充 → 点登录 → 点弹窗同意
async function recoverLogin(targetId) {
  // 先检测当前状态，决定是否需要 reload
  const preCheck = await checkLogin(targetId);
  const alreadyOnLoginPage = !preCheck.loggedIn && !preCheck.sessionExpired &&
    (preCheck.url && preCheck.url.includes('login'));

  // 已经在登录页时不 reload（reload 会清掉 Chrome 密码管理器的自动填充）
  if (!alreadyOnLoginPage) {
    await cdp.eval(targetId, 'location.reload()');
  }

  // 轮询等待页面就绪：登录页+密码框出现，或 session 弹窗出现（最多 20s）
  let hasModal = false;
  let isLoginPage = false;
  let pwdFieldReady = false;
  for (let i = 0; i < 20; i++) {
    await sleep(1000);
    const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
    const st = typeof raw === 'string' ? JSON.parse(raw) : raw;
    hasModal = st.sessionExpired;
    isLoginPage = !st.loggedIn && !st.sessionExpired;
    // 登录页需要密码框也出现才算就绪
    if (hasModal) break;
    if (isLoginPage) {
      const hasPwd = await cdp.eval(targetId, '!!document.querySelector("input[type=password]")');
      if (hasPwd) { pwdFieldReady = true; break; }
    }
  }

  if (isLoginPage && pwdFieldReady) {
    // 场景 B：完全退出到登录页
    // Chrome 自动填充需要先点用户名框再点密码框（两步触发关联填充）
    await sleep(2000);

    // Step 1: 点用户名框 → 等待 → 点密码框 → 触发 Chrome 密码管理器自动填充
    // 多次尝试：Chrome 自动填充时序不稳定，需重试
    let passwordFilled = false;
    for (let attempt = 0; attempt < 3 && !passwordFilled; attempt++) {
      // 先点用户名框触发 Chrome 关联记忆
      const hasUserField = await cdp.eval(targetId, '!!document.querySelector("input[name=userName]")');
      if (hasUserField) {
        await cdp.clickAt(targetId, 'input[name="userName"]');
        await sleep(1500);
      }
      // 再点密码框触发密码自动填充
      await cdp.clickAt(targetId, 'input[type="password"]');
      await sleep(2000);

      passwordFilled = await cdp.eval(targetId, `(function(){
        var pwd = document.querySelector('input[type="password"]');
        return !!(pwd && pwd.value && pwd.value.length > 0);
      })()`);
      if (!passwordFilled && attempt < 2) {
        if (process.env.VERBOSE) process.stderr.write(`[recoverLogin] 密码未填充，第${attempt + 1}次重试\n`);
        await sleep(1000);
      }
    }
    if (!passwordFilled) {
      throw new Error('ERP已完全退出登录且密码未自动填充（已重试3次），请手动重新登录ERP后重试');
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
}

// 等待 ERP 页面内容加载完毕（Vue mount + 数据渲染）
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

  for (let i = 0; i < 30; i++) { // 最多 15s（30 × 500ms）
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

// 导航到 ERP 指定页面
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
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] Session 已过期，执行完整刷新\n`);
      return navigateErp(targetId, pageName);
    }

    // 已在目标页且 session 有效，直接返回
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新（session 新鲜，已在目标页）\n`);
      cache[targetId] = { time: now, page: pageName }; saveSessionCache(cache);
      return;
    }

    // 在不同页，切换标签（无需刷新）
    if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新，切换到 ${pageName}\n`);
  } else {
    // Session 缓存过期或首次：先轻量检测是否真的需要 reload
    // 如果 ERP 已登录（checkLogin 通过），跳过 reload 直接切 tab（减少不必要的 reload 导致登录丢失）
    const preLoginCheck = await checkLogin(targetId);
    if (preLoginCheck.loggedIn) {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 缓存过期但 ERP 仍登录中，跳过 reload 直接切 tab\n`);
      // 更新缓存（重建 session 信任）
      cache[targetId] = { time: now, page: null }; saveSessionCache(cache);
    } else {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 执行完整刷新（${sessionFresh === false ? 'TTL过期' : '首次'}）\n`);
      // ⚠️ 刷新让掉线弹窗出现（不刷新时 title/hash 维持旧值，无法检测掉线）
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
        if (process.env.VERBOSE) process.stderr.write(`[navigateErp] ERP 已掉线，尝试恢复登录\n`);
        try {
          await recoverLogin(targetId);
        } catch {
          // 恢复失败，再试一次（不再 reload，recoverLogin 内部已处理重试）
          await sleep(3000);
          await recoverLogin(targetId);
        }
      }
    }
  }

  await retry(async () => {
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      // DOM 轮询等待 Vue 内容加载（替换固定 sleep）
      await waitForPageContent(targetId, pageName);
      return;
    }

    // 切页面前清理所有弹窗（档案V2子品弹窗等可能残留）
    await cdp.eval(targetId, CLOSE_ALL_DIALOGS_JS);

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

    // DOM 轮询等待 Vue 内容加载
    await waitForPageContent(targetId, pageName);
  }, { maxRetries: 3, delayMs: 6000, label: `erp-nav ${pageName}` });

  // 更新 session 缓存（持久化到文件，跨进程复用）
  cache[targetId] = { time: Date.now(), page: pageName };
  saveSessionCache(cache);
}

async function erpNav(targetId, pageName) {
  try {
    // 等待 ERP 页面稳定（title 出现或 URL 跳到登录页），最多 10s
    for (let i = 0; i < 10; i++) {
      const st = await checkLogin(targetId);
      if (st.loggedIn || st.sessionExpired || (st.url && st.url.includes('login'))) break;
      await sleep(1000);
    }
    const status = await checkLogin(targetId);
    if (!status.loggedIn) {
      if (process.env.VERBOSE) process.stderr.write('[erp-nav] ERP 已掉线，尝试恢复登录\n');
      await recoverLogin(targetId);
    }
    await navigateErp(targetId, pageName);
    return ok({ page: pageName, hash: PAGE_MAP[pageName] });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { navigateErp, checkLogin, recoverLogin, erpNav, CLOSE_ALL_DIALOGS_JS };
