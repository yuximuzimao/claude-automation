'use strict';
/**
 * 鲸灵账号 note → ERP 商品对应表店铺名 映射表
 *
 * ERP 可用店铺（2026-04-09 实测）：
 * 汐澜 / 顺链 / 煜嘉轩 / 百浩创展 / 泓砚 / 丰瑞宁 / 蓄力生长 / 曼玲 /
 * 杭州共途 / 上海绰绰 / 成都展宏妍 / 厦门蒲颜
 *
 * 已停用：悦希（老店铺）、汉益仙（老店铺）
 */
const SHOP_MAP = [
  { noteKeyword: '汐澜',     erpShop: '汐澜' },
  { noteKeyword: '展宏妍',   erpShop: '成都展宏妍' },
  { noteKeyword: '百浩',     erpShop: '百浩创展' },
  { noteKeyword: '蓄力生长', erpShop: '蓄力生长' },
  { noteKeyword: '共途',     erpShop: '杭州共途' },
  { noteKeyword: '上海绰绰', erpShop: '上海绰绰' },
  { noteKeyword: '厦门蒲颜', erpShop: '厦门蒲颜' },
  { noteKeyword: '泓砚',     erpShop: '泓砚' },
  { noteKeyword: '丰瑞宁',   erpShop: '丰瑞宁' },
  { noteKeyword: '煜嘉轩',   erpShop: '煜嘉轩' },
  { noteKeyword: '曼玲',     erpShop: '曼玲' },
  { noteKeyword: '顺链',     erpShop: '顺链' },
  { noteKeyword: '澜泽',     erpShop: '澜泽' },
];

/**
 * 根据账号 note 查找对应 ERP 店铺名
 * @param {string} note  accounts.json 中的 note 字段（如「百浩-RITEKOKO」）
 * @returns {string}     ERP 店铺名（如「百浩创展」）
 *
 * 规则优先级：
 *   1. SHOP_MAP 显式映射（noteKeyword 为 note 子串）
 *   2. 默认 fallback：取 note 中首个「-」前的部分作为店铺名
 *      （如「新店铺-XSHOP」→「新店铺」，仅在新店铺未加入 SHOP_MAP 时生效）
 */
function getErpShop(note) {
  const match = SHOP_MAP.find(m => note.includes(m.noteKeyword));
  if (match) return match.erpShop;

  // 新店铺 fallback：取破折号前的部分作为 ERP 店铺名
  const derived = (note.split('-')[0] || note).trim();
  if (derived) {
    process.stderr.write(`[shop-map] 新店铺 fallback: 「${note}」→「${derived}」（尚未在 SHOP_MAP 显式注册，请确认 ERP 店铺名后补充映射）\n`);
    return derived;
  }
  throw new Error(`账号「${note}」无法推导 ERP 店铺名，请在 lib/erp/shop-map.js 手动补充映射`);
}

module.exports = { getErpShop, SHOP_MAP };
