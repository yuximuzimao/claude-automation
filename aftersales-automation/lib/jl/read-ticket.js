'use strict';
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { ok, fail } = require('../result');
const { waitFor } = require('../wait');

// 递归读取 Vue orderInfo 的 JS（固定字符串，不动态生成）
// 从 DOM innerText 补充读取 Vue orderInfo 中缺失的字段
const READ_ORDER_INFO_JS = `(function(){
  function findDeep(vm, depth) {
    if (depth > 10 || !vm) return null;
    if (vm.$data && vm.$data.orderInfo) return vm.$data.orderInfo;
    for (var i = 0; i < (vm.$children || []).length; i++) {
      var r = findDeep(vm.$children[i], depth + 1);
      if (r) return r;
    }
    return null;
  }
  var info = findDeep(document.querySelector('#app').__vue__, 0);
  if (!info) return JSON.stringify({error:'orderInfo not found'});

  var bodyText = document.body.innerText;

  // 退货物流单号 + 多次使用检测（页面直接显示可见文本，非 tooltip）
  var rtMatch = bodyText.match(/退货物流单号[：:]\\s*([A-Za-z0-9]+)/);
  var returnTracking = rtMatch ? rtMatch[1] : '';
  var returnTrackingMultiUse = false;
  var returnTrackingUsedBy = [];
  if (returnTracking && bodyText.indexOf('多次使用') !== -1) {
    returnTrackingMultiUse = true;
    // 提取"多次使用"附近区域内的工单号（平台展示的关联工单，16-22位长数字）
    var muIdx = bodyText.indexOf('多次使用');
    var muSection = bodyText.substring(Math.max(0, muIdx - 100), muIdx + 600);
    var muNums = muSection.match(/1\\d{16,21}/g) || [];
    returnTrackingUsedBy = muNums;
  }

  // 售后说明（buyerRemark）：Vue 优先，DOM 补充
  var remarkMatch = bodyText.match(/售后说明[：:]\\s*([^\\n]+)/);
  var domRemark = remarkMatch ? remarkMatch[1].trim() : '';
  var buyerRemark = info.buyerRemark || domRemark || '';

  // 售后原因：Vue 多字段名尝试，DOM 补充
  var afterSaleReason = info.applyReasonDesc || info.reasonDesc || info.refundReason || info.applyReason || '';
  if (!afterSaleReason) {
    var rsnMatch = bodyText.match(/(?:退款原因|申请原因|售后原因)[：:]\\s*([^\\n]+)/);
    if (rsnMatch) afterSaleReason = rsnMatch[1].trim();
  }

  // 售后金额：Vue 多字段名尝试，DOM 补充
  var amount = info.refundAmount || info.applyAmount || info.amount || 0;
  if (!amount) {
    var amtMatch = bodyText.match(/(?:退款金额|售后金额|申请金额)[：:]\\s*[¥￥]?([\\d.]+)/);
    if (amtMatch) amount = parseFloat(amtMatch[1]) || 0;
  }

  // 支付金额
  var payAmount = info.payAmount || info.orderAmount || 0;

  // 售后标签：Vue 数组或 DOM 解析
  var tags = [];
  var rawTags = info.labelList || info.labels || info.tagList || [];
  if (rawTags.length) {
    tags = rawTags.map(function(t){ return t.labelName || t.name || String(t); });
  }
  if (!tags.length) {
    var tagMatch = bodyText.match(/标签[：:]\\s*([^\\n]+)/);
    if (tagMatch) tags = tagMatch[1].split(/[,，、\\s]+/).filter(Boolean);
  }

  // 售后图片数量：精准定位"售后图片"模块，排除商品缩略图和标签图
  var imageCount = 0;
  (function(){
    var allContainers = document.querySelectorAll('.detail-module_mb10, .el-container.detail-module_mb10');
    for (var ci = 0; ci < allContainers.length; ci++) {
      var ct = allContainers[ci];
      var titleEl = ct.querySelector('.detail-module_title, [class*="detail-module_title"]');
      var titleText = titleEl ? titleEl.innerText : '';
      if (titleText.indexOf('售后图片') === -1) continue;
      // 在此容器内只数买家上传的图（排除 CDN 静态图标，如上传按钮）
      var imgs = ct.querySelectorAll('img');
      for (var ii = 0; ii < imgs.length; ii++) {
        var src = imgs[ii].src || '';
        // 排除静态 CDN 图标（上传按钮等）
        if (src.indexOf('cdn.jlsupp.com/static/') !== -1) continue;
        if (src.indexOf('data:image') !== -1) continue;
        if (!src) continue;
        imageCount++;
      }
      break; // 找到售后图片区域后不继续扫
    }
  })();

  // 历史售后次数：Vue 多字段名尝试，DOM 补充
  var afterSaleCount = info.afterSaleCount || info.buyerAfterSaleCount || info.historyAfterSaleCount || 0;
  if (!afterSaleCount) {
    var countMatch = bodyText.match(/历史售后[：:\\s]*(\\d+)\\s*次/) ||
                     bodyText.match(/售后次数[：:\\s]*(\\d+)/) ||
                     bodyText.match(/已售后\\s*(\\d+)\\s*次/);
    if (countMatch) afterSaleCount = parseInt(countMatch[1]) || 0;
  }

  // 工单状态（Vue 字段常为空，从 body text 补充提取）
  var workOrderStatus = info.workOrderStatus || info.orderStatus || '';
  if (!workOrderStatus) {
    var wsMatch = bodyText.match(/工单状态[：:]\\s*([^\\n]+)/);
    if (wsMatch) workOrderStatus = wsMatch[1].trim();
  }

  return JSON.stringify({
    subOrders: (info.subBizOrderDetailDTO || []).map(function(s){
      return {
        id: s.subBizOrderId,
        sku: s.spuBarcode,
        attr1: s.attribute1,
        logistics: s.logisticsStatusDesc,
        afterSaleNum: s.afterSaleNum
      };
    }),
    gifts: (info.giftSubBizOrderDetailDTO || []).map(function(g){
      return { id: g.subBizOrderId, sku: g.spuBarcode, attr1: g.attribute1 };
    }),
    mainOrderId: info.bizOrderId,
    subBizType: info.subBizType,
    workOrderType: info.workOrderType,
    workOrderStatus: workOrderStatus || undefined,
    returnTracking: returnTracking,
    returnTrackingMultiUse: returnTrackingMultiUse || undefined,
    returnTrackingUsedBy: returnTrackingUsedBy.length ? returnTrackingUsedBy : undefined,
    buyerRemark: buyerRemark,
    afterSaleReason: afterSaleReason,
    amount: amount || undefined,
    payAmount: payAmount || undefined,
    tags: tags.length ? tags : undefined,
    imageCount: imageCount || undefined,
    afterSaleCount: afterSaleCount || undefined
  });
})()`;

