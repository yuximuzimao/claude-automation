'use strict';
/**
 * cdp.js - Chrome DevTools Protocol 直连封装
 * 直接通过 WebSocket 连接 Chrome（port 9222），不依赖任何 proxy
 * （port 3456 被 web-access skill 占用，无法使用）
 */
const http = require('http');
const { randomUUID } = require('node:crypto');

const CHROME_PORT = 9222;
const EVAL_TIMEOUT = 125000;

function logBrowserDiagnostic(event, details) {
  console.error('[browser-diagnostic] ' + JSON.stringify({
    at: new Date().toISOString(), event, ...details,
  }));
}

// 用固定标签描述路由，避免诊断记录带出查询参数、详情页标题或页面内容。
function pageKind(url) {
  try {
    const { hostname, pathname, protocol } = new URL(url);
    if (hostname === 'scrm.jlsupp.com') {
      if (pathname.endsWith('/after-sale-list')) return 'jl_list';
      if (pathname.endsWith('/after-sale-detail')) return 'jl_detail';
      if (pathname.includes('/login')) return 'jl_login';
      return 'jl_other';
    }
    if (hostname.endsWith('.superboss.cc')) return 'erp';
    if (url === 'about:blank') return 'blank';
    if (protocol === 'chrome-error:') return 'chrome_error';
  } catch {}
  return 'other';
}

function captureFailedTarget(error, abortSignal) {
  const { cdpDiagnosticId: diagnosticId, cdpTargetId: targetId } = error;
  if (!diagnosticId || abortSignal?.aborted) return;
  // 独立取证，只读本机 DevTools HTTP 接口，不等待、不重发指令。
  const timeout = AbortSignal.timeout(1000);
  const signal = abortSignal ? AbortSignal.any([abortSignal, timeout]) : timeout;
  void cdp.getTargets({ signal }).then(targets => {
    if (!Array.isArray(targets)) {
      logBrowserDiagnostic('cdp_target_snapshot', { diagnosticId, result: 'invalid_target_list' });
      return;
    }
    const target = targets.find(item => item?.id === targetId);
    logBrowserDiagnostic('cdp_target_snapshot', {
      diagnosticId,
      result: target ? 'target_present' : 'target_absent',
      targetType: target?.type,
      pageKind: target ? pageKind(target.url) : undefined,
      pageCount: targets.filter(item => item?.type === 'page').length,
    });
  }).catch(probeError => {
    logBrowserDiagnostic('cdp_target_snapshot', {
      diagnosticId,
      result: 'target_list_unavailable',
      errorCode: probeError.code || probeError.name,
      httpStatus: probeError.httpStatus,
    });
  });
}

// 一次性 CDP WebSocket 调用（用完即关）
function cdpCall(targetId, method, params, timeout) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();
    const origin = {};
    Error.captureStackTrace(origin, cdpCall);
    const ws = new WebSocket(`ws://localhost:${CHROME_PORT}/devtools/page/${targetId}`);
    const id = Math.floor(Math.random() * 100000);
    let opened = false;
    let commandSent = false;
    let settled = false;
    let socketClose;
    const reportFailure = (error, kind, cause) => {
      const diagnosticId = randomUUID();
      error.cdpDiagnosticId = diagnosticId;
      error.cdpTargetId = targetId;
      error.cdpFailureKind = kind;
      error.cdpMethod = method;
      error.cdpMouseEvent = method === 'Input.dispatchMouseEvent' ? params?.type : undefined;
      const status = cause?.statusCode ?? cause?.cause?.statusCode;
      logBrowserDiagnostic('cdp_transport', {
        diagnosticId, targetId, method, kind, opened, commandSent, elapsedMs: Date.now() - startedAt,
        mouseEvent: error.cdpMouseEvent,
        errorCode: cause?.code ?? cause?.cause?.code,
        protocolErrorCode: kind === 'protocol_error' ? cause?.code : undefined,
        handshakeHttpStatus: Number.isInteger(status) ? status : undefined,
        socketClose,
        callSite: origin.stack.split('\n').slice(1, 6).map(line => line.trim()),
      });
    };
    const timer = setTimeout(() => {
      settled = true;
      ws.close();
      const error = new Error(`CDP timeout: ${method} (target: ${targetId})`);
      reject(error);
      reportFailure(error, 'timeout');
    }, timeout || 30000);

    ws.addEventListener('open', () => {
      opened = true;
      ws.send(JSON.stringify({ id, method, params: params || {} }));
      commandSent = true;
    });
    ws.addEventListener('close', event => {
      if (!settled) socketClose = { code: event.code, wasClean: event.wasClean };
    });
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id === id) {
        settled = true;
        clearTimeout(timer);
        ws.close();
        if (msg.error) {
          const error = new Error(msg.error.message || JSON.stringify(msg.error));
          reject(error);
          reportFailure(error, 'protocol_error', msg.error);
        } else {
          resolve(msg.result);
        }
      }
    });
    ws.addEventListener('error', (e) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const error = new Error('WebSocket error: ' + (e.message || 'connection failed'));
      reject(error);
      reportFailure(error, opened ? 'socket_error' : 'handshake_error', e.error);
    });
  });
}

