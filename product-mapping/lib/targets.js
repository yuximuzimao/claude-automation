'use strict';
const cdp = require('./cdp');

// 产品匹配项目锁定的 ERP 标签页 ID（两个 ERP tab 共存时避免串到售后项目）
const PINNED_ERP_ID = '1F46BAA92728117C35DD6845CB85FB33';

let cached = null;

async function getTargetIds(force) {
  if (cached && !force) return cached;
  const targets = await cdp.getTargets();

  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  if (!jl) throw new Error('鲸灵标签页未找到，请确认浏览器已打开对应页面');

  // 优先使用锁定的 ERP 标签页
  let erp = targets.find(t => t.targetId === PINNED_ERP_ID);
  if (!erp) {
    // fallback：按 URL 匹配
    erp = targets.find(t => t.url && t.url.includes('superboss.cc'));
  }
  if (!erp) throw new Error('ERP标签页未找到，请确认浏览器已打开对应页面');

  cached = { jlId: jl.targetId, erpId: erp.targetId };
  return cached;
}

module.exports = { getTargetIds };
