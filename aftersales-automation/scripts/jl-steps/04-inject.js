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
 *   3. 找鲸灵 tab，固定导航售后列表，再用 lib/jl/login-state 判据验证：
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
 *   编排调用 inject(accountNum, { targetId })                  # 只操作已解析/已清理 tab
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
const AFTER_SALE_LIST_URL = 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list';

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

function normalizeInjectOptions(waitMsOrOptions) {
  if (waitMsOrOptions && typeof waitMsOrOptions === 'object') {
    return {
      waitMs: waitMsOrOptions.waitMs == null ? DEFAULT_WAIT_MS : Number(waitMsOrOptions.waitMs),
      targetId: waitMsOrOptions.targetId ? String(waitMsOrOptions.targetId) : null,
    };
  }
  return {
    waitMs: waitMsOrOptions == null ? DEFAULT_WAIT_MS : Number(waitMsOrOptions),
    targetId: null,
  };
}

function resolveInjectionTargetId(explicitTargetId, targets = []) {
  if (explicitTargetId) return String(explicitTargetId);

  const jlTabs = targets.filter(t =>
    t && t.type === 'page' && t.url && t.url.includes(JL_DOMAIN)
  );
  if (jlTabs.length === 0) throw new Error('注入后未找到鲸灵 tab');
  if (jlTabs.length > 1) {
    throw new Error(`注入后发现多个鲸灵 tab（${jlTabs.length}），必须明确传入 targetId`);
  }
  if (!jlTabs[0].id) throw new Error('唯一鲸灵 tab 缺少 targetId');
  return jlTabs[0].id;
}

/**
 * 注入目标账号并验证登录。
 * @param {string|number} accountNum 账号编号
 * @param {number|{waitMs?:number,targetId?:string}} waitMsOrOptions 等待时间或编排目标
 */
async function inject(accountNum, waitMsOrOptions = DEFAULT_WAIT_MS) {
  if (!accountNum) return { success: false, error: '缺少 accountNum' };
  const { waitMs, targetId: requestedTargetId } = normalizeInjectOptions(waitMsOrOptions);

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

  // 3. 编排调用只使用已解析/已清理 targetId；CLI 兼容路径只接受唯一鲸灵 tab。
  let targets = [];
  if (!requestedTargetId) {
    try {
      targets = await cdp.getTargets();
    } catch (e) {
      return { success: false, error: `列出 tab 失败: ${e.message}` };
    }
  }
  let targetId;
  try {
    targetId = resolveInjectionTargetId(requestedTargetId, targets);
  } catch (e) {
    return { success: false, error: e.message };
  }

  // 4. 固定进入售后列表，让新认证态生效且不继承旧详情页上下文。
  try {
    await cdp.navigate(targetId, AFTER_SALE_LIST_URL);
  } catch (e) {
    return { success: false, error: `注入后导航售后列表失败: ${e.message}` };
  }
  // 5. 再等登录态跳转稳定（规则：等 8s）
  await new Promise(r => setTimeout(r, waitMs));

  let info;
  try {
    const raw = await cdp.eval(targetId, READ_LOGIN_STATE_JS);
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
    return { success: true, loggedIn: true, shopName: judged.shopName, accountNum: String(accountNum), matchedNote: note, url: judged.url, targetId };
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

module.exports = {
  inject,
  normalizeInjectOptions,
  resolveInjectionTargetId,
  DEFAULT_WAIT_MS,
  AFTER_SALE_LIST_URL,
};