// 执行 JS 表达式，返回解析后的值
async function evalJs(targetId, jsCode, timeout) {
  const result = await cdpCall(targetId, 'Runtime.evaluate', {
    expression: jsCode,
    awaitPromise: true,
    returnByValue: true,
  }, timeout || EVAL_TIMEOUT);
  const raw = result && result.result && result.result.value;
  if (typeof raw !== 'string') return raw;
  try { return JSON.parse(raw); } catch { return raw; }
}

// 通过 DOM getBoundingClientRect 计算真实坐标并点击
async function clickAt(targetId, selector) {
  const rect = await evalJs(targetId, `(function(){
    var el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return { x: r.left + r.width/2, y: r.top + r.height/2, found: true };
  })()`);
  if (!rect || !rect.found) throw new Error(`Element not found: ${selector}`);
  await dispatchMouseEvent(targetId, {
    type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1,
  });
  await dispatchMouseEvent(targetId, {
    type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1,
  });
  return { clicked: true, x: rect.x, y: rect.y };
}

// 按屏幕坐标发送真实鼠标点击。用于固定位置控件的后备点击。
async function clickPoint(targetId, x, y) {
  await dispatchMouseEvent(targetId, {
    type: 'mousePressed', x, y, button: 'left', clickCount: 1,
  });
  await dispatchMouseEvent(targetId, {
    type: 'mouseReleased', x, y, button: 'left', clickCount: 1,
  });
  return { clicked: true, x, y };
}

// CDP Input.dispatchMouseEvent 在后台标签页会卡死（Chrome 不处理非激活 tab 的 input）。
// 此包装函在发送任意 mouse 事件前先 HTTP 激活目标标签页，统一解决所有调用方的失焦超时。
async function dispatchMouseEvent(targetId, event, timeout) {
  await activateTarget(targetId);
  return cdpCall(targetId, 'Input.dispatchMouseEvent', event, timeout || 10000);
}

// 列出所有标签页（Chrome HTTP API）
function getTargets({ signal } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: CHROME_PORT, path: '/json',
      method: 'GET', timeout: 10000, signal,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
        catch (error) {
          error.httpStatus = res.statusCode;
          reject(error);
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('getTargets timeout')); });
    req.end();
  });
}

// 导航到 URL，等待 Page.loadEventFired
async function navigate(targetId, url) {
  // 先 enable Page domain，再 navigate，再等 load
  const ws = new WebSocket(`ws://localhost:${CHROME_PORT}/devtools/page/${targetId}`);
  await new Promise((res, rej) => {
    ws.addEventListener('open', res);
    ws.addEventListener('error', rej);
  });
  let cmdId = 1;
  function send(method, params) {
    return new Promise((resolve, reject) => {
      const id = cmdId++;
      const h = (e) => {
        const m = JSON.parse(e.data);
        if (m.id === id) { ws.removeEventListener('message', h); resolve(m.result); }
      };
      ws.addEventListener('message', h);
      ws.send(JSON.stringify({ id, method, params: params || {} }));
      setTimeout(() => { ws.removeEventListener('message', h); reject(new Error('nav timeout')); }, 30000);
    });
  }
  await send('Page.enable');
  const loadPromise = new Promise(resolve => {
    const h = (e) => {
      const m = JSON.parse(e.data);
      if (m.method === 'Page.loadEventFired') { ws.removeEventListener('message', h); resolve(); }
    };
    ws.addEventListener('message', h);
    setTimeout(resolve, 15000); // 最长等 15s
  });
  await send('Page.navigate', { url });
  await loadPromise;
  ws.close();
  return { navigated: true };
}

