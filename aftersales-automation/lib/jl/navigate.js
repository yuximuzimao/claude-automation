'use strict';
const cdp = require('../cdp');
const { sleep, retry } = require('../wait');

// Vue Router 导航到目标路径，带前置检查和重试
// target: targetId; path: 路径如 '/business/after-sale-list'; query: {workOrderNum: '...'} 可选
async function navigate(targetId, path, query) {
  const currentUrl = await cdp.eval(targetId, 'window.location.href');

  // 已在目标路径则跳过
  if (currentUrl.includes(path)) {
    if (!query) return;
    // 有 query 时检查是否完全匹配
    const currentSearch = await cdp.eval(targetId, 'window.location.search + window.location.hash');
    const queryKey = Object.keys(query)[0];
    if (currentSearch.includes(query[queryKey])) return;
  }

  // 如果不在列表页，先回列表页
  if (!currentUrl.includes('after-sale-list') && path !== '/business/after-sale-list') {
    await navigate(targetId, '/business/after-sale-list');
  }

  const pushCode = query
    ? `var v=document.querySelector('#app').__vue__;v.$router.push({path:'${path}',query:${JSON.stringify(query)}});'pushed'`
    : `var v=document.querySelector('#app').__vue__;v.$router.push('${path}');'pushed'`;

  await retry(async () => {
    await cdp.eval(targetId, pushCode);
    await sleep(3000);
    const url = await cdp.eval(targetId, 'window.location.href');
    if (!url.includes(path)) throw new Error(`导航失败：当前 ${url}，期望包含 ${path}`);
    if (query) {
      const qv = Object.values(query)[0];
      if (!url.includes(qv)) throw new Error(`导航成功但 query 不匹配: ${url}`);
    }
  }, { maxRetries: 2, delayMs: 2000, label: `navigate to ${path}` });
}

module.exports = { navigate };
