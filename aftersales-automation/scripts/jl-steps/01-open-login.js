#!/usr/bin/env node
/**
 * 鲸灵安全注入 — 原子步骤 01：打开 login 页（最简版，像点收藏夹）
 *
 * 设计：每个步骤是独立可单测的原子脚本，单次执行、报错即停、不重试、
 * 不连带影响其他步骤。最后由编排脚本把验证过的原子步串起来。
 *
 * 本步只做一件事：像真人点收藏夹一样，新开一个标签输入 login URL。
 *   - 新开标签直达 URL（= 浏览器地址栏输入网址回车），不注入任何东西
 *   - 不查找现有 tab、不对已有 tab 强行 navigate（那会让已登录的后台页被导回 login，
 *     正是风控眼里的异常行为）
 *   - 已登录 → 平台自己跳后台停住；未登录 → 停在 login 页
 *
 * ⚠️ 本版「最简：不考虑已有 tab」。多 tab 检测/去重（确保只剩一个鲸灵 tab）
 *    是下一版增量，单独脚本，不在本步。
 *
 * 输出（stdout，单行 JSON）：
 *   成功 { success:true, targetId, url, title, readyState }
 *   失败 { success:false, error }
 *
 * 用法：
 *   node scripts/jl-steps/01-open-login.js          # 默认 login URL
 *   node scripts/jl-steps/01-open-login.js <url>     # 指定 URL（测试用）
 *
 * 风控铁律：scrm.jlsupp.com 报错即停，绝不重试。单次执行，失败直接返回。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

const LOGIN_URL = 'https://scrm.jlsupp.com/micro-businessPlatform/login';
const JL_DOMAIN = 'scrm.jlsupp.com';

/**
 * 新开标签打开 login 页（像点收藏夹，纯打开，不注入、不复用、不导航现有 tab）。
 * @param {string} loginUrl
 * @returns {Promise<{success, targetId?, url?, title?, readyState?, error?}>}
 */
async function openLogin(loginUrl = LOGIN_URL) {
  // 新开一个标签直达 URL（= 地址栏输入网址回车）。Chrome 自己加载，
  // 已登录则平台自动跳后台，未登录停 login。我们不做任何额外导航。
  let targetId;
  try {
    const created = await cdp.createTarget(loginUrl);
    targetId = created && created.id;
    if (!targetId) {
      return { success: false, error: '新建 tab 未返回 targetId' };
    }
  } catch (e) {
    return { success: false, error: `打开 login 页失败: ${e.message}` };
  }

  // 等页面加载稳定：轮询 readyState=complete（最多 ~10s），不主动 reload/navigate。
  // 仅被动读取，不构成对页面的操作。
  let info;
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 500));
    try {
      const raw = await cdp.eval(
        targetId,
        `JSON.stringify({ url: location.href, title: document.title, readyState: document.readyState })`
      );
      info = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (info && info.readyState === 'complete') break;
    } catch (e) {
      // 页面跳转中 eval 可能短暂失败，继续轮询（被动等待，非行为操作）
    }
  }

  if (!info) {
    return { success: false, error: '打开后无法读取页面状态', targetId };
  }
  if (!(info.url || '').includes(JL_DOMAIN)) {
    return { success: false, error: `打开后 URL 不在鲸灵域名: ${info.url}`, targetId };
  }
  return {
    success: true,
    targetId,
    url: info.url,
    title: info.title,
    readyState: info.readyState,
  };
}

// CLI 入口
if (require.main === module) {
  const url = process.argv[2] || LOGIN_URL;
  openLogin(url)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { openLogin, LOGIN_URL, JL_DOMAIN };
