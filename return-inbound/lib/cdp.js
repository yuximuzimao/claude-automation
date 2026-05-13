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
      reject(new Error(`CDP timeout: ${method}`));
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

const cdp = {
  eval: evalJs,
  clickAt,
  screenshot,
  navigate,
  scroll,
  key,
  typeText,
  getTargets,
  createTarget,
  activateTarget,
};

module.exports = cdp;
