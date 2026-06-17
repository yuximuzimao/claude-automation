'use strict';
/**
 * 鲸灵登录态判定（纯函数，可单测，不依赖 cdp）。
 *
 * 状态判据（用户规定 2026-06-17，交叉验证防误判）：
 *   - 已登录：店铺名 <p class="readonly"> 有值。
 *   - 未登录（确证）：必须【同时】满足三条——
 *       ① 读不到店铺名
 *       ② 页面含 "商家登录"
 *       ③ 页面含 "未注册的手机号登录成功后将自动注册"
 *     三者同时满足才视为"确实在未登录的 login 页"。
 *   - 任何"既不是已登录、又不满足未登录三条件"的状态 = 未知错误 → 报异常停止。
 *     （单一特征不足以确证状态，避免把异常页/加载中页误判为未登录）
 *
 * login 页两句标志文案已真机核对（2026-06-17）确实存在且文案一致。
 */

const JL_DOMAIN = 'scrm.jlsupp.com';
const LOGIN_MARK_1 = '商家登录';
const LOGIN_MARK_2 = '未注册的手机号登录成功后将自动注册';

/**
 * @param {{url:string, title?:string, shopName:string, has商家登录:boolean, has自动注册:boolean}} info
 * @returns {{success, state?, loggedIn?, shopName?, url?, title?, error?}}
 *   state: 'logged-in' | 'logged-out'
 */
function judgeLoginState(info) {
  if (!info || !(info.url || '').includes(JL_DOMAIN)) {
    return { success: false, error: `当前 tab 不在鲸灵域名: ${info && info.url}` };
  }

  // 已登录：店铺名有值
  if (info.shopName) {
    return { success: true, state: 'logged-in', loggedIn: true, shopName: info.shopName, url: info.url, title: info.title };
  }

  // 未登录确证：读不到店铺名 且 两句标志文案同时存在
  const loginMarksBoth = !!info['has商家登录'] && !!info['has自动注册'];
  if (!info.shopName && loginMarksBoth) {
    return { success: true, state: 'logged-out', loggedIn: false, url: info.url, title: info.title };
  }

  // 既非已登录、又不满足未登录三条件 → 未知错误，报异常停止
  return {
    success: false,
    error: `未知页面状态（非已登录也非确证未登录）：shopName=${JSON.stringify(info.shopName)}, 商家登录=${!!info['has商家登录']}, 自动注册=${!!info['has自动注册']}, url=${info.url}`,
  };
}

/**
 * 在页面上下文执行的读取表达式：一次性读出判定所需全部特征。
 * 返回 JSON 字符串：{ url, title, shopName, has商家登录, has自动注册 }
 */
const READ_LOGIN_STATE_JS = `
(() => {
  const p = document.querySelector('p.readonly');
  const shopName = p ? (p.innerText || p.textContent || '').trim() : '';
  const bodyText = document.body ? (document.body.innerText || '') : '';
  return JSON.stringify({
    url: location.href,
    title: document.title,
    shopName,
    'has商家登录': bodyText.includes(${JSON.stringify(LOGIN_MARK_1)}),
    'has自动注册': bodyText.includes(${JSON.stringify(LOGIN_MARK_2)})
  });
})()
`;

/**
 * 从账号 note 提取店铺核心关键字。
 * note 格式为「核心名-品牌」（如 "百浩-RITEKOKO" / "共途-KGOS" / "上海绰绰-悦希"），
 * 取 "-" 之前的整段作为核心关键字。页面店铺名是工商全称（如"合肥百浩创展贸易有限公司"），
 * 核心关键字必为其子串。
 * @param {string} note
 * @returns {string}
 */
function shopKeyword(note) {
  if (!note) return '';
  // 取第一个分隔符（- 或 — 或 _）之前的部分，去首尾空格
  const core = String(note).split(/[-—_]/)[0].trim();
  return core;
}

/**
 * 关键字匹配：页面店铺全称是否包含 note 的核心关键字。
 * 用户规定（2026-06-17）：店铺简称的核心词必完整包含在工商全称里，用子串包含匹配，
 * 比精确匹配可靠（note 是简称、页面是全称，格式不同）。
 * @param {string} pageShopName 页面读到的工商全称
 * @param {string} accountNote  账号 note
 * @returns {boolean}
 */
function matchShopName(pageShopName, accountNote) {
  const kw = shopKeyword(accountNote);
  if (!kw || !pageShopName) return false;
  return String(pageShopName).includes(kw);
}

module.exports = {
  judgeLoginState,
  matchShopName,
  shopKeyword,
  READ_LOGIN_STATE_JS,
  JL_DOMAIN,
  LOGIN_MARK_1,
  LOGIN_MARK_2,
};
