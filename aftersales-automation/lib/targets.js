'use strict';
const cdp = require('./cdp');

let cached = null;

async function getTargetIds(force) {
  if (cached && !force) return cached;
  const targets = await cdp.getTargets();
  const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
  // 支持 ERP_TAB_ID 环境变量指定 ERP 标签页（多标签页时避免选错）
  let erp;
  if (process.env.ERP_TAB_ID) {
    erp = targets.find(t => t.id === process.env.ERP_TAB_ID);
    if (!erp) throw new Error(`指定的ERP标签页 ${process.env.ERP_TAB_ID} 未找到`);
  } else {
    erp = targets.find(t => t.url && t.url.includes('superboss.cc'));
  }
  if (!jl) throw new Error('鲸灵标签页未找到，请确认浏览器已打开对应页面');
  if (!erp) throw new Error('ERP标签页未找到，请确认浏览器已打开对应页面');
  cached = { jlId: jl.id, erpId: erp.id };
  return cached;
}

module.exports = { getTargetIds };
