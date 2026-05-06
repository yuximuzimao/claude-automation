'use strict';
/**
 * WHAT: ERP 页面导航 + 登录状态检测与恢复
 * WHERE: 所有 ERP 操作的前置步骤，erpNav() / checkLogin() / recoverLogin()
 * WHY: 跳过 reload 直接导航会读到上次页面残留数据；密码框需 cdp.clickAt 触发 Chrome 自动填充
 * ENTRY: 所有 lib/erp/*.js 的第一步调用
 *
 * 登录保障层级（由外到内）:
 *   1. Session 缓存（6h TTL）—— 减少无谓 reload
 *   2. 保活心跳（server.js，1h fetch + checkLogin）—— 预防掉线
 *   3. 熔断器 —— 连续3次认证失败后快速失败，防止无效空转
 *   4. recoverLogin —— Chrome 自动填充 → 凭据注入 fallback
 *   5. erp-health.json —— 有状态可重复告警
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const cdp = require('../cdp');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

const PAGE_MAP = {
  '订单管理':   '#/tradeNew/manage/',
  '售后工单新版': '#/aftersale/sale_handle_next/',
  '商品档案V2': '#/prod/parallel/',
  '商品对应表': '#/prod/prod_correspondence_next/',
};

// ============================================================
// Session 缓存（跨进程复用，collect.js 每次是新进程）
// ============================================================
const SESSION_TTL_MS = 6 * 60 * 60 * 1000; // 6 小时
const SESSION_CACHE_FILE = path.join(__dirname, '../../data/erp-session-cache.json');

function loadSessionCache() {
  try { return JSON.parse(fs.readFileSync(SESSION_CACHE_FILE, 'utf8')); } catch { return {}; }
}

function saveSessionCache(cache) {
  try { fs.writeFileSync(SESSION_CACHE_FILE, JSON.stringify(cache)); } catch {}
}

// ============================================================
// ERP Health 文件（有状态告警）
// ============================================================
const HEALTH_FILE = path.join(__dirname, '../../data/erp-health.json');

function loadErpHealth() {
  try { return JSON.parse(fs.readFileSync(HEALTH_FILE, 'utf8')); } catch { return {}; }
}

// read-merge-write，防止多调用点覆盖丢数据
function updateErpHealth(updates) {
  try {
    const merged = Object.assign({}, loadErpHealth(), updates);
    fs.writeFileSync(HEALTH_FILE, JSON.stringify(merged, null, 2));
  } catch {}
}

function alertErpDown(reason) {
  try {
    const msg = `ERP 登录异常: ${String(reason).slice(0, 80)}`;
    spawnSync('osascript', ['-e',
      `display notification ${JSON.stringify(msg)} with title "ERP 告警" sound name "Basso"`
    ], { timeout: 5000 });
  } catch {}
}

// ============================================================
// 熔断器（仅统计认证失败，跨进程文件持久化）
// ============================================================
const CB_FILE = path.join(__dirname, '../../data/erp-circuit-breaker.json');
const CB_FAIL_THRESHOLD = 3;
const CB_COOLDOWN_MS = 15 * 60 * 1000; // 15 分钟

function loadCircuitBreaker() {
  try {
    const cb = JSON.parse(fs.readFileSync(CB_FILE, 'utf8'));
    // 启动时重置已过冷却期的 open 状态
    if (cb.state === 'open' && cb.lastFailAt && (Date.now() - cb.lastFailAt > CB_COOLDOWN_MS)) {
      cb.state = 'half_open';
    }
    return cb;
  } catch {
    return { state: 'closed', consecutiveFails: 0, lastFailAt: null, lastError: null };
  }
}

function saveCircuitBreaker(cb) {
  try { fs.writeFileSync(CB_FILE, JSON.stringify(cb)); } catch {}
}

function onErpSuccess() {
  const cb = loadCircuitBreaker();
  const wasDown = cb.consecutiveFails > 0 || cb.state !== 'closed';
  cb.state = 'closed';
  cb.consecutiveFails = 0;
  saveCircuitBreaker(cb);
  if (wasDown) {
    updateErpHealth({ status: 'up', lastOkTime: new Date().toISOString(), consecutiveAuthFail: 0 });
    try {
      spawnSync('osascript', ['-e',
        'display notification "ERP 已恢复登录" with title "ERP 恢复" sound name "Glass"'
      ], { timeout: 5000 });
    } catch {}
    console.log('[ERP 熔断] 已恢复，重置熔断器');
  }
}

function onAuthFail(reason) {
  const cb = loadCircuitBreaker();
  cb.consecutiveFails = (cb.consecutiveFails || 0) + 1;
  cb.lastFailAt = Date.now();
  cb.lastError = String(reason).slice(0, 200);
  if (cb.consecutiveFails >= CB_FAIL_THRESHOLD && cb.state !== 'open') {
    cb.state = 'open';
    updateErpHealth({
      status: 'down',
      lastFailTime: new Date().toISOString(),
      lastAlertTime: new Date().toISOString(),
      failReason: cb.lastError,
      consecutiveAuthFail: cb.consecutiveFails,
    });
    alertErpDown(`连续${cb.consecutiveFails}次认证失败，已熔断`);
    console.error(`[ERP 熔断] 连续${cb.consecutiveFails}次认证失败，熔断开启，${CB_COOLDOWN_MS / 60000}分钟后重试`);
  }
  saveCircuitBreaker(cb);
}

// 分类错误是否为认证失败（主用结构判定，辅以文案）
async function classifyErpError(targetId, e) {
  // 文案快速判定（兜底，防止结构判定失败）
  if (/退出登录|密码未|登录失败|登录恢复失败/.test(e.message || '')) return true;
  // 结构判定：确保页面已加载完成，避免假阳性
  try {
    const ready = await cdp.eval(targetId, 'document.readyState === "complete"');
    if (!ready) return false; // 页面未完成加载，不计入认证失败
    const loginStatus = await checkLogin(targetId);
    return !loginStatus.loggedIn;
  } catch { return false; } // checkLogin 本身失败，不计入
}

// ============================================================
// 凭据注入（三级降级，仅在 Chrome 自动填充失败时触发）
// ============================================================
async function injectCredentials(targetId) {
  const username = process.env.ERP_USERNAME;
  const password = process.env.ERP_PASSWORD;
  if (!username || !password) return false; // 未配置凭据，跳过

  // Level 1: nativeInputValueSetter + dispatchEvent（绕过 Vue/React 受控组件拦截）
  const r1 = await cdp.eval(targetId, `(function(){
    var userEl = document.querySelector('input[name="userName"]');
    var pwdEl = document.querySelector('input[type="password"]');
    if (!pwdEl) return JSON.stringify({ ok: false, reason: 'no-pwd-field' });
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    if (userEl) {
      nativeSetter.call(userEl, ${JSON.stringify(username)});
      userEl.dispatchEvent(new Event('input', { bubbles: true }));
      userEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
    nativeSetter.call(pwdEl, ${JSON.stringify(password)});
    pwdEl.dispatchEvent(new Event('input', { bubbles: true }));
    pwdEl.dispatchEvent(new Event('change', { bubbles: true }));
    return JSON.stringify({ ok: true, pwdMatch: pwdEl.value === ${JSON.stringify(password)} });
  })()`);
  if (r1 && r1.ok && r1.pwdMatch) {
    if (process.env.VERBOSE) process.stderr.write('[injectCredentials] Level 1 nativeSetter 成功\n');
    return true;
  }

  // Level 2: execCommand('insertText')（deprecated 但在 Chromium 中通常有效）
  if (process.env.VERBOSE) process.stderr.write('[injectCredentials] Level 1 失败，尝试 execCommand\n');
  await cdp.eval(targetId, `(function(){
    var pwdEl = document.querySelector('input[type="password"]');
    if (!pwdEl) return;
    pwdEl.focus();
    pwdEl.select();
    document.execCommand('selectAll');
    document.execCommand('insertText', false, ${JSON.stringify(password)});
  })()`);
  const check2 = await cdp.eval(targetId, `(function(){
    var el = document.querySelector('input[type="password"]');
    return el ? el.value : '';
  })()`);
  if (check2 === password) {
    if (process.env.VERBOSE) process.stderr.write('[injectCredentials] Level 2 execCommand 成功\n');
    return true;
  }

  // Level 3: CDP Input.insertText（聚焦后直接插入，最终兜底）
  if (process.env.VERBOSE) process.stderr.write('[injectCredentials] Level 2 失败，尝试 CDP typeText\n');
  await cdp.clickAt(targetId, 'input[type="password"]');
  await sleep(300);
  // 先清空现有内容
  await cdp.eval(targetId, `(function(){
    var pwdEl = document.querySelector('input[type="password"]');
    if (pwdEl) {
      var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeSetter.call(pwdEl, '');
      pwdEl.dispatchEvent(new Event('input', { bubbles: true }));
    }
  })()`);
  await cdp.typeText(targetId, password);
  await sleep(300);
  const check3 = await cdp.eval(targetId, `(function(){
    var el = document.querySelector('input[type="password"]');
    return el ? el.value : '';
  })()`);
  if (check3 === password) {
    if (process.env.VERBOSE) process.stderr.write('[injectCredentials] Level 3 CDP typeText 成功\n');
    return true;
  }

  process.stderr.write('[injectCredentials] 三级注入均失败\n');
  return false;
}

// ============================================================
// 关闭弹窗（供外部调用）
// ============================================================
const CLOSE_ALL_DIALOGS_JS = `(function(){
  // 关闭所有可见的 Element UI 弹窗（不限 trade-detail-dialog，档案V2子品弹窗等也覆盖）
  // ⚠️ 必须用 Vue 方式关闭，不能 DOM 移除：后者不更新 Vue 内部 dialogVisible 状态
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(e){
    return window.getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
  });
  wrappers.forEach(function(w) {
    var btn = w.querySelector('.el-dialog__closeBtn');
    if (btn) btn.click();
  });
  return JSON.stringify({closed: wrappers.length});
})()`;

// ============================================================
// 登录状态检测
// ============================================================
const CHECK_LOGIN_JS = `(function(){
  var isOut = window.location.href.includes('login') || !document.title.includes('快麦ERP--');
  var sessionExpired = !!document.querySelector('.inner-login-wrapper');
  return JSON.stringify({loggedIn: !isOut && !sessionExpired, title: document.title, url: window.location.href, sessionExpired: sessionExpired});
})()`;

async function checkLogin(targetId) {
  const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

// ============================================================
// 登录恢复
// 场景 A: Session 超时弹窗（.inner-login-wrapper）→ 勾协议 + 点登录
// 场景 B: 完全退出到登录页 → Chrome 自动填充（Phase 1）→ 凭据注入（Phase 2 fallback）
// ============================================================
async function recoverLogin(targetId) {
  const preCheck = await checkLogin(targetId);
  const alreadyOnLoginPage = !preCheck.loggedIn && !preCheck.sessionExpired &&
    (preCheck.url && preCheck.url.includes('login'));

  // 已经在登录页时不 reload（reload 会清掉 Chrome 密码管理器的自动填充）
  if (!alreadyOnLoginPage) {
    await cdp.eval(targetId, 'location.reload()');
  }

  // 轮询等待页面就绪（最多 20s）
  let hasModal = false;
  let isLoginPage = false;
  let pwdFieldReady = false;
  for (let i = 0; i < 20; i++) {
    await sleep(1000);
    const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
    const st = typeof raw === 'string' ? JSON.parse(raw) : raw;
    hasModal = st.sessionExpired;
    isLoginPage = !st.loggedIn && !st.sessionExpired;
    if (hasModal) break;
    if (isLoginPage) {
      const hasPwd = await cdp.eval(targetId, '!!document.querySelector("input[type=password]")');
      if (hasPwd) { pwdFieldReady = true; break; }
    }
  }

  if (isLoginPage && pwdFieldReady) {
    // ---- 场景 B: 完全退出到登录页 ----
    await sleep(2000);

    // Phase 1: Chrome 自动填充（单次尝试，确定性行为，重试无意义）
    const hasUserField = await cdp.eval(targetId, '!!document.querySelector("input[name=userName]")');
    if (hasUserField) {
      await cdp.clickAt(targetId, 'input[name="userName"]');
      await sleep(1500);
    }
    await cdp.clickAt(targetId, 'input[type="password"]');
    await sleep(2000);

    let passwordFilled = await cdp.eval(targetId, `(function(){
      var pwd = document.querySelector('input[type="password"]');
      return !!(pwd && pwd.value && pwd.value.length > 0);
    })()`);

    // Phase 2: 凭据注入 fallback（仅在自动填充失败且 env vars 已配置时触发）
    if (!passwordFilled) {
      if (process.env.VERBOSE) process.stderr.write('[recoverLogin] Chrome 自动填充未触发，尝试凭据注入 fallback\n');
      const injected = await injectCredentials(targetId);
      if (!injected) {
        throw new Error('ERP已完全退出登录：Chrome自动填充未触发，凭据注入失败（请配置 ERP_USERNAME/ERP_PASSWORD 或手动登录）');
      }
      passwordFilled = true;
    }

    // 点登录按钮
    await cdp.eval(targetId, `(function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){
        return b.textContent.indexOf('登') >= 0;
      });
      if (btn) btn.click();
    })()`);
    await sleep(2000);

    // 处理协议确认弹窗
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

  // ---- 场景 A: Session 超时弹窗 ----
  await retry(async () => {
    const hasWrapper = await cdp.eval(targetId, '!!document.querySelector(".inner-login-wrapper")');
    if (!hasWrapper) throw new Error('登录弹窗未出现');
    await cdp.clickAt(targetId, '.iCheck-helper');
    await sleep(500);
  }, { maxRetries: 8, delayMs: 6000, label: 'recover-login: wait wrapper' });

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

// ============================================================
// 等待页面内容加载（Vue mount + 数据渲染）
// ============================================================
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

  for (let i = 0; i < 30; i++) {
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

// ============================================================
// 导航到 ERP 指定页面
// ============================================================
async function navigateErp(targetId, pageName) {
  const targetHash = PAGE_MAP[pageName];
  if (!targetHash) throw new Error(`未知页面: ${pageName}，可用: ${Object.keys(PAGE_MAP).join(', ')}`);

  const cache = loadSessionCache();
  const entry = cache[targetId];
  const now = Date.now();
  const sessionFresh = entry && (now - entry.time < SESSION_TTL_MS);

  if (sessionFresh) {
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) {
      delete cache[targetId]; saveSessionCache(cache);
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] Session 已过期，执行完整刷新\n`);
      return navigateErp(targetId, pageName);
    }
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新（session 新鲜，已在目标页）\n`);
      cache[targetId] = { time: now, page: pageName }; saveSessionCache(cache);
      return;
    }
    if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 跳过刷新，切换到 ${pageName}\n`);
  } else {
    const preLoginCheck = await checkLogin(targetId);
    if (preLoginCheck.loggedIn) {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 缓存过期但 ERP 仍登录中，跳过 reload 直接切 tab\n`);
      cache[targetId] = { time: now, page: null }; saveSessionCache(cache);
    } else {
      if (process.env.VERBOSE) process.stderr.write(`[navigateErp] 执行完整刷新（${sessionFresh === false ? 'TTL过期' : '首次'}）\n`);
      await cdp.eval(targetId, 'location.reload(); "ok"');
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
          await sleep(3000);
          await recoverLogin(targetId);
        }
      }
    }
  }

  await retry(async () => {
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      await waitForPageContent(targetId, pageName);
      return;
    }
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
    for (let i = 0; i < 6; i++) {
      await sleep(500);
      const h = await cdp.eval(targetId, 'window.location.hash');
      if (h === targetHash) break;
    }
    const hash = await cdp.eval(targetId, 'window.location.hash');
    if (hash !== targetHash) throw new Error(`导航失败: 期望 ${targetHash}，实际 ${hash}`);
    await waitForPageContent(targetId, pageName);
  }, { maxRetries: 3, delayMs: 6000, label: `erp-nav ${pageName}` });

  cache[targetId] = { time: Date.now(), page: pageName };
  saveSessionCache(cache);
}

// ============================================================
// erpNav: 对外入口，含熔断器保护
// ============================================================
async function erpNav(targetId, pageName) {
  // 熔断检查
  const cb = loadCircuitBreaker();
  if (cb.state === 'open') {
    const elapsed = Date.now() - (cb.lastFailAt || 0);
    if (elapsed < CB_COOLDOWN_MS) {
      const waitMin = Math.ceil((CB_COOLDOWN_MS - elapsed) / 60000);
      return fail(new Error(`ERP 熔断中（连续${cb.consecutiveFails}次认证失败，约${waitMin}分钟后重试）：${cb.lastError || ''}`));
    }
    // 冷却期结束 → half_open，允许一次探测
    cb.state = 'half_open';
    saveCircuitBreaker(cb);
    if (process.env.VERBOSE) process.stderr.write('[ERP 熔断] 冷却期结束，进入 half_open 探测\n');
  }

  try {
    // 等待页面稳定（最多 10s）
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
    onErpSuccess();
    return ok({ page: pageName, hash: PAGE_MAP[pageName] });
  } catch (e) {
    // 分类错误：认证失败计入熔断，其他不进 breaker
    const isAuth = await classifyErpError(targetId, e);
    if (isAuth) onAuthFail(e.message);
    return fail(e);
  }
}

module.exports = {
  navigateErp, checkLogin, recoverLogin, erpNav, CLOSE_ALL_DIALOGS_JS,
  updateErpHealth, loadErpHealth, alertErpDown,
};
