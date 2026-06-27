#!/usr/bin/env node
'use strict';
/**
 * 鲸灵安全注入 — 原子步骤 07：清当前 tab 的鲸灵 cookie/storage（注入前清场）
 *
 * 设计：独立可单测的原子脚本，单次执行、报错即停、不重试。
 *
 * 为什么需要：鲸灵"退出登录"是破坏性操作（让原账号服务端 session 失效），不能用来
 * 切换账号。改为注入新账号前先清掉当前 tab 的旧账号 cookie/storage——保证传给平台的
 * 只有新注入的认证信息，不混旧账号。
 *
 * 关键（2026-06-17 真机+Codex 审查证实）：真正的登录凭证 JSESSIONID 在
 * seller-portal.jlsupp.com/merchant，默认 getCookies({}) 看不到它会漏清→混账号。
 * cdp.clearJlCookiesAndStorage 已显式覆盖全部 jlsupp 子域。
 *
 * 输出（stdout，单行 JSON）：
 *   { success:true, targetId, deletedCount, verified:true, remainingAuthCookies:[] }
 *   { success:false, error }
 *
 * 用法：node scripts/jl-steps/07-clear-jl-data.js <targetId>
 *
 * 风控铁律：只清 jlsupp 域，不碰 ERP；报错即停，绝不重试。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

async function clearJlData(targetId) {
  if (!targetId) return { success: false, error: '缺少 targetId' };
  try {
    const r = await cdp.clearJlCookiesAndStorage(targetId);
    if (r.verified !== true) {
      return {
        ...r,
        success: false,
        targetId,
        error: '清理鲸灵数据失败: 认证 Cookie 清理验证失败',
      };
    }
    return { ...r, success: true, targetId };
  } catch (e) {
    return { success: false, error: `清理鲸灵数据失败: ${e.message}`, targetId };
  }
}

// CLI 入口
if (require.main === module) {
  const targetId = process.argv[2];
  clearJlData(targetId)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { clearJlData };
