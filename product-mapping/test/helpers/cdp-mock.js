'use strict';
// L1 层 mock：模拟 cdp 模块，不需要真实浏览器

/**
 * 创建 mock cdp 对象
 * @param {object} evalResponses - 预设的 eval 返回值 { jsCode: response }
 */
function createMockCdp(evalResponses = {}) {
  const calls = {
    eval: [],
    clickAt: [],
    getTargets: 0,
  };

  const mock = {
    async eval(targetId, jsCode) {
      calls.eval.push({ targetId, jsCode });
      if (evalResponses[jsCode] !== undefined) return evalResponses[jsCode];
      // 默认返回
      return null;
    },
    async clickAt(targetId, selector) {
      calls.clickAt.push({ targetId, selector });
      return 'clicked';
    },
    async getTargets() {
      calls.getTargets++;
      return evalResponses._targets || [];
    },
    async reload(targetId) {
      calls.eval.push({ targetId, jsCode: 'location.reload()' });
    },
    async navigate(targetId, url) {
      return 'navigated';
    },
    _calls: calls,
    _setResponse(jsCode, value) {
      evalResponses[jsCode] = value;
    },
  };

  return mock;
}

/**
 * 拦截 require 调用，注入 mock cdp
 * 用法：const restore = injectMockCdp(mockCdp); ... restore();
 */
function injectMockCdp(mockCdp) {
  const Module = require('module');
  const originalResolveFilename = Module._resolveFilename;
  const mockPaths = new Set();

  // 拦截 cdp 模块的 require
  const originalRequire = Module.prototype.require;
  Module.prototype.require = function(id) {
    if (id.endsWith('/cdp') || id.endsWith('\\cdp') || id === './cdp' || id === '../cdp') {
      return mockCdp;
    }
    return originalRequire.apply(this, arguments);
  };

  return function restore() {
    Module.prototype.require = originalRequire;
  };
}

module.exports = { createMockCdp, injectMockCdp };
