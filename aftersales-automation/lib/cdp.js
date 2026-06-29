'use strict';
/**
 * cdp.js - Chrome DevTools Protocol 直连封装
 * 直接通过 WebSocket 连接 Chrome（port 9222），不依赖任何 proxy
 * （port 3456 被 web-access skill 占用，无法使用）
 */
const http = require('http');

const CHROME_PORT = 9222;
const EVAL_TIMEOUT = 125000;

// 一次性 CDP WebSocket 调用（用完即关）
function cdpCall(targetId, method, params, timeout) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://localhost:${CHROME_PORT}/devtools/page/${targetId}`);
    const id = Math.floor(Math.random() * 100000);
    const timer = setTimeout(() => {
      ws.close();
      reject(new Error(`CDP timeout: ${method} (target: ${targetId})`));
    }, timeout || 30000);

    ws.addEventListener('open', () => {
      ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id === id) {
        clearTimeout(timer);
        ws.close();
        if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
    ws.addEventListener('error', (e) => {
      clearTimeout(timer);
      reject(new Error('WebSocket error: ' + (e.message || 'connection failed')));
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
  await cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1,
  });
  await cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1,
  });
  return { clicked: true, x: rect.x, y: rect.y };
}

// 按屏幕坐标发送真实鼠标点击。用于固定位置控件的后备点击。
async function clickPoint(targetId, x, y) {
  await cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mousePressed', x, y, button: 'left', clickCount: 1,
  });
  await cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mouseReleased', x, y, button: 'left', clickCount: 1,
  });
  return { clicked: true, x, y };
}

// 列出所有标签页（Chrome HTTP API）
function getTargets() {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost', port: CHROME_PORT, path: '/json',
      method: 'GET', timeout: 10000,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
        catch(e) { reject(e); }
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
      res.on('end', () => resolve());
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
};

module.exports = cdp;
