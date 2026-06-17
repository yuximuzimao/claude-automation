#!/usr/bin/env node
/**
 * 鲸灵安全注入 — 原子步骤 04：注入目标账号 + 验证登录成功
 *
 * 设计：独立可单测的原子脚本，单次执行、报错即停、不重试。
 *
 * 触发场景：步骤 02 判定错号、步骤 03 已登出（确证未登录），现注入目标账号。
 *
 * 流程：
 *   1. 调用 sessions/jl.js inject <num>（复用现有注入，保持 CLI 契约）
 *   2. 注入成功后等 8 秒（规则：等登录态跳转稳定）
 *   3. 找鲸灵 tab，用 lib/jl/login-state 判据验证：
 *        state=logged-in 且 店铺名匹配目标账号 → 成功
 *        否则报异常停止（不假装成功）
 *
 * 输出（stdout，单行 JSON）：
 *   { success:true,  loggedIn:true, shopName, accountNum, url }
 *   { success:false, error }
 *
 * 用法：
 *   node scripts/jl-steps/04-inject.js <accountNum>            # 默认等 8s
 *   node scripts/jl-steps/04-inject.js <accountNum> <waitMs>   # 自定义等待
 *
 * 风控铁律：scrm.jlsupp.com 报错即停，绝不重试。真实写操作（注入登录）。
 */

const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { judgeLoginState, matchShopName, shopKeyword, READ_LOGIN_STATE_JS, JL_DOMAIN } = require(path.join(__dirname, '../../lib/jl/login-state'));

const SESSIONS_DIR = path.join(__dirname, '../../../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');
const DEFAULT_WAIT_MS = 8000;

/** 读账号 note（供店铺名匹配验证用） */
function getAccountNote(accountNum) {
  try {
    const accounts = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));
    const a = accounts[String(accountNum)];
    return a ? (a.note || a.name || '') : '';
  } catch (e) {
    return '';
  }
}

/**
 * 注入目标账号并验证登录。
 * @param {string|number} accountNum 账号编号
 * @param {number} waitMs 注入后等待毫秒（默认 8000）
 */
async function inject(accountNum, waitMs = DEFAULT_WAIT_MS) {
  if (!accountNum) return { success: false, error: '缺少 accountNum' };

  // 1. 调 jl.js inject（复用现有注入逻辑）
  const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
    timeout: 30000, encoding: 'utf8',
  });
  if (inj.status !== 0) {
    const msg = (inj.stderr || inj.stdout || '').trim().slice(0, 200);
    return { success: false, error: `jl.js inject 失败: ${msg}` };
  }

  // 2. 等注入写入稳定（规则：等 8s）
  await new Promise(r => setTimeout(r, waitMs));

  // 3. 找鲸灵 tab
  let targets;
  try {
    targets = await cdp.getTargets();
  } catch (e) {
    return { success: false, error: `列出 tab 失败: ${e.message}` };
  }
  const jlTab = (targets || []).find(t => t.type === 'page' && t.url && t.url.includes(JL_DOMAIN));
  if (!jlTab) {
    return { success: false, error: '注入后未找到鲸灵 tab' };
  }

  // 4. 刷新页面让注入的 session 在页面生效。
  //    jl.js inject 已去掉注入后导航（纯注入只写 cookie/localStorage），页面仍停在注入前
  //    的 login/未登录态，不重新加载平台就识别不到登录 → 必报"注入后仍未登录"。
  //    刷新=重新打开当前 URL（带新 cookie 加载，平台自动跳后台），等价用户手动 F5。
  //    此处页面本就是 login/未登录态，刷新它不违反「复用 tab 禁导航」（那条针对禁止把
  //    已登录后台页导回 login，方向相反）。报错即停，不重试。
  try {
    await cdp.navigate(jlTab.id, jlTab.url);
  } catch (e) {
    return { success: false, error: `注入后刷新页面失败: ${e.message}` };
  }
  // 5. 再等登录态跳转稳定（规则：等 8s）
  await new Promise(r => setTimeout(r, waitMs));

  let info;
  try {
    const raw = await cdp.eval(jlTab.id, READ_LOGIN_STATE_JS);
    info = typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch (e) {
    return { success: false, error: `读取登录态失败: ${e.message}` };
  }

  const judged = judgeLoginState(info);
  if (judged.success && judged.state === 'logged-in') {
    // 已登录 → 再验店铺名是否匹配目标账号（关键字包含匹配，防注入到错号）
    const note = getAccountNote(accountNum);
    if (note && !matchShopName(judged.shopName, note)) {
      return {
        success: false,
        error: `注入后店铺名不匹配目标账号：页面="${judged.shopName}" 期望含关键字="${shopKeyword(note)}"（note="${note}"）`,
      };
    }
    return { success: true, loggedIn: true, shopName: judged.shopName, accountNum: String(accountNum), matchedNote: note, url: judged.url, targetId: jlTab.id };
  }
  if (judged.success && judged.state === 'logged-out') {
    return { success: false, error: `注入后仍未登录（session 可能失效）: ${judged.url}` };
  }
  return { success: false, error: `注入后页面状态异常：${judged.error}` };
}

// CLI 入口
if (require.main === module) {
  const accountNum = process.argv[2];
  const waitMs = process.argv[3] ? Number(process.argv[3]) : DEFAULT_WAIT_MS;
  inject(accountNum, waitMs)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { inject, DEFAULT_WAIT_MS };
