'use strict';
const http = require('http');

const PROXY = 'http://localhost:3456';
const DIRECT_PORT = 9222;
const EVAL_TIMEOUT = 125000; // 125s，略高于 CDP 内部 120s
const HEALTH_TIMEOUT = 3000; // 健康检查超时 3s

// 连接模式：'proxy' | 'direct'，启动时锁定
let connectionMode = 'proxy';

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

// 直连模式：通过 Chrome HTTP API 获取 targets
function directGetTargets() {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://localhost:${DIRECT_PORT}/json`, { timeout: HEALTH_TIMEOUT }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try {
          const targets = JSON.parse(Buffer.concat(chunks).toString());
          // 统一字段名：直连返回 id，proxy 返回 targetId
          resolve(targets.map(t => ({
            targetId: t.id,
            url: t.url,
            title: t.title,
          })));
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Direct connection timeout')); });
  });
}

// 直连模式下 eval 不支持（需要 WebSocket，项目无 ws 依赖）
function directEval() {
  throw new Error('CDP proxy 不可用且直连模式不支持 eval，请确保 web-access skill 的 proxy (port 3456) 正在运行');
}

const cdp = {
  // 健康检查：检测 proxy 是否可用，不可用则 fallback 到直连
  async healthCheck() {
    try {
      await request('GET', '/targets', undefined, HEALTH_TIMEOUT);
      connectionMode = 'proxy';
      return { ok: true, mode: 'proxy' };
    } catch (e) {
      // proxy 不可用，尝试直连
      try {
        await directGetTargets();
        connectionMode = 'direct';
        if (process.env.VERBOSE) process.stderr.write('[cdp] proxy 不可用，fallback 到直连 9222\n');
        return { ok: true, mode: 'direct' };
      } catch (e2) {
        return { ok: false, error: `proxy: ${e.message}, direct: ${e2.message}` };
      }
    }
  },

  // 获取当前连接模式
  getConnectionMode() {
    return connectionMode;
  },

  // 执行 JS，自动尝试 JSON.parse 返回值
  async eval(targetId, jsCode) {
    if (connectionMode === 'direct') {
      const raw = await directEval(targetId, jsCode);
      if (typeof raw !== 'string') return raw;
      try { return JSON.parse(raw); } catch { return raw; }
    }
    const res = await request('POST', `/eval?target=${targetId}`, jsCode, EVAL_TIMEOUT);
    const raw = res.value !== undefined ? res.value : res;
    if (typeof raw !== 'string') return raw;
    try { return JSON.parse(raw); } catch { return raw; }
  },

  // CSS 选择器真实点击
  async clickAt(targetId, selector) {
    if (connectionMode === 'direct') {
      directEval(); // 直连不支持，抛错
    }
    return request('POST', `/clickAt?target=${targetId}`, selector);
  },

  // 截图保存到本地文件
  async screenshot(targetId, filePath) {
    return request('GET', `/screenshot?target=${targetId}&file=${encodeURIComponent(filePath)}`);
  },

  // 刷新当前页面
  async reload(targetId) {
    try {
      await cdp.eval(targetId, 'location.reload()');
    } catch (_) {
      // 页面刷新会中断当前连接，忽略该错误
    }
  },

  // 导航到 URL
  async navigate(targetId, url) {
    if (connectionMode === 'direct') {
      directEval(); // 直连不支持
    }
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
    if (connectionMode === 'direct') {
      return directGetTargets();
    }
    return request('GET', '/targets');
  },
};

module.exports = cdp;
