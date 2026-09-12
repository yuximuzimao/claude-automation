'use strict';
/**
 * WHAT: 鲸灵首页提醒信息抓取 + 持久化缓存（文件，按账号分组）
 * WHERE: routes.js（GET /api/jl-alerts） + scan-all.js（每账号扫完后读取）
 * WHY: scan-all.js 是子进程，内存缓存无法共享主进程，必须用文件作为缓存媒介
 *
 * 缓存结构：{ byAccount: { "1": { num, note, items, fetchedAt }, ... }, updatedAt }
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');

const CACHE_FILE = path.join(__dirname, '../../data/jl-alerts-cache.json');
const ACCOUNTS_FILE = path.join(__dirname, '../../../sessions/accounts.json');

function readAccountNotes() {
  try {
    const accounts = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));
    return Object.fromEntries(Object.entries(accounts).map(([num, account]) => [
      String(num),
      String((account && (account.note || account.name)) || `账号${num}`).trim(),
    ]));
  } catch {
    return null;
  }
}

function writeCache(cache) {
  const serialized = JSON.stringify(cache);
  const tmpPath = `${CACHE_FILE}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(tmpPath, serialized);
  fs.renameSync(tmpPath, CACHE_FILE);
  const readBack = fs.readFileSync(CACHE_FILE, 'utf8');
  if (readBack !== serialized) throw new Error('平台提醒缓存写入后校验失败');
}

function reconcileCacheAccounts(cache, accountNotes) {
  if (!cache || !cache.byAccount || !accountNotes) return { cache, changed: false };
  const next = { ...cache, byAccount: { ...cache.byAccount } };
  let changed = false;
  for (const [key, entry] of Object.entries(next.byAccount)) {
    const expectedNote = accountNotes[String(key)];
    const cachedNote = String((entry && entry.note) || '').trim();
    if (!expectedNote || cachedNote !== expectedNote) {
      delete next.byAccount[key];
      changed = true;
    }
  }
  if (changed) next.updatedAt = new Date().toISOString();
  return { cache: next, changed };
}

function validateAlertAccount(accountNum, accountNote, accountNotes) {
  const key = String(accountNum || 'unknown');
  const suppliedNote = String(accountNote || '').trim();
  if (!accountNotes) return { ok: true, key, note: suppliedNote || key };
  const expectedNote = accountNotes[key];
  if (!expectedNote) return { ok: false, key, reason: '账号不存在' };
  if (suppliedNote !== expectedNote) return { ok: false, key, reason: '店铺显示名不匹配' };
  return { ok: true, key, note: expectedNote };
}

async function fetchAndCacheAlerts(accountNum, accountNote) {
  const accountNotes = readAccountNotes();
  const accountGuard = validateAlertAccount(accountNum, accountNote, accountNotes);
  if (!accountGuard.ok) {
    console.warn(`[alerts] 账号${accountGuard.key}${accountGuard.reason}，拒绝读取首页提醒`);
    return readCache();
  }
  const { key } = accountGuard;

  const targets = await cdp.getTargets();
  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  if (!jl) return readCache();

  // 点左侧导航栏「后台首页」按钮（fixed 定位，不受页面滚动影响）
  // 用 URL 直跳可能绕过 Vue router 导致弹窗时序问题，点按钮和人工操作行为一致
  const curUrl = await cdp.eval(jl.id, 'window.location.href').catch(() => '');
  if (!curUrl.includes('/business/home')) {
    const clicked = await cdp.eval(jl.id, `
      (() => {
        const btn = Array.from(document.querySelectorAll('.nav-item')).find(el =>
          (el.innerText || el.textContent || '').trim() === '后台首页'
        );
        if (btn) btn.click();
        return !!btn;
      })()
    `).catch(() => false);
    if (!clicked) {
      console.warn('[alerts] 未找到「后台首页」导航按钮，跳过');
      return readCache();
    }
    await new Promise(r => setTimeout(r, 4000));
  }

  const items = await cdp.eval(jl.id, `
    Array.from(document.querySelectorAll('.scroll-item')).map(el => ({
      title: (el.querySelector('.title')?.innerText || '').trim(),
      content: (el.querySelector('.content')?.innerText || '').trim(),
    })).filter(i => i.title || i.content)
  `).catch(() => []);

  if (Array.isArray(items) && items.length > 0) {
    const cache = readCache() || { byAccount: {} };
    cache.byAccount[key] = { num: accountNum, note: accountGuard.note, items, fetchedAt: new Date().toISOString() };
    cache.updatedAt = new Date().toISOString();
    try { writeCache(cache); } catch(e) {}
    return cache;
  }
  return readCache();
}

function readCache() {
  try {
    let raw = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
    // 兼容旧格式（items 数组）→ 迁移为 byAccount
    if (raw && raw.items && !raw.byAccount) {
      raw = { byAccount: {}, updatedAt: raw.fetchedAt };
    }
    const reconciled = reconcileCacheAccounts(raw, readAccountNotes());
    if (reconciled.changed) {
      try { writeCache(reconciled.cache); } catch(e) {}
    }
    return reconciled.cache;
  } catch { return null; }
}

// 向后兼容旧接口
function getCache() { return readCache(); }
function setCache(v) { try { writeCache(v); } catch(e) {} }

/**
 * 每次扫描完成后调：对未扫描的账号做 24h 过期判断。
 * @param {Set<number>|number[]} scannedNums — 本次被扫描的账号编号
 */
function expireStaleAlerts(scannedNums) {
  const scanned = new Set((scannedNums || []).map(String));
  const cache = readCache();
  if (!cache || !cache.byAccount) return;
  const now = Date.now();
  const H24 = 24 * 3600000;
  let changed = false;

  for (const key of Object.keys(cache.byAccount)) {
    if (scanned.has(key)) continue; // 被扫描的账号不管，扫描时 fetchAndCacheAlerts 已更新
    const entry = cache.byAccount[key];
    if (!entry || !entry.fetchedAt) continue;
    const age = now - new Date(entry.fetchedAt).getTime();
    if (age >= H24) {
      // 超过 24h：清空提醒，刷新时间
      cache.byAccount[key] = {
        num: entry.num,
        note: entry.note,
        items: [],
        fetchedAt: new Date().toISOString(),
      };
      changed = true;
      console.log(`[alerts] 账号${key} (${entry.note || '未知'}) 提醒已超24h，清空`);
    }
    // < 24h：保留旧提醒，不做任何操作
  }

  if (changed) {
    cache.updatedAt = new Date().toISOString();
    try { writeCache(cache); } catch(e) {}
  }
  return cache;
}

module.exports = {
  fetchAndCacheAlerts,
  getCache,
  setCache,
  expireStaleAlerts,
  reconcileCacheAccounts,
  validateAlertAccount,
  readAccountNotes,
};
