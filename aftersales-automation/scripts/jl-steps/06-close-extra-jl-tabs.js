#!/usr/bin/env node
'use strict';
/**
 * 鲸灵安全注入 — 原子步骤 06：关闭多余鲲灵 tab，只保留第一个。
 *
 * 只调用本地 Chrome close target 端点；逐个关闭，任一失败立即停止，不重试。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { countJlTabs } = require('./05-count-jl-tabs');

const DEFAULT_CLOSE_GAP_MS = 300;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function closeExtraJlTabs(options = {}) {
  const sleepMs = options.sleepMs == null ? DEFAULT_CLOSE_GAP_MS : options.sleepMs;
  const counted = await countJlTabs();
  if (!counted || !counted.success) {
    return { success: false, error: counted && counted.error ? counted.error : '统计鲲灵 tab 失败' };
  }

  const tabs = counted.tabs || [];
  if (counted.count === 0) {
    return { success: true, count: 0, closed: [], keptTargetId: null };
  }
  const keptTargetId = tabs[0] && tabs[0].id;
  if (counted.count === 1) {
    return { success: true, count: 1, closed: [], keptTargetId };
  }
  if (!keptTargetId) {
    return { success: false, count: counted.count, closed: [], keptTargetId: null, error: '无法确定保留的鲲灵 tab' };
  }

  const closed = [];
  for (const tab of tabs.slice(1)) {
    try {
      await cdp.closeTarget(tab.id);
      closed.push(tab.id);
      if (sleepMs > 0) await sleep(sleepMs);
    } catch (e) {
      return {
        success: false,
        count: counted.count,
        closed,
        keptTargetId,
        error: e.message,
      };
    }
  }

  return { success: true, count: counted.count, closed, keptTargetId };
}

if (require.main === module) {
  closeExtraJlTabs()
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { closeExtraJlTabs, DEFAULT_CLOSE_GAP_MS };
