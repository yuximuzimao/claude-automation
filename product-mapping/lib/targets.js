'use strict';
const cdp = require('./cdp');

let cached = null;

async function getTargetIds(force) {
  if (cached && !force) return cached;
  const targets = await cdp.getTargets();
  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  const erp = targets.find(t => t.url && t.url.includes('superboss.cc'));
  if (!jl) throw new Error('鲸灵标签页未找到，请确认浏览器已打开对应页面');
  if (!erp) throw new Error('ERP标签页未找到，请确认浏览器已打开对应页面');
  cached = { jlId: jl.targetId, erpId: erp.targetId };
  return cached;
}

module.exports = { getTargetIds };