async function readTicket(targetId, workOrderNum) {
  try {
    await navigate(targetId, '/business/after-sale-detail', { workOrderNum });

    // ── 核验页面是否加载了对应工单（区分账号错误 vs 页面慢）────────
    const verifyJS = `(function(){
      var t = document.body.innerText || '';
      if (!t.includes('${workOrderNum}')) return 'notfound';
      if (t.includes('售后工单信息') || t.includes('售后类型') || t.includes('售后原因')) return 'ok';
      return 'loading';
    })()`;
    // 最多等 4s 确认工单号出现在页面上
    let pageOk = false;
    for (let i = 0; i < 5; i++) {
      await new Promise(r => setTimeout(r, 800));
      try {
        const v = await cdp.eval(targetId, verifyJS);
        if (v === 'ok') { pageOk = true; break; }
        if (v === 'notfound' && i >= 2) {
          return fail(`工单 ${workOrderNum} 页面未找到，账号可能未切换到对应店铺`);
        }
      } catch { /* ignore */ }
    }

    // 等待 API 数据加载完成（mainOrderId 有值才算就绪）
    // try/catch：页面未就绪时 eval 可能抛出（如 #app.__vue__ 为 null），捕获后继续轮询
    const data = await waitFor(
      async () => {
        try {
          const raw = await cdp.eval(targetId, READ_ORDER_INFO_JS);
          if (raw.error) return null;
          if (!raw.mainOrderId) return null;
          return raw;
        } catch {
          return null;
        }
      },
      { timeoutMs: 12000, intervalMs: 800, label: `read-ticket ${workOrderNum}` }
    );
    // 过滤掉当前工单号本身（页面上的工单号会被误匹配为"已关联工单"）
    if (data.returnTrackingUsedBy) {
      data.returnTrackingUsedBy = data.returnTrackingUsedBy.filter(n => n !== workOrderNum);
      if (!data.returnTrackingUsedBy.length) {
        delete data.returnTrackingUsedBy;
        delete data.returnTrackingMultiUse;
      }
    }
    return ok(data);
  } catch (e) {
    return fail(e);
  }
}

module.exports = { readTicket };
