#!/usr/bin/env node
/**
 * 鲸灵安全注入 — 原子步骤 02：读取登录态（纯读，不点击）
 *
 * 设计：独立可单测的原子脚本，单次执行、报错即停、不重试。
 *
 * 本步只做一件事：在已打开的鲸灵 tab 上判定登录态。
 *   - 打开页面后必须等 8 秒再读（平台登录态跳转是异步的，读早了会落在 login 页读不到）
 *   - 判据（交叉验证防误判，见 lib/jl/login-state.js）：
 *       已登录   → 店铺名 <p class="readonly"> 有真实店铺名
 *       未登录   → 读不到店铺名 且 同时含"商家登录"+"未注册的手机号登录成功后将自动注册"
 *       瞬时态   → "新用户"或鲸灵微应用尚未形成上述可信特征，只读有界等待
 *       其它     → 等待上限后仍未知则报异常停止（不把异常页误判为未登录）
 *   - 纯读：不悬停、不点击、不注入。店铺名即使藏在隐藏下拉里 innerText 仍可读（已真机验证）
 *
 * 退出登录按钮位置（固定坐标，真机验证 2026-06-17，供 03 退出脚本用，本步不触发）：
 *   - 悬停触发点（右上角店铺区 div.user 中心）：(1358, 28)
 *   - 退出登录按钮（菜单展开后）：(1328, 244)
 *
 * 输出（stdout，单行 JSON）：
 *   { success:true, state:'logged-in',  loggedIn:true,  shopName, url, title }
 *   { success:true, state:'logged-out', loggedIn:false, url, title }
 *   { success:false, error }   ← 读取出错 / 未知页面状态
 *
 * 用法：
 *   node scripts/jl-steps/02-read-shop-name.js <targetId>            # 默认等 8s
 *   node scripts/jl-steps/02-read-shop-name.js <targetId> <waitMs>   # 自定义等待（测试用）
 *
 * 风控铁律：scrm.jlsupp.com 报错即停，绝不重试。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { judgeLoginState, READ_LOGIN_STATE_JS, JL_DOMAIN } = require(path.join(__dirname, '../../lib/jl/login-state'));

const DEFAULT_WAIT_MS = 8000;          // 打开后固定等 8 秒再读（用户规定）
const SETTLE_RETRY_MS = 1000;
const SETTLE_MAX_RETRIES = 8;

// 退出登录交互坐标（固定，真机验证）。本步不使用，导出供 03 退出脚本复用。
const LOGOUT_HOVER_POINT = { x: 1358, y: 28 };
const LOGOUT_BUTTON_POINT = { x: 1328, y: 244 };

/**
 * 读当前登录态。
 * @param {string} targetId  鲸灵 tab 的 CDP targetId（由步骤 01 返回）
 * @param {number} waitMs    读取前等待毫秒（默认 8000）
 */
async function readShopName(targetId, waitMs = DEFAULT_WAIT_MS, options = {}) {
  if (!targetId) return { success: false, error: '缺少 targetId' };

  const cdpClient = options.cdp || cdp;
  const sleep = options.sleep || (ms => new Promise(r => setTimeout(r, ms)));
  const settleRetryMs = options.settleRetryMs == null ? SETTLE_RETRY_MS : Number(options.settleRetryMs);
  const settleMaxRetries = options.settleMaxRetries == null ? SETTLE_MAX_RETRIES : Number(options.settleMaxRetries);

  // 1. 等待页面登录态跳转稳定（规则：默认固定等 8s）
  await sleep(waitMs);

  // 2. 瞬时状态只在本层吸收：业务层不能看到 transitional，也不能把空白微应用当终态。
  // 只做有界纯读；若始终无法进入可信终态，则明确失败，不触发清理/注入。
  let lastInfo = null;
  let lastJudged = null;
  for (let attempt = 0; attempt <= settleMaxRetries; attempt++) {
    try {
      const raw = await cdpClient.eval(targetId, READ_LOGIN_STATE_JS);
      lastInfo = typeof raw === 'string' ? JSON.parse(raw) : raw;
    } catch (e) {
      return { success: false, error: `读取页面失败: ${e.message}` };
    }

    lastJudged = judgeLoginState(lastInfo);
    const isTransition = lastJudged && lastJudged.success === true && lastJudged.state === 'transitional';
    const isUnsettledJlPage = lastJudged && lastJudged.success === false &&
      lastInfo && (lastInfo.url || '').includes(JL_DOMAIN) &&
      !lastInfo.shopName &&
      !lastInfo['has商家登录'] &&
      !lastInfo['has自动注册'];

    if (!isTransition && !isUnsettledJlPage) return lastJudged;

    if (attempt === settleMaxRetries) {
      if (isTransition) {
        return {
          success: false,
          error: `页面长时间停留在切号过渡态：页面="${lastInfo.shopName || ''}"，url=${lastInfo.url || ''}`,
        };
      }
      return {
        success: false,
        error: `页面长时间未形成可信登录态：shopName=${JSON.stringify(lastInfo && lastInfo.shopName || '')}, url=${lastInfo && lastInfo.url || ''}`,
      };
    }
    await sleep(settleRetryMs);
  }

  return lastJudged || { success: false, error: '读取登录态失败' };
}

// CLI 入口
if (require.main === module) {
  const targetId = process.argv[2];
  const waitMs = process.argv[3] ? Number(process.argv[3]) : DEFAULT_WAIT_MS;
  readShopName(targetId, waitMs)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = {
  readShopName,
  judgeLoginState,
  LOGOUT_HOVER_POINT,
  LOGOUT_BUTTON_POINT,
  DEFAULT_WAIT_MS,
  SETTLE_RETRY_MS,
  SETTLE_MAX_RETRIES,
};
