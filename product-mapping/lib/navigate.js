'use strict';
// 移植自售后工单项目 lib/erp/navigate.js
// 核心：reload → 登录检测 → hash 导航 → hash 验证
const cdp = require('./cdp');
const { sleep, retry } = require('./wait');

const PAGE_MAP = {
  '商品档案V2': '#/prod/parallel/',
  '商品对应表': '#/prod/prod_correspondence_next/',
};

const CHECK_LOGIN_JS =
  '(function(){' +
  '  var isOut=window.location.href.includes("login")||!document.title.includes("快麦ERP--");' +
  '  var sessionExpired=!!document.querySelector(".inner-login-wrapper");' +
  '  return JSON.stringify({loggedIn:!isOut&&!sessionExpired,title:document.title,sessionExpired:sessionExpired});' +
  '})()';

async function checkLogin(targetId) {
  const raw = await cdp.eval(targetId, CHECK_LOGIN_JS);
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

/**
 * 导航到 ERP 指定页面
 * 流程：reload → 等 5s → 检登录 → hash 跳转 → 验 hash → 等 Vue mount
 */
async function navigateErp(targetId, pageName) {
  const targetHash = PAGE_MAP[pageName];
  if (!targetHash) throw new Error(`未知页面: ${pageName}`);

  // 1. 先刷新，让掉线弹窗出现
  try { await cdp.eval(targetId, 'location.reload(); "ok"'); } catch (_) {}
  await sleep(5000);

  // 2. 检查登录状态
  const loginStatus = await checkLogin(targetId);
  if (!loginStatus.loggedIn) {
    throw new Error(`ERP 未登录或 session 超时，请手动刷新登录后重试。title=${loginStatus.title}, sessionExpired=${loginStatus.sessionExpired}`);
  }

  // 3. 导航 + 验证 hash
  await retry(async () => {
    const currentHash = await cdp.eval(targetId, 'window.location.hash');
    if (currentHash === targetHash) {
      // 已在目标页，等 Vue mount
      await sleep(4000);
      return;
    }

    // 点顶部 tab
    const clickTabJS =
      '(function(){' +
      '  var li=Array.from(document.querySelectorAll("li.fix-tab")).find(function(el){' +
      '    return el.textContent.trim()===' + JSON.stringify(pageName) + ';' +
      '  });' +
      '  if(!li) return "not found";' +
      '  li.click();return "clicked";' +
      '})()';
    const result = await cdp.eval(targetId, clickTabJS);
    if (result === 'not found') throw new Error(`顶部标签未找到: ${pageName}`);
    await sleep(3000);

    // 验证 hash
    const hash = await cdp.eval(targetId, 'window.location.hash');
    if (hash !== targetHash) throw new Error(`导航失败: 期望 ${targetHash}，实际 ${hash}`);

    // 等 Vue mount
    await sleep(2000);
  }, { maxRetries: 3, delayMs: 6000, label: `nav ${pageName}` });
}

module.exports = { navigateErp, checkLogin };