// 刷新当前页（等价 F5/Ctrl+R，不指定 URL），等待 Page.loadEventFired。
// 用于注入 cookie 后让平台用新 session 自行跳转，而不是导航到新地址。
async function reload(targetId) {
  const ws = new WebSocket(`ws://localhost:${CHROME_PORT}/devtools/page/${targetId}`);
  await new Promise((res, rej) => {
    ws.addEventListener('open', res);
    ws.addEventListener('error', rej);
  });
  let cmdId = 1;
  function send(method, params) {
    return new Promise((resolve, reject) => {
      const id = cmdId++;
      const h = (e) => {
        const m = JSON.parse(e.data);
        if (m.id === id) { ws.removeEventListener('message', h); resolve(m.result); }
      };
      ws.addEventListener('message', h);
      ws.send(JSON.stringify({ id, method, params: params || {} }));
      setTimeout(() => { ws.removeEventListener('message', h); reject(new Error('reload timeout')); }, 30000);
    });
  }
  await send('Page.enable');
  const loadPromise = new Promise(resolve => {
    const h = (e) => {
      const m = JSON.parse(e.data);
      if (m.method === 'Page.loadEventFired') { ws.removeEventListener('message', h); resolve(); }
    };
    ws.addEventListener('message', h);
    setTimeout(resolve, 15000); // 最长等 15s
  });
  await send('Page.reload', {});
  await loadPromise;
  ws.close();
  return { reloaded: true };
}

// 截图
async function screenshot(targetId, filePath) {
  const result = await cdpCall(targetId, 'Page.captureScreenshot', { format: 'png' });
  const fs = require('fs');
  fs.writeFileSync(filePath, Buffer.from(result.data, 'base64'));
  return { saved: filePath };
}

// 滚动
async function scroll(targetId, direction) {
  const delta = direction === 'up' ? -500 : 500;
  return evalJs(targetId, `window.scrollBy(0, ${delta}); 'ok'`);
}

// 发送按键
async function key(targetId, keyName) {
  await cdpCall(targetId, 'Input.dispatchKeyEvent', { type: 'keyDown', key: keyName });
  await cdpCall(targetId, 'Input.dispatchKeyEvent', { type: 'keyUp', key: keyName });
  return { key: keyName };
}

// 向当前焦点元素插入文本（需先 clickAt 聚焦目标元素）
// 使用 Input.insertText，可穿透前端框架的 value setter 拦截
async function typeText(targetId, text) {
  await cdpCall(targetId, 'Input.insertText', { text });
}

// Chrome HTTP API: PUT /json/new?{url} 创建新标签页，返回 target 信息（含 id）
function createTarget(url) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: CHROME_PORT,
      path: '/json/new?' + encodeURIComponent(url),
      method: 'PUT', timeout: 15000,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
        catch(e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('createTarget timeout')); });
    req.end();
  });
}

// Chrome HTTP API: POST /json/activate/{targetId} 将标签页切换到前台
// 必须前台才能触发 Chrome 密码管理器自动填充
function activateTarget(targetId) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: CHROME_PORT,
      path: '/json/activate/' + targetId,
      method: 'POST', timeout: 5000,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        if (res.statusCode >= 400) {
          logBrowserDiagnostic('cdp_activate_http_error', { targetId, status: res.statusCode });
        }
        resolve();
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('activateTarget timeout')); });
    req.end();
  });
}

// Chrome HTTP API: GET /json/close/{targetId} 关闭指定标签页
function closeTarget(targetId) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: CHROME_PORT,
      path: '/json/close/' + encodeURIComponent(targetId),
      method: 'GET', timeout: 5000,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 400) {
          const body = Buffer.concat(chunks).toString().trim();
          reject(new Error(`closeTarget failed: HTTP ${res.statusCode}${body ? ` ${body}` : ''}`));
          return;
        }
        resolve({ closed: true, targetId });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('closeTarget timeout')); });
    req.end();
  });
}

