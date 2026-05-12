'use strict';
const cdp = require('./cdp');

const ERP_URL = 'https://viperp.superboss.cc';
const CACHE_TTL = 5 * 60 * 1000; // 5min TTL，避免 server 长进程用到已关闭 tab 的脏缓存

let cached = null;
let cachedAt = 0;

// 轮询 document.readyState，直到 complete/interactive 或超时
async function waitForDomReady(targetId, timeout) {
  const end = Date.now() + (timeout || 15000);
  while (Date.now() < end) {
    try {
      const state = await cdp.eval(targetId, 'document.readyState');
      if (state === 'complete' || state === 'interactive') return;
    } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
}

async function getTargetIds(force) {
  if (cached && !force && (Date.now() - cachedAt < CACHE_TTL)) return cached;

  const targets = await cdp.getTargets();
  const pages = targets.filter(t => t.type === 'page');

  const jl = pages.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  if (!jl) throw new Error('鲸灵标签页未找到，请确认浏览器已打开对应页面');

  // ERP 查找：环境变量优先，缺失时 warn + fallback，不 hard fail
  let erp;
  if (process.env.ERP_TAB_ID) {
    erp = pages.find(t => t.id === process.env.ERP_TAB_ID);
    if (!erp) console.warn(`[targets] 指定的ERP标签页 ${process.env.ERP_TAB_ID} 未找到，尝试自动查找`);
  }
  if (!erp) {
    erp = pages.find(t => t.url && t.url.includes('superboss.cc'));
  }

  // ERP tab 不存在 → 自动创建（仅负责 tab 生命周期，登录恢复由 erpNav 负责）
  if (!erp) {
    console.log('[targets] ERP标签页不存在，自动创建...');
    erp = await cdp.createTarget(ERP_URL);
    await cdp.activateTarget(erp.id);
    await waitForDomReady(erp.id, 15000);
    console.log('[targets] ERP标签页已创建:', erp.id.slice(0, 8));
  }

  cached = { jlId: jl.id, erpId: erp.id };
  cachedAt = Date.now();
  return cached;
}

module.exports = { getTargetIds };
