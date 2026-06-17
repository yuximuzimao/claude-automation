#!/usr/bin/env node
'use strict';
/**
 * 鲸灵安全注入 — 原子步骤 05：统计鲲灵 tab 数量。
 *
 * 纯读取 Chrome targets，不执行页面行为、不导航、不重试。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

const JL_DOMAIN = 'scrm.jlsupp.com';

function isJlPageTarget(target) {
  return Boolean(
    target &&
    target.type === 'page' &&
    target.url &&
    target.url.includes(JL_DOMAIN)
  );
}

async function countJlTabs() {
  try {
    const targets = await cdp.getTargets();
    const tabs = (targets || [])
      .filter(isJlPageTarget)
      .map(t => ({ id: t.id, url: t.url, title: t.title || '' }));
    return { success: true, count: tabs.length, tabs };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

if (require.main === module) {
  countJlTabs()
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { countJlTabs, isJlPageTarget, JL_DOMAIN };
