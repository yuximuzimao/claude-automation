'use strict';
/**
 * WHAT: 鲸灵首页提醒信息抓取 + 持久化缓存（文件）
 * WHERE: routes.js（GET /api/jl-alerts） + scan-all.js（每账号扫完后读取）
 * WHY: scan-all.js 是子进程，内存缓存无法共享主进程，必须用文件作为缓存媒介
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');

const CACHE_FILE = path.join(__dirname, '../../data/jl-alerts-cache.json');
const HOME_URL = 'https://scrm.jlsupp.com/micro-supplier/business/home';

async function fetchAndCacheAlerts() {
  const targets = await cdp.getTargets();
  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  if (!jl) return readCache();

  // 若当前不在首页，先导航过去
  const curUrl = await cdp.eval(jl.id, 'window.location.href').catch(() => '');
  if (!curUrl.includes('/home')) {
    await cdp.navigate(jl.id, HOME_URL);
    // 等首页滚动公告渲染（4s 确保完整加载）
    await new Promise(r => setTimeout(r, 4000));
  }

  const items = await cdp.eval(jl.id, `
    Array.from(document.querySelectorAll('.scroll-item')).map(el => ({
      title: (el.querySelector('.title')?.innerText || '').trim(),
      content: (el.querySelector('.content')?.innerText || '').trim(),
    })).filter(i => i.title || i.content)
  `).catch(() => []);

  if (Array.isArray(items) && items.length > 0) {
    const cache = { items, fetchedAt: new Date().toISOString() };
    try { fs.writeFileSync(CACHE_FILE, JSON.stringify(cache)); } catch(e) {}
    return cache;
  }
  return readCache();
}

function readCache() {
  try { return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); } catch { return null; }
}

// 向后兼容旧接口
function getCache() { return readCache(); }
function setCache(v) { try { fs.writeFileSync(CACHE_FILE, JSON.stringify(v)); } catch(e) {} }

module.exports = { fetchAndCacheAlerts, getCache, setCache };