// 清掉指定 tab 上所有鲸灵(*.jlsupp.com)相关的 cookie + localStorage/sessionStorage。
// 用于切换账号时先清空旧账号残留再注入新账号——保证传给平台的只有注入的认证信息。
// 关键约束：
//   - 只删 jlsupp 域，ERP(superboss.cc) 等其他域天然不在名单，零误伤
//   - getCookies 必须显式传 urls 覆盖全部 jlsupp 子域！默认 getCookies({}) 只返回
//     "当前 tab URL 适用"的 cookie，看不到 seller-portal.jlsupp.com/merchant 的
//     JSESSIONID（真正的登录凭证）——漏清它会导致新账号注入后混入旧账号登录态。
//     (2026-06-17 真机+Codex 审查证实此盲区)
//   - 取到全集后逐条 deleteCookies(name+domain+path)，domain 原样回传(含前导点)
//   - 删除后用相同 urls 复查；仅 JSESSIONID/_us 残留会阻止后续注入
//   - 绝不用 Network.clearBrowserCookies(会清掉整个浏览器含 ERP 登录)
//   - 报错即停，任一调用失败直接抛
const JL_COOKIE_URLS = [
  'https://scrm.jlsupp.com/',
  'https://seller-portal.jlsupp.com/',
  'https://seller-portal.jlsupp.com/merchant',
];
const JL_AUTH_COOKIE_NAMES = new Set(['JSESSIONID', '_us']);

function isJlCookie(cookie) {
  return typeof cookie.domain === 'string' &&
    cookie.domain.replace(/^\./, '').endsWith('jlsupp.com');
}

async function clearJlCookiesAndStorage(targetId) {
  if (!targetId) throw new Error('clearJlCookiesAndStorage 缺少 targetId');
  const res = await cdp.cdpCall(targetId, 'Network.getCookies', { urls: JL_COOKIE_URLS });
  const all = (res && res.cookies) || [];
  const jlCookies = all.filter(isJlCookie);
  // 去重（不同 urls 可能返回同一 cookie），按 name+domain+path 唯一
  const seen = new Set();
  const deleted = [];
  for (const c of jlCookies) {
    const key = `${c.name}@${c.domain}${c.path || '/'}`;
    if (seen.has(key)) continue;
    seen.add(key);
    // domain 原样回传(含前导点)，否则可能删不掉；用 name+domain+path 三元组精确删
    await cdp.cdpCall(targetId, 'Network.deleteCookies', {
      name: c.name,
      domain: c.domain,
      path: c.path || '/',
    });
    deleted.push({ name: c.name, domain: c.domain, path: c.path || '/' });
  }
  await cdp.eval(targetId, 'localStorage.clear(); sessionStorage.clear(); "ok"');
  const verification = await cdp.cdpCall(targetId, 'Network.getCookies', { urls: JL_COOKIE_URLS });
  const remainingAuthCookies = Array.from(new Map(
    ((verification && verification.cookies) || [])
      .filter(c => isJlCookie(c) && JL_AUTH_COOKIE_NAMES.has(c.name))
      .map(c => {
        const item = { name: c.name, domain: c.domain, path: c.path || '/' };
        return [`${item.name}@${item.domain}${item.path}`, item];
      })
  ).values());
  if (remainingAuthCookies.length > 0) {
    const locations = remainingAuthCookies
      .map(c => `${c.name}@${c.domain}${c.path}`)
      .join(', ');
    throw new Error(`清理后认证 Cookie 验证失败，仍存在: ${locations}`);
  }
  return {
    deletedCount: deleted.length,
    deletedCookies: deleted,
    verified: true,
    remainingAuthCookies: [],
  };
}

const cdp = {
  eval: evalJs,
  cdpCall,
  logBrowserDiagnostic,
  pageKind,
  captureFailedTarget,
  clearJlCookiesAndStorage,
  clickAt,
  clickPoint,
  screenshot,
  navigate,
  reload,
  scroll,
  key,
  typeText,
  getTargets,
  createTarget,
  activateTarget,
  closeTarget,
  dispatchMouseEvent,
};

module.exports = cdp;
