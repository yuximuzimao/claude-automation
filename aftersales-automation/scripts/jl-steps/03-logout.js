#!/usr/bin/env node
/**
 * 鲸灵安全注入 — 原子步骤 03：退出登录（真实点击）
 *
 * 设计：独立可单测的原子脚本，单次执行、报错即停、不重试。
 *
 * 触发场景：步骤 02 判定当前登录店铺 != 目标账号（错号），需走平台正规登出，
 * 由平台清服务端 session（不暴力清 localStorage）。
 *
 * 流程（固定坐标，真机验证 2026-06-17）：
 *   1. tab 切前台（activateTarget）
 *   2. 鼠标移到右上角店铺区 (1358,28) → 等 200ms → dropdown-menu 展开
 *   3. 鼠标移到退出登录按钮 (1328,244) → 等 200ms（稳定）
 *   4. 左键点击退出登录
 *   5. 等待 → 验证已登出（URL 回到 login / 店铺名消失）
 *
 * 输出（stdout，单行 JSON）：
 *   { success:true, loggedOut:true, url }     ← 登出成功
 *   { success:false, error }                  ← 失败（报错即停，不重试）
 *
 * 用法：
 *   node scripts/jl-steps/03-logout.js <targetId>
 *
 * 风控铁律：scrm.jlsupp.com 报错即停，绝不重试。这是真实写操作（登出）。
 */

const path = require('path');
const WebSocket = require('ws');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { judgeLoginState, READ_LOGIN_STATE_JS } = require(path.join(__dirname, '../../lib/jl/login-state'));

const CHROME_PORT = 9222;
const JL_DOMAIN = 'scrm.jlsupp.com';

// 固定坐标（真机验证）
const HOVER_POINT = { x: 1358, y: 28 };    // 右上角店铺区，悬停触发下拉
const LOGOUT_POINT = { x: 1328, y: 244 };  // 退出登录按钮
const STEP_DELAY_MS = 200;                  // 每个动作后稳定延迟
const LOGOUT_WAIT_MS = 8000;                // 点击后等登出跳转（用户规定 8s）

const sleep = ms => new Promise(r => setTimeout(r, ms));

function connect(targetId) {
  const ws = new WebSocket(`ws://localhost:${CHROME_PORT}/devtools/page/${targetId}`);
  let id = 1;
  const pending = {};
  ws.on('message', d => {
    const m = JSON.parse(d);
    if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; }
  });
  function send(method, params) {
    return new Promise((res, rej) => {
      const i = id++;
      pending[i] = res;
      ws.send(JSON.stringify({ id: i, method, params: params || {} }));
      setTimeout(() => rej(new Error('CDP timeout: ' + method)), 8000);
    });
  }
  return new Promise((resolve, reject) => {
    ws.on('open', () => resolve({ send, close: () => ws.close() }));
    ws.on('error', reject);
  });
}

/**
 * 退出登录（真实点击）。错号场景下走平台正规登出。
 * @param {string} targetId 鲸灵 tab 的 CDP targetId
 */
async function logout(targetId) {
  if (!targetId) return { success: false, error: '缺少 targetId' };

  // 1. tab 切前台
  try { await cdp.activateTarget(targetId); } catch (e) { /* 非致命，继续 */ }
  await sleep(STEP_DELAY_MS);

  let conn;
  try {
    conn = await connect(targetId);
  } catch (e) {
    return { success: false, error: `连接 CDP 失败: ${e.message}` };
  }
  const { send, close } = conn;

  try {
    // 2. 移到右上角店铺区，悬停展开下拉
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: HOVER_POINT.x, y: HOVER_POINT.y });
    await sleep(STEP_DELAY_MS);

    // 验证下拉已展开（报错即停：没展开就不点，避免乱点）
    const menuOpen = await evalExpr(send, `getComputedStyle(document.querySelector('.dropdown-menu')).display === 'block'`);
    if (!menuOpen) {
      close();
      return { success: false, error: '悬停后下拉菜单未展开，中止（不盲点）' };
    }

    // 3. 移到退出登录按钮，稳定
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: LOGOUT_POINT.x, y: LOGOUT_POINT.y });
    await sleep(STEP_DELAY_MS);

    // 验证退出按钮此刻可见（报错即停）
    const btnVisible = await evalExpr(send, `(()=>{const e=[...document.querySelectorAll('.dropdown-menu-item')].find(x=>(x.innerText||'').trim()==='退出登录');if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0;})()`);
    if (!btnVisible) {
      close();
      return { success: false, error: '退出登录按钮不可见，中止（不盲点）' };
    }

    // 4. 左键点击退出登录（mousePressed + mouseReleased）
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: LOGOUT_POINT.x, y: LOGOUT_POINT.y, button: 'left', clickCount: 1 });
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: LOGOUT_POINT.x, y: LOGOUT_POINT.y, button: 'left', clickCount: 1 });
  } catch (e) {
    close();
    // 鲸灵操作报错即停，不重试
    return { success: false, error: `退出登录操作失败: ${e.message}` };
  }

  // 5. 等待登出跳转（规则：等 8s），用三条件交叉验证确证已登出
  await sleep(LOGOUT_WAIT_MS);
  let info;
  try {
    const raw = await evalExpr(send, READ_LOGIN_STATE_JS);
    info = typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch (e) {
    close();
    return { success: false, error: `登出后读取状态失败: ${e.message}` };
  }
  close();

  // 确证判据（见 lib/jl/login-state.js）：
  //   读不到店铺名 且 同时含"商家登录"+"未注册的手机号登录成功后将自动注册" → 确证登出
  //   仍是已登录 / 未知状态 → 报异常停止（不假装登出成功）
  const judged = judgeLoginState(info);
  if (judged.success && judged.state === 'logged-out') {
    return { success: true, loggedOut: true, url: judged.url };
  }
  if (judged.success && judged.state === 'logged-in') {
    return { success: false, error: `点击退出后仍处于登录态: ${judged.shopName} / ${judged.url}` };
  }
  // judged.success === false → 未知页面状态
  return { success: false, error: `登出后页面状态异常：${judged.error}` };
}

async function evalExpr(send, expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true });
  if (r.exceptionDetails) throw new Error('eval 异常: ' + (r.exceptionDetails.text || ''));
  return r.result && r.result.result && r.result.result.value;
}

// CLI 入口
if (require.main === module) {
  const targetId = process.argv[2];
  logout(targetId)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { logout, HOVER_POINT, LOGOUT_POINT, STEP_DELAY_MS };
