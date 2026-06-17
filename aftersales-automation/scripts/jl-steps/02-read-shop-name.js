#!/usr/bin/env node
/**
 * 鲸灵安全注入 — 原子步骤 02：读取登录态（纯读，不点击）
 *
 * 设计：独立可单测的原子脚本，单次执行、报错即停、不重试。
 *
 * 本步只做一件事：在已打开的鲸灵 tab 上判定登录态。
 *   - 打开页面后必须等 8 秒再读（平台登录态跳转是异步的，读早了会落在 login 页读不到）
 *   - 判据（交叉验证防误判，见 lib/jl/login-state.js）：
 *       已登录   → 店铺名 <p class="readonly"> 有值
 *       未登录   → 读不到店铺名 且 同时含"商家登录"+"未注册的手机号登录成功后将自动注册"
 *       其它     → 未知错误，报异常停止（不把异常页误判为未登录）
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
const { judgeLoginState, READ_LOGIN_STATE_JS } = require(path.join(__dirname, '../../lib/jl/login-state'));

const DEFAULT_WAIT_MS = 8000;          // 打开后固定等 8 秒再读（用户规定）

// 退出登录交互坐标（固定，真机验证）。本步不使用，导出供 03 退出脚本复用。
const LOGOUT_HOVER_POINT = { x: 1358, y: 28 };
const LOGOUT_BUTTON_POINT = { x: 1328, y: 244 };

/**
 * 读当前登录态。
 * @param {string} targetId  鲸灵 tab 的 CDP targetId（由步骤 01 返回）
 * @param {number} waitMs    读取前等待毫秒（默认 8000）
 */
async function readShopName(targetId, waitMs = DEFAULT_WAIT_MS) {
  if (!targetId) return { success: false, error: '缺少 targetId' };

  // 1. 等待页面登录态跳转稳定（规则：固定等 8s）
  await new Promise(r => setTimeout(r, waitMs));

  // 2. 一次性读出判定所需全部特征（纯读）
  let info;
  try {
    const raw = await cdp.eval(targetId, READ_LOGIN_STATE_JS);
    info = typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch (e) {
    return { success: false, error: `读取页面失败: ${e.message}` };
  }

  // 3. 纯函数判定登录态（含未知状态报异常）
  return judgeLoginState(info);
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
};
