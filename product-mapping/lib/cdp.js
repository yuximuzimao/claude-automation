'use strict';
const http = require('http');

const PROXY = 'http://localhost:3456';
const EVAL_TIMEOUT = 125000; // 125s，略高于 CDP 内部 120s

function request(method, path, body, timeout) {
  return new Promise((resolve, reject) => {
    const url = new URL(PROXY + path);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method,
      headers: body !== undefined ? {
        'Content-Type': 'text/plain',
        'Content-Length': Buffer.byteLength(body),
      } : {},
      timeout: timeout || 30000,
    };
    const req = http.request(options, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString();
        try {
          const json = JSON.parse(text);
          if (json.error) reject(new Error(json.error));
          else resolve(json);
        } catch {
          resolve(text);
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timeout')); });
    if (body !== undefined) req.write(body);
    req.end();
  });
}

const cdp = {
  // 执行 JS，自动尝试 JSON.parse 返回值（消除调用方的 typeof 判断）
  async eval(targetId, jsCode) {
    const res = await request('POST', `/eval?target=${targetId}`, jsCode, EVAL_TIMEOUT);
    const raw = res.value !== undefined ? res.value : res;
    if (typeof raw !== 'string') return raw;
    try { return JSON.parse(raw); } catch { return raw; }
  },

  // CSS 选择器真实点击
  async clickAt(targetId, selector) {
    return request('POST', `/clickAt?target=${targetId}`, selector);
  },

  // 截图保存到本地文件
  async screenshot(targetId, filePath) {
    return request('GET', `/screenshot?target=${targetId}&file=${encodeURIComponent(filePath)}`);
  },

  // 刷新当前页面（等同于 F5，保留会话状态）
  async reload(targetId) {
    try {
      await request('POST', `/eval?target=${targetId}`, 'location.reload()', EVAL_TIMEOUT);
    } catch (_) {
      // 页面刷新会中断当前连接，忽略该错误
    }
  },

  // 导航到 URL
  async navigate(targetId, url) {
    return request('GET', `/navigate?target=${targetId}&url=${encodeURIComponent(url)}`);
  },

  // 滚动页面
  async scroll(targetId, direction) {
    return request('GET', `/scroll?target=${targetId}&direction=${direction}`);
  },

  // 发送按键（如 Enter）
  async key(targetId, key) {
    return request('POST', `/key?target=${targetId}`, key);
  },

  // 列出所有标签页
  async getTargets() {
    return request('GET', '/targets');
  },
};

module.exports = cdp;
