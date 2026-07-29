'use strict';
/**
 * infer.js - 规则推理引擎（只查信息，不执行操作）
 *
 * 架构说明：
 *   inferDecision(sim, queueItem)  — 主入口：校验 + 路由
 *   inferRefundOnly(ctx)           — flow-5.2/5.3 仅退款（独立函数）
 *   inferRefundReturn(ctx)         — flow-5.1 退货退款（独立函数）
 *
 * 数据合约见 docs/collect-schema.md。
 * 变更任一读取字段必须同步更新该文档。
 */

const { hasConfirmedReturn, SIGNED_KEYWORDS, YIZHAN_KEYWORDS, EXEMPT_ACCESSORY_KEYWORDS, NON_MERCHANT_REASONS, MERCHANT_FAULT_REASONS, REMIND_HOURS, SAFETY_MARGIN_HOURS } = require('./constants');
const { proveReturnItems } = require('./return-item-proof');

// 解析 urgency 字符串（如 "1天3小时" / "3小时"）为总小时数
function parseUrgencyHours(urgency) {
  if (!urgency) return null;
  const dayMatch = urgency.match(/(\d+)天/);
  const hourMatch = urgency.match(/(\d+)小时/);
  return ((dayMatch ? parseInt(dayMatch[1]) : 0) * 24) + (hourMatch ? parseInt(hourMatch[1]) : 0);
}

// 判断是否有包裹签收超过指定天数（从物流文本解析签收时间）
// 返回 { overdue: boolean, days: number, signedAt: string|null }
function checkSignedOverDays(cd, days) {
  const packages = (cd.logistics && cd.logistics.packages) || [];
  const signRegex = /签收\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})/;

  for (const pkg of packages) {
    const m = (pkg.text || '').match(signRegex);
    if (!m) continue;
    const signedAt = new Date(m[1]);
    if (isNaN(signedAt.getTime())) continue;
    const diffDays = (Date.now() - signedAt.getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays > days) {
      return { overdue: true, days: Math.floor(diffDays), signedAt: m[1] };
    }
  }
  return { overdue: false, days: 0, signedAt: null };
}

// 返回所有 ERP 行数据（见 docs/collect-schema.md）
function getErpRows(cd, field) {
  // 主品 ERP：优先合并 erpSearches（所有子订单），fallback 到 erpSearch（向后兼容）
  if (field === 'erpSearch' && cd.erpSearches && cd.erpSearches.length > 0) {
    return cd.erpSearches.flatMap(s => (s.rows && s.rows.rows) || []);
  }
  // 赠品 ERP：优先合并 giftErpSearches（所有赠品子订单），fallback 到 giftErpSearch
  if (field === 'giftErpSearch' && cd.giftErpSearches && cd.giftErpSearches.length > 0) {
    return cd.giftErpSearches.flatMap(s => (s.rows && s.rows.rows) || []);
  }
  return (cd[field] && cd[field].rows && cd[field].rows.rows) || [];
}

function getRowTrackings(row) {
  const trackings = [
    ...((row && Array.isArray(row.trackings)) ? row.trackings : []),
    row && row.tracking,
  ];
  return [...new Set(trackings.filter(Boolean))];
}

function getPackageTracking(pkg) {
  const match = ((pkg && pkg.text) || '').match(/物流单号[：:]\s*\n?(\S+)/);
  return match ? match[1] : null;
}

const NOT_PICKED_UP_KEYWORDS = ['未揽收', '等待揽收', '尚未揽收'];
const ACTUAL_SHIPMENT_RE = /揽收|在途|派件|签收|入站|到达|离开|运输/;

function evaluateRefundOnlyTrackings(cd, rows) {
  const trackings = [...new Set(rows.flatMap(getRowTrackings))];
  const erpResults = cd.erpLogistics && Array.isArray(cd.erpLogistics.results)
    ? cd.erpLogistics.results
    : (cd.erpLogistics && cd.erpLogistics.logisticsText ? [cd.erpLogistics] : []);
  const packages = (cd.logistics && cd.logistics.packages) || [];
  const packageTrackings = packages.map(getPackageTracking).filter(Boolean);
  const missingFromErpRows = packageTrackings.filter(tracking => !trackings.includes(tracking));

  const outcomes = trackings.map(tracking => {
    const texts = [
      ...erpResults.filter(result => result.tracking === tracking).map(result => result.logisticsText || ''),
      ...packages.filter(pkg => getPackageTracking(pkg) === tracking).map(pkg => pkg.text || ''),
    ].filter(Boolean);
    const hasReturn = texts.some(hasConfirmedReturn);
    if (hasReturn) return { tracking, outcome: 'returned' };

    const hasNotPickedUp = texts.some(text => NOT_PICKED_UP_KEYWORDS.some(keyword => text.includes(keyword)));
    const hasActualShipment = texts.some(text => {
      let withoutNotPickedUp = text;
      NOT_PICKED_UP_KEYWORDS.forEach(keyword => {
        withoutNotPickedUp = withoutNotPickedUp.split(keyword).join('');
      });
      return ACTUAL_SHIPMENT_RE.test(withoutNotPickedUp);
    });
    if (hasActualShipment) return { tracking, outcome: 'shipped' };
    if (hasNotPickedUp) return { tracking, outcome: 'not_picked_up' };
    return { tracking, outcome: 'unknown' };
  });

  return { trackings, outcomes, missingFromErpRows };
}

// 聚合所有行的发货状态，替代只读第一行的 getErpStatus()
// 已发货状态：卖家已发货 / 交易成功 / 交易关闭（订单已关闭但曾是发货状态）
// 无快递单号时可确认未发货的状态：待审核 / 待打印快递单 / 待发货
function getAggregatedErpStatus(cd, field) {
  const rows = getErpRows(cd, field);
  if (!rows.length) return { raw: null, statuses: [], hasShipped: false, allNotShipped: false, hasTracking: false };
  const statuses = [...new Set(rows.map(r => r.status).filter(Boolean))];
  const SHIPPED = ['卖家已发货', '交易成功', '交易关闭'];
  const NOT_SHIPPED = ['待审核', '待打印快递单', '待发货'];
  return {
    raw: rows[0].status || null,
    statuses,
    hasShipped: statuses.some(s => SHIPPED.includes(s)),
    allNotShipped: statuses.length > 0 && statuses.every(s => NOT_SHIPPED.includes(s)),
    hasTracking: rows.some(r => !!(r.tracking || (r.trackings && r.trackings.length))),
  };
}

// 检查所有包裹是否都有退回物流节点
function allPackagesReturned(packages) {
  if (!packages || !packages.length) return false;
  return packages.every(pkg => hasConfirmedReturn(pkg.text));
}

// 检查是否有包裹已被买家签收（且无退回节点）
function anyPackageSignedByBuyer(packages) {
  if (!packages || !packages.length) return false;
  return packages.some(pkg => {
    const text = pkg.text || '';
    const hasReturn = hasConfirmedReturn(text);
    const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
    return hasSigned && !hasReturn;
  });
}

function approve(reason, rulesApplied) {
  return { action: 'approve', reason, confidence: 'high', rulesApplied: rulesApplied || [], warnings: [] };
}

function reject(reason, warnings, rulesApplied) {
  return { action: 'reject', reason, confidence: 'high', warnings: warnings || [], rulesApplied: rulesApplied || [] };
}

const INTERCEPT_REJECT_REASON_TRANSIT = '已通知快递拦截暂未退回';
const INTERCEPT_REJECT_REASON_STATION = '已到驿站待取件';
const INTERCEPT_REJECT_DETAIL = '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款';

function withInterceptRejectCopy(decision, rejectReason) {
  return {
    ...decision,
    rejectReason,
    rejectDetail: INTERCEPT_REJECT_DETAIL,
  };
}

// 有拦截记录时不创建重复拦截提醒
function interceptWarnings(cd) {
  return cd.intercepted ? [] : ['需创建快递拦截提醒'];
}

function escalate(reason, extra) {
  return { action: 'escalate', reason, confidence: 'low', rulesApplied: [], warnings: [], ...extra };
}

function summarizeReceivedReturnItems(cd) {
  const grouped = new Map();
  const receivedRows = (cd.erpAftersale?.rows || []).filter(row =>
    String(row?.goodsStatus || '').includes('卖家已收到退货')
  );
  for (const row of receivedRows) {
    for (const item of row.items || []) {
      const name = String(item?.name || item?.specCode || '未知商品').trim();
      const current = grouped.get(name) || { qtyGood: 0, qtyBad: 0 };
      current.qtyGood += Number(item?.qtyGood) || 0;
      current.qtyBad += Number(item?.qtyBad) || 0;
      grouped.set(name, current);
    }
  }
  if (!grouped.size) return '尚未取得已收货商品明细';
  return [...grouped.entries()].map(([name, qty]) => {
    const parts = [];
    if (qty.qtyGood) parts.push(`良品${qty.qtyGood}件`);
    if (qty.qtyBad) parts.push(`次品${qty.qtyBad}件`);
    return `${name}（${parts.join('、') || '数量为0'}）`;
  }).join('、');
}

function inferManualReturnReview({ cd, ticket, queueItem, s, fin, isMerchantFault }) {
  const type = queueItem.type;
  const isExchange = type === '换货';
  const reviewTitle = isMerchantFault
    ? (isExchange ? '商责换货' : '商责退货退款')
    : '换货';
  const recommendedActionLabel = isExchange ? '同意换货' : '同意退款';
  const merchantReasonText = isMerchantFault
    ? `，售后原因「${ticket.afterSaleReason || '未知'}」`
    : '';
  const manualReasons = [
    ...(isMerchantFault ? ['商责'] : []),
    ...(isExchange ? ['换货'] : []),
  ];

  s({ type: 'read', label: '人工确认类型', value: reviewTitle });
  s({ type: 'read', label: '退货快递单号', value: ticket.returnTracking || '无' });

  if (!ticket.returnTracking) {
    s({ type: 'branch', text: `${reviewTitle}无退货单号，无法核验退回商品 → 人工处理` });
    return fin(escalate(`【${reviewTitle}｜人工确认】无退货单号${merchantReasonText}，无法核验客户实际退回商品，请人工处理`, {
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: false,
      manualReviewKind: isMerchantFault
        ? (isExchange ? 'merchant_exchange_no_tracking' : 'merchant_refund_return_no_tracking')
        : 'exchange_no_tracking',
      manualReviewReasons: manualReasons,
      rulesApplied: [{
        doc: isExchange ? 'flow-5.4' : 'INDEX.md',
        section: '人工确认',
        summary: `${reviewTitle}无退货单号→人工处理`,
      }],
      warnings: [`⚠️ ${reviewTitle}缺少退货核验依据，请人工打开工单确认后处理`],
    }));
  }

  const proof = proveReturnItems(cd);
  const receivedSummary = summarizeReceivedReturnItems(cd);
  const outcomeLabels = {
    exact: '规格、数量及良次品核对一致',
    excess: '存在多退商品',
    short: '存在少退商品',
    damaged: '退回商品含次品',
    unmatched: '退回商品规格与订单不符',
    incomplete: `核验依据不完整：${(proof.missingFacts || []).join('；') || '未知缺失项'}`,
  };
  const outcomeLabel = outcomeLabels[proof.outcome] || `核验结果未知（${proof.outcome || 'unknown'}）`;
  s({ type: 'read', label: '仓库实际退回', value: receivedSummary });
  s({ type: 'check', condition: '退回商品严格核验', result: outcomeLabel });

  if (proof.outcome === 'exact') {
    const manualReviewKind = isMerchantFault
      ? (isExchange ? 'merchant_exchange_return_exact' : 'merchant_refund_return_exact')
      : 'exchange_return_exact';
    const summary = isMerchantFault
      ? (isExchange
        ? '商责换货退回核验通过→推荐人工同意换货'
        : '商责退货退款核验通过→推荐人工同意退款')
      : '换货退回核验通过→推荐人工同意换货';
    const consequence = isExchange
      ? '同意后会生成新的发货单；还必须确认正确商品没有被提前人工补发'
      : '商责案件涉及责任及罚款风险';
    s({ type: 'branch', text: `退回商品核对无误 → 推荐人工确认后${recommendedActionLabel}，禁止无人自动执行` });
    return fin({
      action: 'approve',
      reason: `【${reviewTitle}｜推荐人工${recommendedActionLabel}】退回商品核对无误：${receivedSummary}${merchantReasonText}；${consequence}，请人工核对后再执行`,
      confidence: 'high',
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: true,
      manualReviewKind,
      manualReviewReasons: manualReasons,
      recommendedActionLabel,
      rulesApplied: [{
        doc: isExchange ? 'flow-5.4' : 'INDEX.md',
        section: '有退货单号',
        summary,
      }],
      warnings: [
        `⚠️ ${reviewTitle}禁止无人自动执行；人工核对无误后，可使用单笔或批量执行`,
        ...(isExchange ? [
          '⚠️ 请先确认正确商品是否已提前补发/换出：若已发出，应拒绝换货并手动归档；只有未提前发出时才执行同意换货',
          '同意换货将生成新的发货单，请确认退回商品无误',
        ] : []),
      ],
    });
  }

  const manualReviewKind = isMerchantFault
    ? (isExchange ? 'merchant_exchange_return_review' : 'merchant_refund_return_review')
    : 'exchange_return_review';
  s({ type: 'branch', text: `${outcomeLabel} → 不推荐直接同意，转人工确认` });
  return fin(escalate(`【${reviewTitle}｜人工确认】${outcomeLabel}；仓库实际退回：${receivedSummary}${merchantReasonText}，请人工核对后处理`, {
    confidence: proof.outcome === 'incomplete' ? 'low' : 'high',
    requiresHumanReview: true,
    autoExecutionBlocked: true,
    humanTriggeredExecutionAllowed: false,
    manualReviewKind,
    manualReviewReasons: manualReasons,
    rulesApplied: [{
      doc: isExchange ? 'flow-5.4' : 'INDEX.md',
      section: '有退货单号',
      summary: `${reviewTitle}退回核验异常→人工确认`,
    }],
    warnings: [`⚠️ ${reviewTitle}退回核验未通过，不能直接执行推荐同意；请人工确认实际处理动作`],
  }));
}

function isLiveScanItem(sim, queueItem) {
  return sim.mode === 'live' && queueItem.source === 'scan';
}

// hint 关键词 → 覆盖 action
function parseHintAction(hint) {
  if (!hint) return null;
  if (/同意|approve|退款|可退/.test(hint)) return 'approve';
  if (/拒绝|reject|不退|拒退/.test(hint)) return 'reject';
  if (/人工|escalate|上报|待确认/.test(hint)) return 'escalate';
  return null;
}

// ── 采集数据完整性校验 ─────────────────────────────────────────────
// 必填字段缺失时立即 escalate，禁止走 else 默认分支（防止无声失败）
// 见 docs/collect-schema.md
function validateCollectedData(cd, type) {
  if (!cd.ticket) return '采集数据缺失：ticket 未采集（read-ticket 失败）';
  if (type === '仅退款' && !cd.erpSearch && !cd.collectErrors.some(e => e.startsWith('erp-search:'))) {
    return '采集数据缺失：仅退款工单缺少 erpSearch 且无对应 collectError';
  }
  return null; // null = 通过
}

// ── flow-5.2/5.3 仅退款 ──────────────────────────────────────────
// 接收显式 ctx，不访问外层变量
// 见 docs/flow-5.2.md / docs/flow-5.3.md
function inferRefundOnly({ cd, ticket, queueItem, s, fin }) {
  const erpAgg = getAggregatedErpStatus(cd, 'erpSearch');
  const erpStatus = erpAgg.raw;
  const gifts = ticket.gifts || [];
  const giftAgg = gifts.length > 0 ? getAggregatedErpStatus(cd, 'giftErpSearch') : null;
  const mainRows = getErpRows(cd, 'erpSearch');
  const giftRows = getErpRows(cd, 'giftErpSearch');
  const allRows = [...mainRows, ...giftRows];
  s({ type: 'read', label: 'ERP主商品状态', value: erpAgg.statuses.length ? erpAgg.statuses.join('/') : '未获取' });

  if (!erpStatus && !erpAgg.statuses.length) {
    s({ type: 'branch', text: '上报 → ERP状态未获取' });
    return fin(escalate('未获取到ERP状态，需人工核查'));
  }

  if (gifts.length > 0 && giftRows.length === 0) {
    s({ type: 'branch', text: '上报 → 赠品ERP状态未获取' });
    return fin(escalate('赠品ERP状态未获取，需人工核查'));
  }

  const noTrackingStatuses = ['待审核', '待打印快递单', '待发货'];
  const abnormalNoTrackingRow = allRows.find(row =>
    getRowTrackings(row).length === 0 && !noTrackingStatuses.includes(row.status)
  );
  if (abnormalNoTrackingRow) {
    const status = abnormalNoTrackingRow.status || '未知';
    s({ type: 'branch', text: `上报 → ERP状态${status}但无快递单号，属于数据异常` });
    return fin(escalate(`ERP状态为「${status}」但无快递单号，数据异常，需人工核查`));
  }

  const trackingEvaluation = evaluateRefundOnlyTrackings(cd, allRows);
  if (trackingEvaluation.trackings.length > 0) {
    const outcomeLabels = {
      returned: '已退回',
      not_picked_up: '未揽收',
      shipped: '已发货未退回',
      unknown: '未知',
    };
    const outcomeDetails = trackingEvaluation.outcomes
      .map(item => `${item.tracking}：${outcomeLabels[item.outcome] || item.outcome}`)
      .join('；');
    s({
      type: 'read',
      label: '逐行物流核验',
      value: `单号${trackingEvaluation.trackings.length}个：${outcomeDetails}`,
    });

    if (trackingEvaluation.missingFromErpRows.length > 0) {
      s({ type: 'branch', text: '上报 → 鲸灵存在未包含在ERP行中的快递单号，采集不完整' });
      return fin(escalate('物流采集不完整：鲸灵存在ERP行中未采集到的快递单号，需人工核查'));
    }

    const hasUnknownTracking = trackingEvaluation.outcomes.some(item => item.outcome === 'unknown');
    const hasShippedTracking = trackingEvaluation.outcomes.some(item => item.outcome === 'shipped');
    if (hasUnknownTracking && !hasShippedTracking) {
      s({ type: 'branch', text: '上报 → 有快递单号但物流结果不明' });
      return fin(escalate('有快递单号但未读取到明确物流结果，需人工核查'));
    }

    const allTrackingSafe = trackingEvaluation.outcomes.every(item =>
      item.outcome === 'returned' || item.outcome === 'not_picked_up'
    );
    if (allTrackingSafe) {
      s({ type: 'branch', text: '同意退款 → 所有ERP行均未发货或物流已退回' });
      return fin(approve(
        '主商品和赠品全部ERP行均未发货或物流已退回',
        [{ doc: 'flow-5.2', section: 'Step4', summary: '全部ERP行逐行核验通过→同意退款' }]
      ));
    }
  }

  // 5.2：未发货
  // 待审核 / 待打印快递单 / 待发货：所有行都无快递单号时可退款
  const isNotShipped = erpAgg.allNotShipped && trackingEvaluation.trackings.length === 0;
  s({ type: 'check', condition: `所有ERP行 ∈ [待审核, 待打印快递单, 待发货] 且全部无快递单号`, result: isNotShipped });

  if (isNotShipped) {
    s({ type: 'branch', text: '进入「仅退款-未发货」流程 (flow-5.2)' });
    s({ type: 'read', label: '赠品数量', value: `${gifts.length} 件` });

    if (gifts.length > 0) {
      const giftErpStatus = giftAgg.raw;
      s({ type: 'read', label: 'ERP赠品状态', value: giftAgg.statuses.length ? giftAgg.statuses.join('/') : '未获取' });

      if (!giftErpStatus && !giftAgg.statuses.length) {
        s({ type: 'branch', text: '上报 → 赠品ERP状态未获取' });
        return fin(escalate('赠品ERP状态未获取，需人工核查'));
      }
      const giftOk = giftAgg.allNotShipped;
      s({ type: 'check', condition: `赠品所有ERP行 ∈ [待审核, 待打印快递单, 待发货]（全部未发货）`, result: giftOk });

      if (!giftOk && giftAgg.hasShipped) {
        // 赠品有已发货行 → 读 ERP 物流判断是否可等待（与 flow-5.3 赠品逻辑一致）
        const erpLogResults = cd.erpLogistics && cd.erpLogistics.results
          ? cd.erpLogistics.results
          : (cd.erpLogistics && cd.erpLogistics.logisticsText ? [cd.erpLogistics] : []);
        const giftShippedRows52 = getErpRows(cd, 'giftErpSearch').filter(r =>
          ['卖家已发货', '交易成功', '交易关闭'].includes(r.status)
        );
        const giftTrackings52 = giftShippedRows52.flatMap(r => r.trackings || (r.tracking ? [r.tracking] : []));
        s({ type: 'read', label: '赠品已发货快递单号', value: giftTrackings52.join('/') || '无' });

        // 无快递单号的已发货行 → 无法判断物流，人工
        if (!giftTrackings52.length) {
          s({ type: 'branch', text: `上报 → 赠品已发货（${giftAgg.statuses.join('/')}）但无快递单号，需人工核查` });
          return fin(escalate(`赠品已发货（${giftAgg.statuses.join('/')}）但无快递单号，需人工核查`, {
            rulesApplied: [{ doc: 'flow-5.2', section: 'Step4c', summary: '赠品已发货无单号→上报人工' }],
          }));
        }

        const giftStatuses52 = giftTrackings52.map(tr => {
          const erpEntry = erpLogResults.find(r => r.tracking === tr);
          if (erpEntry && erpEntry.logisticsText) {
            const text = erpEntry.logisticsText;
            if (hasConfirmedReturn(text)) return { tr, status: 'returned', label: `${tr}（已退回）` };
            if (SIGNED_KEYWORDS.some(kw => text.includes(kw))) return { tr, status: 'signed', label: `${tr}（已签收）` };
            if (YIZHAN_KEYWORDS.some(kw => text.includes(kw))) return { tr, status: 'yizhan', label: `${tr}（驿站待取件）` };
            return { tr, status: 'transit', label: `${tr}（在途）` };
          }
          // 有快递单号但无物流记录 = 刚揽收/暂无信息 → 按在途处理
          return { tr, status: 'transit', label: `${tr}（暂无物流信息，在途）` };
        });
        s({ type: 'read', label: '赠品物流状态', value: giftStatuses52.map(p => p.label).join('；') });

        const giftAllReturned52 = giftStatuses52.every(p => p.status === 'returned');
        s({ type: 'check', condition: '赠品快递全部已退回', result: giftAllReturned52 });

        if (!giftAllReturned52) {
          const giftAnySigned52 = giftStatuses52.some(p => p.status === 'signed');
          const giftAnyYizhan52 = giftStatuses52.some(p => p.status === 'yizhan');
          if (giftAnySigned52 || giftAnyYizhan52) {
            // 已签收/驿站 → 无法自动等待，上报人工
            const desc = `主商品未发货，赠品${giftStatuses52.map(p => p.label).join('；')}，需人工处理赠品退回`;
            s({ type: 'branch', text: `上报 → ${desc}` });
            return fin(escalate(desc, {
              rulesApplied: [{ doc: 'flow-5.2', section: 'Step4c', summary: '赠品已签收/驿站→上报人工' }],
            }));
          }
          // 在途 → 等待重查（主商品可先不退款，等赠品退回后一起处理）
          const giftDesc = `赠品${giftStatuses52.map(p => p.label).join('；')}`;
          s({ type: 'branch', text: `等待重查 → 主商品未发货，${giftDesc}，等快递退回后再同意退款` });
          return fin(withInterceptRejectCopy({
            action: 'reject',
            waitingRescan: true,
            manualExecutionAllowedWhileWaiting: true,
            reasonCode: 'INTERCEPT_WAITING',
            reason: `主商品未发货，${giftDesc}，赠品拦截尚未退回，当前等待重查；人工可提前沿用该工单原拒绝原因执行拒绝`,
            confidence: 'medium',
            rulesApplied: [{ doc: 'flow-5.2', section: 'Step4c', summary: '赠品在途→等待重查，可人工提前拒绝' }],
            warnings: interceptWarnings(cd),
          }, INTERCEPT_REJECT_REASON_TRANSIT));
        }
        // 赠品全退回 → 继续走主商品未发货 → approve
        s({ type: 'branch', text: '赠品全部已退回 → 继续走主商品未发货→同意退款' });
      }

      if (!giftOk && !giftAgg.hasShipped) {
        s({ type: 'branch', text: `上报 → 赠品ERP状态异常: ${giftAgg.statuses.join('/')}` });
        return fin(escalate(`赠品ERP状态异常: ${giftAgg.statuses.join('/')}，需人工核查`));
      }

    }

    s({ type: 'branch', text: `同意退款 → 主商品${gifts.length ? '+赠品' : ''}均未发货（无快递单号）` });
    return fin(approve(
      `主商品${gifts.length ? '+赠品' : ''}均未发货（无快递单号）`,
      [{ doc: 'flow-5.2', section: 'Step4', summary: '主商品+赠品未发货→同意退款' }]
    ));
  }

  // 5.3：任意主品或赠品单号已有实际发货节点 → 进入现有已发货处理流程
  const isShipped = trackingEvaluation.outcomes.some(item => item.outcome === 'shipped');
  s({ type: 'check', condition: `主品或赠品任意快递单已有实际发货节点`, result: isShipped });

  if (isShipped) {
    s({ type: 'branch', text: '进入「仅退款-已发货」流程 (flow-5.3)' });
    const shippedFlowTrackings = new Set(
      trackingEvaluation.outcomes
        .filter(item => item.outcome !== 'not_picked_up')
        .map(item => item.tracking)
    );

    // 已拦截记录仅影响输出文案和快递行动，不影响物流验证流程
    if (cd.intercepted) {
      const it = cd.intercepted;
      s({ type: 'read', label: '拦截记录', value: `快递 ${it.tracking} 已拦截（首次工单 ${it.workOrderNum}，${it.executedAt ? it.executedAt.slice(0, 10) : '未知时间'}）` });
    }

    const packages = cd.logistics && cd.logistics.packages
      ? cd.logistics.packages.filter(pkg => {
        const tracking = getPackageTracking(pkg);
        return !tracking || shippedFlowTrackings.has(tracking);
      })
      : null;
    const packageTrackings = packages ? packages.map(getPackageTracking).filter(Boolean) : [];
    s({
      type: 'read',
      label: '鲸灵物流包裹',
      value: packages ? `${packages.length}个：${packageTrackings.join('、') || '单号未识别'}` : '未获取',
    });

    // ERP双源：同时检查 ERP 物流文本（鲸灵有时不更新退回状态）
    // erpLogistics 格式：{ results: [{ tracking, logisticsText }, ...] }（多行）或旧格式 { logisticsText }（单行兼容）
    const allErpLogResults = cd.erpLogistics && cd.erpLogistics.results
      ? cd.erpLogistics.results
      : (cd.erpLogistics && cd.erpLogistics.logisticsText ? [cd.erpLogistics] : []);
    const erpLogResults = allErpLogResults.filter(result =>
      !result.tracking || shippedFlowTrackings.has(result.tracking)
    );
    // 修正：所有有物流信息的行都必须有退回关键词才算全部退回（之前 .some() 导致部分退回误判为全部退回）
    const erpLogsWithText = erpLogResults.filter(r => r.logisticsText);
    const erpReturned = erpLogsWithText.length > 0 && erpLogsWithText.every(r => hasConfirmedReturn(r.logisticsText));
    // 逐运单物流状态（替代原来的 tracking 列表 + '?'）
    const erpTrackingStatuses = erpLogResults.filter(r => r.tracking).map(r => {
      const text = r.logisticsText || '';
      const hasReturn = hasConfirmedReturn(text);
      const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
      const status = hasReturn ? '已退回' : hasSigned ? '已签收' : '在途';
      return `${r.tracking}：${status}`;
    });
    s({ type: 'read', label: '各运单物流状态', value: erpTrackingStatuses.length ? erpTrackingStatuses.join('；') : '未采集' });

    if (!packages || !packages.length) {
      if (erpReturned && !trackingEvaluation.outcomes.some(item => item.outcome === 'unknown')) {
        s({ type: 'branch', text: '同意退款 → 鲸灵物流未读到，但ERP物流显示已退回' });
        return fin(approve(
          '物流显示已退回',
          [{ doc: 'flow-5.3', section: 'Step3', summary: 'ERP双源核查→已退回→同意退款' }]
        ));
      }
      // 鲸灵物流未读到，但 ERP 有物流数据 → 按 ERP 物流状态决策
      if (erpLogsWithText.length > 0) {
        const anySigned = erpLogsWithText.some(r => SIGNED_KEYWORDS.some(kw => r.logisticsText.includes(kw)));
        const anyYizhan = erpLogsWithText.some(r => YIZHAN_KEYWORDS.some(kw => r.logisticsText.includes(kw)));
        const erpDesc = erpTrackingStatuses.join('；');
        if (anySigned || anyYizhan) {
          s({ type: 'branch', text: `上报 → 鲸灵物流未读到，ERP显示已签收/驿站：${erpDesc}` });
          return fin(escalate(`鲸灵物流未读到，ERP显示${erpDesc}，需人工确认`));
        }
        // 在途 → 等待重查
        s({ type: 'branch', text: `等待重查 → 鲸灵物流未读到，ERP显示在途：${erpDesc}` });
        return fin(withInterceptRejectCopy({
          action: 'reject',
          waitingRescan: true,
          manualExecutionAllowedWhileWaiting: true,
          reasonCode: 'INTERCEPT_WAITING',
          reason: `鲸灵物流未读到，ERP显示${erpDesc}，拦截尚未退回，当前等待重查；人工可提前沿用该工单原拒绝原因执行拒绝`,
          rulesApplied: [{ doc: 'flow-5.3', section: 'Step3', summary: 'ERP在途→等待重查，可人工提前拒绝' }],
          warnings: interceptWarnings(cd),
        }, INTERCEPT_REJECT_REASON_TRANSIT));
      }
      s({ type: 'branch', text: '上报 → 已发货但无法读取物流信息' });
      return fin(escalate('已发货但无法读取物流信息'));
    }

    const pkgSummary = packages.map(p => {
      const text = p.text || '';
      const hasRet = hasConfirmedReturn(text);
      const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
      const numMatch = text.match(/物流单号[：:]\s*\n?(\S+)/);
      const num = numMatch ? numMatch[1] : (p.tab || '?');
      return `${num}：${hasRet ? '已退回' : hasSigned ? '已签收' : '在途'}`;
    }).join('；');
    s({ type: 'read', label: '各包裹物流状态', value: pkgSummary });

    // 交叉核查：合并 ERP 全部 tracking（主品+赠品）+ 鲸灵全部包裹 tracking → 去重
    // 鲸灵工单详情页不显示赠品物流，因此必须从 ERP 补充赠品 tracking
    const mainShippedRows = getErpRows(cd, 'erpSearch').filter(r =>
      getRowTrackings(r).some(tracking => shippedFlowTrackings.has(tracking))
    );
    const giftShippedRows = getErpRows(cd, 'giftErpSearch').filter(r =>
      getRowTrackings(r).some(tracking => shippedFlowTrackings.has(tracking))
    );
    const totalShipRows = mainShippedRows.length + giftShippedRows.length;
    const mainRowTrackings = [...new Set(mainShippedRows.flatMap(getRowTrackings))];
    const giftRowTrackings = [...new Set(giftShippedRows.flatMap(getRowTrackings))];
    s({
      type: 'read',
      label: 'ERP发货行及单号',
      value: `${totalShipRows}行（主品${mainShippedRows.length}行：${mainRowTrackings.join('、') || '无单号'}；赠品${giftShippedRows.length}行：${giftRowTrackings.join('、') || '无单号'}）`,
    });

    // 提取所有已知 tracking：ERP主品 + ERP赠品 + 鲸灵物流包裹
    const erpTrackings = [...mainShippedRows, ...giftShippedRows]
      .flatMap(getRowTrackings)
      .filter(tracking => shippedFlowTrackings.has(tracking));
    const jlTrackings = (packages || []).map(p => {
      const m = (p.text || '').match(/物流单号：\n(\S+)/);
      return m ? m[1] : null;
    }).filter(Boolean);
    const allTrackings = [...new Set([...erpTrackings, ...jlTrackings])];
    s({
      type: 'read',
      label: '合并去重单号',
      value: `ERP：${[...new Set(erpTrackings)].join('、') || '无'}；鲸灵：${[...new Set(jlTrackings)].join('、') || '无'}；去重后${allTrackings.length}个：${allTrackings.join('、') || '无'}`,
    });

    // 采集完整性：鲸灵读到的每个 tracking 必须都能在 ERP 结果里找到
    // ERP 是权威发货记录，鲸灵是物流读取。若鲸灵有 tracking 不在 ERP → ERP 采集遗漏了该发货行
    const allShippedRows = [...mainShippedRows, ...giftShippedRows];
    const noTrackingRows = allShippedRows.filter(r => !r.tracking && (!r.trackings || r.trackings.length === 0));
    const erpUniqueTrackings = new Set(erpTrackings);
    const jlOnlyTrackings = jlTrackings.filter(tr => !erpUniqueTrackings.has(tr));
    const collectionComplete = jlOnlyTrackings.length === 0;
    s({
      type: 'check',
      condition: `物流采集完整（ERP单号：${[...erpUniqueTrackings].join('、') || '无'}；鲸灵单号：${[...new Set(jlTrackings)].join('、') || '无'}；ERP无单号行${noTrackingRows.length}行；鲸灵仅有单号：${jlOnlyTrackings.join('、') || '无'}）`,
      result: collectionComplete,
    });

    const allJLReturned = allPackagesReturned(packages);

    const collectionTotal = allTrackings.length + noTrackingRows.length;
    if (allJLReturned && !collectionComplete) {
      s({
        type: 'branch',
        text: `上报 → 采集不完整（已知单号：${allTrackings.join('、') || '无'}；无单号${noTrackingRows.length}行；合计${collectionTotal}，但ERP有${totalShipRows}行发货）`,
      });
      return fin(escalate(`物流采集不完整（已采集${collectionTotal}/${totalShipRows}条），无法确认全部退回，需人工核查`));
    }

    // 赠品已发货独立校验：计算赠品物流状态，仅在主品全部退回时用于决策（不提前 escalate）
    // 交叉验证原则：同一快递单号，鲸灵和 ERP 任一数据源显示「退回」即判退回。
    // 不再区分"主品/赠品包裹"或"哪个源优先"——退回信息只要存在就算数。
    const jlReturnedTrackings = new Set(
      (packages || []).filter(pkg => hasConfirmedReturn(pkg.text))
        .map(pkg => {
          const m = (pkg.text || '').match(/物流单号[：:]\s*\n?(\S+)/);
          return m ? m[1] : null;
        }).filter(Boolean)
    );
    const jlSignedTrackings = new Set(
      (packages || []).filter(pkg => {
        const text = pkg.text || '';
        return SIGNED_KEYWORDS.some(kw => text.includes(kw)) && !hasConfirmedReturn(text);
      }).map(pkg => {
        const m = (pkg.text || '').match(/物流单号[：:]\s*\n?(\S+)/);
        return m ? m[1] : null;
      }).filter(Boolean)
    );
    let giftPkgStatuses = [];
    let giftNotReturned = [];
    if (giftShippedRows.length > 0) {
      const giftTrackings = giftShippedRows
        .flatMap(getRowTrackings)
        .filter(tracking => shippedFlowTrackings.has(tracking));
      giftPkgStatuses = giftTrackings.map(tr => {
        const erpEntry = erpLogResults.find(r => r.tracking === tr);
        const erpReturned = erpEntry && erpEntry.logisticsText && hasConfirmedReturn(erpEntry.logisticsText);
        // 任一数据源显示退回 → 判退回
        if (jlReturnedTrackings.has(tr) || erpReturned) return { tr, status: 'returned', label: `${tr}已退回` };
        // 鲸灵显示已签收（且两边都不是退回）
        if (jlSignedTrackings.has(tr)) return { tr, status: 'signed', label: `${tr}已签收未退回` };
        // 余下走 ERP 判断
        if (erpEntry && erpEntry.logisticsText) {
          const text = erpEntry.logisticsText;
          const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
          const hasYizhan = !hasSigned && YIZHAN_KEYWORDS.some(kw => text.includes(kw));
          if (hasYizhan) return { tr, status: 'yizhan', label: `${tr}驿站待取件未拦截成功` };
          if (hasSigned) return { tr, status: 'signed', label: `${tr}已签收未退回` };
          return { tr, status: 'transit', label: `${tr}在途未拦截成功需拦截` };
        }
        return { tr, status: '未读取到物流', label: `${tr}未读取到物流需人工拦截` };
      });
      giftNotReturned = giftPkgStatuses.filter(p => p.status !== 'returned');
      s({ type: 'read', label: '赠品快递单号', value: giftTrackings.join('/') || '无' });
      s({ type: 'read', label: '赠品物流状态', value: giftPkgStatuses.map(p => p.label).join('；') });
      s({ type: 'check', condition: '赠品快递全部已退回', result: giftNotReturned.length === 0 });
    }

    const allReturned = collectionComplete && (allJLReturned || erpReturned);
    s({ type: 'check', condition: `全部包裹有退回物流节点（鲸灵:${allJLReturned}，ERP:${erpReturned}，采集完整:${collectionComplete}）`, result: allReturned });

    if (allReturned) {
      if (trackingEvaluation.outcomes.some(item => item.outcome === 'unknown')) {
        s({ type: 'branch', text: '上报 → 部分快递单物流结果不明，不能按全部退回处理' });
        return fin(escalate('部分快递单未读取到明确物流结果，无法确认全部退回，需人工核查'));
      }
      if (giftNotReturned.length > 0) {
        const giftDesc = giftPkgStatuses.map(p => p.label).join('；');
        s({ type: 'branch', text: `上报 → 主品全部退回，但赠品未退回: ${giftDesc}` });
        return fin(escalate(`主品已退回，但赠品${giftDesc}，需人工确认`, {
          rulesApplied: [{ doc: 'flow-5.3', section: 'Step3-gift', summary: '主品退回但赠品未退回→上报人工' }],
        }));
      }
      s({ type: 'branch', text: `同意退款 → 全部包裹已退回` });
      return fin(approve(
        '全部包裹物流显示已退回',
        [{ doc: 'flow-5.3', section: 'Step3', summary: '所有包裹已退回→同意退款' }]
      ));
    }

    // 逐包裹分类：已签收 vs 在途/驿站待取件（可拦截）
    const signedPkgs = [];
    const inTransitPkgs = [];
    const yizhanPkgs = [];
    const returnedPkgs = [];
    packages.forEach(pkg => {
      const text = pkg.text || '';
      const hasReturn = hasConfirmedReturn(text);
      const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
      const numMatch = text.match(/物流单号[：:]\s*([A-Za-z0-9]+)/);
      const tracking = numMatch ? numMatch[1] : (pkg.num || '?');
      if (hasReturn) returnedPkgs.push(tracking);
      else if (hasSigned) signedPkgs.push(tracking);
      else if (YIZHAN_KEYWORDS.some(kw => text.includes(kw))) yizhanPkgs.push(tracking);
      else inTransitPkgs.push(tracking);
    });
    s({ type: 'read', label: '包裹分类', value: `已签收:${signedPkgs.join(',') || '无'} 在途:${inTransitPkgs.join(',') || '无'} 驿站待取:${yizhanPkgs.join(',') || '无'} 已退回:${returnedPkgs.join(',') || '无'}` });

    // 构建统一物流行动摘要（主品 + 赠品），用于 reason 输出
    const mainActionParts = [];
    if (returnedPkgs.length) mainActionParts.push(`${returnedPkgs.join('、')}已退回`);
    if (inTransitPkgs.length) mainActionParts.push(`${inTransitPkgs.join('、')}在途未拦截成功需拦截`);
    if (yizhanPkgs.length) mainActionParts.push(`${yizhanPkgs.join('、')}驿站待取件未拦截成功需拦截`);
    if (signedPkgs.length) mainActionParts.push(`${signedPkgs.join('、')}已签收未退回`);
    const giftActionParts = [];
    giftPkgStatuses.forEach(p => {
      if (p.status === 'returned') giftActionParts.push(`${p.tr}已退回`);
      else if (p.status === 'transit') giftActionParts.push(`${p.tr}在途未拦截成功需拦截`);
      else if (p.status === 'signed') giftActionParts.push(`${p.tr}已签收未退回`);
      else if (p.status === 'yizhan') giftActionParts.push(`${p.tr}驿站待取件未拦截成功`);
      else giftActionParts.push(`${p.tr}未读取到物流需人工拦截`);
    });
    const actionSummary = [
      mainActionParts.length ? `主品${mainActionParts.join('，')}` : '',
      giftActionParts.length ? `赠品${giftActionParts.join('，')}` : ''
    ].filter(Boolean).join('；');

    const anySigned = signedPkgs.length > 0;
    const interceptablePkgs = [...inTransitPkgs, ...yizhanPkgs];

    if (anySigned) {
      // 有包裹已签收：如果同时有可拦截包裹 → escalate（需拦截+已签收需退货退款）
      // 如果全部已签收 → reject（无件可拦截）
      if (interceptablePkgs.length > 0) {
        const desc = `已签收包裹（${signedPkgs.join('、')}）需买家申请退货退款；未签收包裹（${interceptablePkgs.join('、')}）需拦截`;
        s({ type: 'branch', text: `上报 → 混合状态：${desc}` });
        return fin(escalate(desc, {
          rulesApplied: [{ doc: 'flow-5.3', section: 'Step4', summary: '部分签收+部分可拦截→拦截未签收件+签收件走退货退款' }],
        }));
      }
      // 全部已签收，无在途件
      s({ type: 'branch', text: '拒绝退款 → 全部包裹已签收，无件可拦截，请申请退货退款' });
      return fin({ ...reject(
        '商品已签收，无法拦截，请自行申请退货退款',
        [],
        [{ doc: 'flow-5.3', section: 'Step4', summary: '已签收→拒绝，让改退货退款' }]
      ), reasonCode: 'SIGNED_NO_INTERCEPT' });
    }

    // 在途和驿站待取件使用同一时间分支：时效充足先拦截等待，时效不足再拒绝
    const remainingHours = queueItem.deadlineAt
      ? Math.max(0, (new Date(queueItem.deadlineAt).getTime() - Date.now()) / 3600000)
      : parseUrgencyHours(queueItem.urgency);
    const hoursUntilNextScan = queueItem.hoursUntilNextScan != null ? queueItem.hoursUntilNextScan : null;
    const remainingDisplay = remainingHours != null ? `${remainingHours.toFixed(1)}小时` : (queueItem.urgency || '未知');
    s({ type: 'read', label: '剩余时效', value: remainingDisplay });
    s({ type: 'read', label: '距下次扫描', value: hoursUntilNextScan != null ? `${hoursUntilNextScan.toFixed(1)}小时` : '未知' });

    const margin = remainingHours != null && hoursUntilNextScan != null
      ? remainingHours - hoursUntilNextScan
      : null;
    const safeToWait = margin != null
      ? margin > SAFETY_MARGIN_HOURS
      // fallback：hoursUntilNextScan 缺失时用剩余时间 vs REMIND_HOURS 兜底
      : (remainingHours != null ? remainingHours > REMIND_HOURS : null);
    if (margin === null && remainingHours != null) {
      console.warn(`[waitingRescan][${queueItem.workOrderNum}] hoursUntilNextScan 缺失，fallback to remainingHours(${remainingHours.toFixed(1)}h) > REMIND_HOURS(${REMIND_HOURS}h)`);
    }

    const interceptRejectReason = yizhanPkgs.length > 0 && inTransitPkgs.length === 0
      ? INTERCEPT_REJECT_REASON_STATION
      : INTERCEPT_REJECT_REASON_TRANSIT;

    if (safeToWait === true) {
      const scanStr = hoursUntilNextScan != null ? `${hoursUntilNextScan.toFixed(1)}h` : '?h';
      const marginStr = margin != null ? margin.toFixed(1) : '?';
      s({ type: 'branch', text: `自动标记等待重查 → 剩余${remainingHours.toFixed(1)}h - 扫描${scanStr} = ${marginStr}h > ${SAFETY_MARGIN_HOURS}h安全边际` });
      return fin(withInterceptRejectCopy({
        action: 'reject',
        reason: `${actionSummary}；剩余${remainingHours.toFixed(1)}h，距下次扫描${scanStr}，安全边际${marginStr}h，当前等待拦截退回后重查；人工可提前沿用该工单原拒绝原因执行拒绝`,
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.3', section: 'Step4', summary: '在途/驿站拦截件+剩余-扫描>8h→自动等待重查，可人工提前拒绝' }],
        warnings: interceptWarnings(cd),
        waitingRescan: true,
        manualExecutionAllowedWhileWaiting: true,
        reasonCode: 'INTERCEPT_WAITING',
      }, interceptRejectReason));
    }

    const marginStr = margin != null ? margin.toFixed(1) : '?';
    s({ type: 'branch', text: `拒绝退款 → 剩余${remainingHours != null ? remainingHours.toFixed(1) : '?'}h - 扫描${hoursUntilNextScan != null ? hoursUntilNextScan.toFixed(1) : '?'}h = ${marginStr}h ≤ ${SAFETY_MARGIN_HOURS}h安全边际，立即处理防止超时自动退款` });
    return fin(withInterceptRejectCopy({ ...reject(
      `${actionSummary}；剩余${remainingHours != null ? remainingHours.toFixed(1) : '?'}h，距下次扫描${hoursUntilNextScan != null ? hoursUntilNextScan.toFixed(1) : '?'}h，安全边际${marginStr}h，时效不足，需立即拒绝防止超时自动退款`,
      interceptWarnings(cd),
      [{ doc: 'flow-5.3', section: 'Step4', summary: '在途/驿站拦截件+剩余-扫描≤8h→拒绝+创建拦截提醒' }]
    ), reasonCode: 'INTERCEPT_TIMEOUT' }, interceptRejectReason));
  }

  s({ type: 'branch', text: `上报 → ERP状态未识别: ${erpStatus}` });
  return fin(escalate(`ERP状态未识别: ${erpStatus}`));
}

// ── flow-5.1 退货退款 ─────────────────────────────────────────────
// 接收显式 ctx，不访问外层变量
// 见 docs/flow-5.1.md
function inferRefundReturn({ cd, ticket, queueItem, s, fin }) {
  const returnTracking = ticket.returnTracking;
  s({ type: 'read', label: '退货快递单号', value: returnTracking || '无' });

  if (!returnTracking) {
    // 七天无理由退货无单号固定人工；其他原因保留原超期判断
    const reason = ticket.afterSaleReason || '';
    const remark = ticket.buyerRemark || '';

    s({ type: 'read', label: '售后原因', value: reason || '无' });
    s({ type: 'read', label: '售后说明', value: remark || '无' });

    if (reason.includes('七天无理由退货')) {
      const manualReason = '无退货快递单号，可能为超期特殊退货或次品特殊处理，请人工查询并判断是否可以同意提前无理由退货';
      s({ type: 'branch', text: `上报 → ${manualReason}` });
      return fin(escalate(manualReason));
    }

    // 其他平台标准非商责原因（无理由/个人原因类），无快递单号→直接拒绝
    const isNonQualityReason = NON_MERCHANT_REASONS.some(kw => reason.includes(kw));

    // 售后原因是"质量问题"/"其他"但buyerRemark含超期/无理由关键词（实为个人原因）
    // 三重校验：原因 + 关键词 + 签收距今>7天
    const OVERDUE_KEYWORDS = ['买重复', '买多', '买多了', '买错', '拍错', '重复购买', '不想要', '拍多', '未拆封', '没拆开'];
    const hasOverdueKeyword = (reason.includes('质量问题') || reason.includes('其他')) &&
      OVERDUE_KEYWORDS.some(kw => remark.includes(kw));
    const signedCheck = hasOverdueKeyword ? checkSignedOverDays(cd, 7) : { overdue: false };
    const isQualityOrOtherWithOverdueRemark = hasOverdueKeyword && signedCheck.overdue;
    if (hasOverdueKeyword) {
      s({ type: 'check', condition: '签收距今>7天', result: signedCheck.overdue ? `是（签收${signedCheck.days}天前 ${signedCheck.signedAt}）` : '否' });
    }

    if (isNonQualityReason || isQualityOrOtherWithOverdueRemark) {
      const rejectNote = isQualityOrOtherWithOverdueRemark
        ? `售后原因"${reason}"备注"${remark}"，签收${signedCheck.days}天前（${signedCheck.signedAt}），超售后期不支持`
        : `售后原因"${reason}"属于无理由退货诉求，超过售后期不支持`;
      s({ type: 'branch', text: `拒绝退款 → ${rejectNote}` });
      const d = reject(
        rejectNote,
        ['超过售后期，不支持无理由退货'],
        [{ doc: 'flow-5.1', section: 'overdue', summary: '超售后期无理由退货→拒绝' }]
      );
      d.rejectReason = '已超过售后期';
      d.rejectDetail = '商品已超过售后期，不支持退货，图片为发货快递截图';
      d.reasonCode = 'OVERDUE_RETURN';
      return fin(d);
    }

    // 其他质量问题类（无法自动判断）→ 上报人工
    s({ type: 'branch', text: `上报 → 售后原因"${reason}"，无退货快递单号，需人工核查` });
    return fin(escalate(`退货退款无快递单号，售后原因：${reason || '未知'}，需人工核查`));
  }

  const sharedReturnGroup = cd.sharedReturnGroup;

  // 只根据平台详情给出的关联工单处理重复退货单号
  if (ticket.returnTrackingMultiUse) {
    const usedBy = ticket.returnTrackingUsedBy && ticket.returnTrackingUsedBy.length
      ? `，已关联工单：${ticket.returnTrackingUsedBy.join('、')}`
      : '';
    s({ type: 'check', condition: '退货快递单号是否被多个售后工单使用', result: true });
    if (!sharedReturnGroup) {
      s({ type: 'branch', text: `上报 → 平台提示快递单号多次使用${usedBy}，但关联记录尚未核对` });
      return fin(escalate(`退货快递单号已被多个工单共用${usedBy}，系统没有完成关联记录核对，需人工处理`));
    }
    if (sharedReturnGroup.mode === 'incomplete') {
      s({ type: 'branch', text: `上报 → ${sharedReturnGroup.reason}` });
      return fin(escalate(sharedReturnGroup.reason));
    }
    if (sharedReturnGroup.mode === 'same_suborders_only') {
      s({ type: 'read', label: '重复退货单处理', value: '关联工单为相同子订单的重复申请，只核对当前工单' });
    } else if (sharedReturnGroup.mode === 'distinct_suborders') {
      s({ type: 'read', label: '重复退货单处理', value: '关联工单包含不同子订单，合并应退商品后核对' });
    } else {
      s({ type: 'branch', text: '上报 → 重复退货单关联结果无法识别' });
      return fin(escalate('重复退货单关联结果无法识别，需人工核对'));
    }
  }

  const aftersale = cd.erpAftersale;
  const hasRows = aftersale && aftersale.rows && aftersale.rows.length;
  s({ type: 'read', label: 'ERP售后入库记录', value: hasRows ? `${aftersale.rows.length} 条记录` : '无记录' });

  // 场景B/C公共变量（无记录和有记录未入库两种情况共用相同判断逻辑）
  const buyerRemark = ticket.buyerRemark || '';
  const hasImages = !!(ticket.images && ticket.images.length);
  const remainingHoursWait = queueItem.deadlineAt
    ? Math.max(0, (new Date(queueItem.deadlineAt).getTime() - Date.now()) / 3600000)
    : parseUrgencyHours(queueItem.urgency);

  if (!hasRows) {
    // 场景B：无入库记录，基于剩余时效自动决策
    s({ type: 'read', label: '售后说明', value: buyerRemark || '无' });
    s({ type: 'read', label: '售后图片', value: hasImages ? '有' : '无' });
    s({ type: 'read', label: '剩余时效', value: remainingHoursWait != null ? `${remainingHoursWait.toFixed(1)}小时` : '未知' });

    if (remainingHoursWait != null && remainingHoursWait > REMIND_HOURS) {
      s({ type: 'branch', text: `自动标记等待重查 → 仓库未收到退货，剩余${remainingHoursWait.toFixed(1)}h > ${REMIND_HOURS}h，等待下次扫描` });
      return fin({
        action: 'reject',
        waitingRescan: true,
        reason: `仓库未收到退货，剩余${remainingHoursWait.toFixed(1)}h，等待下次扫描自动重查`,
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step3', summary: '未入库+剩余>12h→等待重查' }],
        warnings: [],
      });
    }

    if (remainingHoursWait != null && remainingHoursWait <= REMIND_HOURS) {
      s({ type: 'branch', text: `拒绝退款 → 剩余${remainingHoursWait.toFixed(1)}h ≤ ${REMIND_HOURS}h，时效不足，立即处理` });
      return fin({ ...reject(
        `仓库暂未收到此件，已反馈快递找件`,
        ['⚠️ 时效不足，退货仓库待拆包，建议人工核实'],
        [{ doc: 'flow-5.1', section: 'Step3', summary: '未入库+剩余≤12h→拒绝' }]
      ), reasonCode: 'WAREHOUSE_NOT_RECEIVED' });
    }

    s({ type: 'branch', text: '上报 → 无法确定剩余时效' });
    return fin(escalate('退货尚未入库确认，需人工核查'));
  }

  // 必须有「卖家已收到退货」状态
  const receivedRows = aftersale.rows.filter(row =>
    row.goodsStatus && row.goodsStatus.includes('卖家已收到退货')
  );
  const hasConfirmedReceipt = receivedRows.length > 0;
  const statusList = aftersale.rows.map(r => r.goodsStatus || '?').join('；');
  s({ type: 'check', condition: `存在「卖家已收到退货」状态的入库行（实际：${statusList}）`, result: hasConfirmedReceipt });

  if (!hasConfirmedReceipt) {
    // 场景C：有ERP记录但未入库，基于剩余时效自动决策
    s({ type: 'read', label: '剩余时效', value: remainingHoursWait != null ? `${remainingHoursWait.toFixed(1)}小时` : '未知' });

    if (remainingHoursWait != null && remainingHoursWait > REMIND_HOURS) {
      s({ type: 'branch', text: `自动标记等待重查 → ERP有记录但未入库（状态：${statusList}），剩余${remainingHoursWait.toFixed(1)}h > ${REMIND_HOURS}h，等待下次扫描` });
      return fin({
        action: 'reject',
        waitingRescan: true,
        reason: `仓库未收到退货，剩余${remainingHoursWait.toFixed(1)}h，等待下次扫描自动重查`,
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step3', summary: '有记录未入库+剩余>12h→等待重查' }],
        warnings: [],
      });
    }

    if (remainingHoursWait != null && remainingHoursWait <= REMIND_HOURS) {
      s({ type: 'branch', text: `拒绝退款 → 剩余${remainingHoursWait.toFixed(1)}h ≤ ${REMIND_HOURS}h，时效不足，立即处理` });
      return fin({ ...reject(
        `仓库暂未收到此件，已反馈快递找件`,
        ['⚠️ 时效不足，退货仓库待拆包，建议人工核实'],
        [{ doc: 'flow-5.1', section: 'Step3', summary: '有记录未入库+剩余≤12h→拒绝' }]
      ), reasonCode: 'WAREHOUSE_NOT_RECEIVED' });
    }

    s({ type: 'branch', text: '上报 → 无法确定剩余时效' });
    return fin(escalate('退货尚未入库确认，需人工核查'));
  }

  // ── 收集入库明细 ─────────────────────────────────────────────────
  const receivedItems = [];  // { name, qtyGood, qtyBad }
  receivedRows.forEach(row => {
    (row.items || []).forEach(item => {
      const name = item.name || '';
      if (EXEMPT_ACCESSORY_KEYWORDS.some(kw => name.includes(kw))) return;
      receivedItems.push({
        name,
        specCode: item.specCode || '',
        qtyGood: parseInt(item.qtyGood) || 0,
        qtyBad: parseInt(item.qtyBad) || 0,
      });
    });
  });
  const totalGood = receivedItems.reduce((s, i) => s + i.qtyGood, 0);
  const totalBad = receivedItems.reduce((s, i) => s + i.qtyBad, 0);
  s({ type: 'read', label: '入库数量', value: `良品 ${totalGood} 件，次品 ${totalBad} 件` });

  // ── 问题收集（次品 + 后续缺件统一输出，避免短路隐藏信息）─────
  const issues = [];

  // ── 次品检查：逐商品报告 ────────────────────────────────────────
  const badItems = receivedItems.filter(i => i.qtyBad > 0);
  if (badItems.length > 0) {
    const badDesc = badItems.map(i => `${i.name}（次品${i.qtyBad}件）`).join('、');
    s({ type: 'branch', text: `上报 → 次品：${badDesc}` });
    issues.push({ type: 'qtyBad', message: `退货含次品：${badDesc}` });
  }

  // 不同子订单共用同一退货单：按平台关联到的工单记录合并逐规格核对
  if (sharedReturnGroup && sharedReturnGroup.mode === 'distinct_suborders') {
    const expectedItems = sharedReturnGroup.expectedItems || [];
    const expectedBySpec = new Map();
    for (const item of expectedItems) {
      const specCode = String(item.specCode || '').trim();
      const qty = Number(item.qty);
      if (!specCode || !Number.isFinite(qty) || qty <= 0) {
        return fin(escalate('共用退货单的应退商品记录不完整，需人工核对'));
      }
      const existing = expectedBySpec.get(specCode);
      if (existing) existing.qty += qty;
      else expectedBySpec.set(specCode, { specCode, name: item.name || specCode, qty });
    }
    if (!expectedBySpec.size) return fin(escalate('共用退货单没有可核对的应退商品记录'));

    const receivedBySpec = new Map();
    const missingSpecItems = [];
    for (const item of receivedItems) {
      const specCode = String(item.specCode || '').trim();
      if (!specCode && (item.qtyGood > 0 || item.qtyBad > 0)) {
        missingSpecItems.push(item.name || '未知商品');
        continue;
      }
      if (!specCode) continue;
      const existing = receivedBySpec.get(specCode) || {
        specCode,
        name: item.name || specCode,
        qtyGood: 0,
        qtyBad: 0,
      };
      existing.qtyGood += item.qtyGood;
      existing.qtyBad += item.qtyBad;
      receivedBySpec.set(specCode, existing);
    }
    if (missingSpecItems.length) {
      return fin(escalate(`共用退货单的入库商品缺少规格编码：${missingSpecItems.join('、')}`));
    }
    if (issues.length) {
      return fin(escalate(issues.map(issue => issue.message).join('；'), {
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '共用退货单含次品→上报人工' }],
      }));
    }

    const shortages = [];
    for (const expected of expectedBySpec.values()) {
      const received = receivedBySpec.get(expected.specCode);
      const actual = received ? received.qtyGood : 0;
      if (actual < expected.qty) shortages.push(`${expected.name}（退了${actual}件，应退${expected.qty}件）`);
    }
    if (shortages.length) {
      return fin(escalate(`共用退货单退货数量不足：${shortages.join('、')}`, {
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '共用退货单逐规格不足→上报人工' }],
      }));
    }

    const extras = [];
    for (const received of receivedBySpec.values()) {
      const expected = expectedBySpec.get(received.specCode);
      const extraQty = received.qtyGood - (expected ? expected.qty : 0);
      if (extraQty > 0) extras.push(`${received.name}多${extraQty}件`);
    }
    const summary = [...expectedBySpec.values()].map(item => `${item.name}×${item.qty}`).join('、');
    const decision = approve(
      `共用退货单逐规格核对通过：${summary}${extras.length ? `；确认多退：${extras.join('、')}` : ''}`,
      [{ doc: 'flow-5.1', section: 'Step4', summary: '不同子订单共用退货单，合并逐规格核对通过→同意退款' }]
    );
    if (extras.length) decision.warnings = [`客户实际多退：${extras.join('、')}`];
    return fin(decision);
  }

  // ── 逐商品对比（有 productArchive 时）────────────────────────────
  const subOrders = ticket.subOrders || [];
  const gifts = ticket.gifts || [];

  // 合并所有子订单的商品档案（多子订单各需独立 product-match）
  const productArchives = cd.productArchives || [];
  const productMatches = cd.productMatches || [];
  let archiveSubItems = [];
  // 向后兼容：旧数据无 productArchives 数组时，使用 productArchive 单字段
  if (productArchives.length === 0 && cd.productArchive && cd.productArchive.subItems) {
    archiveSubItems = cd.productArchive.subItems;
    // 单品向后兼容：subItems 为空但有 title → 构造虚拟 subItem
    if (archiveSubItems.length === 0 && cd.productArchive.title) {
      archiveSubItems = [{ name: (cd.productArchive.title || '').split(';')[0].split('-')[0].trim(), specCode: cd.productArchive.outerId, qty: 1 }];
    }
  } else {
    for (const pa of productArchives) {
      if (pa && pa.subItems && pa.subItems.length > 0) {
        for (const item of pa.subItems) {
          archiveSubItems.push({ ...item, _subOrderId: pa.subOrderId });
        }
      } else if (pa && pa.title) {
        // 单品（type=0，subItems 为空）：用档案 title 构造虚拟 subItem，与赠品处理对称
        archiveSubItems.push({ name: (pa.title || '').split(';')[0].split('-')[0].trim(), specCode: pa.outerId, qty: 1, _subOrderId: pa.subOrderId });
      }
    }
  }

  // 检查 product-match 是否有任何子订单失败
  const anyMatchFailed = productMatches.length > 0 && productMatches.every(m => m.error || m.matched === false);
  const anyArchiveAvailable = productArchives.some(pa => pa && pa.subItems);
  // 全部子订单 product-match 失败且无档案可用 → 上报
  if (anyMatchFailed && !anyArchiveAvailable && archiveSubItems.length === 0) {
    const allErrors = productMatches.map(m => `${m.subOrderId || '?'}: ${m.error || 'attr1未匹配'}`).join('; ');
    s({ type: 'branch', text: `上报 → 所有子订单对应表匹配失败，无法确认商品明细` });
    return fin(escalate(`商品对应表匹配失败（${allErrors}），需人工核查`, {
      rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '全部子订单 attr1 mismatch → 上报' }],
    }));
  }

  // 赠品商品档案：合并到 expectedItems 一起参与逐商品匹配
  // 如果赠品是单品（type=0, subItems 为空），用赠品档案的 title 作为1个 expected item
  const giftArchive = cd.giftProductArchive;
  let giftArchiveSubItems = (giftArchive && giftArchive.subItems && giftArchive.subItems.length > 0)
    ? giftArchive.subItems
    : [];
  if (giftArchive && giftArchiveSubItems.length === 0 && giftArchive.title) {
    // 单品赠品：用档案 title 构造虚拟 subItem（qty=1，名称取分号前）
    giftArchiveSubItems = [{ name: (giftArchive.title || '').split(';')[0].split('-')[0].trim(), specCode: giftArchive.outerId, qty: 1 }];
  }

  if (archiveSubItems.length > 0) {
    // ── 逐商品匹配 ──────────────────────────────────────────────
    const afterSaleNum = (subOrders[0] && subOrders[0].afterSaleNum) || 1;
    // afterSaleNum 一致性断言（多子订单应共享同一值，不匹配时打日志）
    if (subOrders.length > 1) {
      const nums = subOrders.map(function(s){ return s.afterSaleNum; });
      if (new Set(nums).size > 1) console.error('[WARN] afterSaleNum mismatch:', nums);
    }
    const matchResults = [];  // { expected: item, expectedQty, matched, receivedQty, status }
    const usedReceived = new Set();  // 已匹配的入库项索引

    // 主品子品匹配
    archiveSubItems.forEach(exp => {
      const isExempt = EXEMPT_ACCESSORY_KEYWORDS.some(kw => (exp.name || '').includes(kw));
      if (isExempt) return;
      const expQty = (exp.qty || 1) * afterSaleNum;

      let bestIdx = -1;
      let bestScore = 0;
      receivedItems.forEach((ri, idx) => {
        if (usedReceived.has(idx)) return;
        const nameA = (exp.name || '').replace(/\s+/g, '');
        const nameB = (ri.name || '').replace(/\s+/g, '');
        if (nameA.includes(nameB) || nameB.includes(nameA)) {
          const score = Math.min(nameA.length, nameB.length);
          if (score > bestScore) { bestScore = score; bestIdx = idx; }
        }
      });

      if (bestIdx >= 0) {
        usedReceived.add(bestIdx);
        const ri = receivedItems[bestIdx];
        const status = ri.qtyGood >= expQty ? 'ok' : 'short';
        matchResults.push({ expected: exp.name, expectedQty: expQty, matched: ri.name, receivedQty: ri.qtyGood, status, source: '主品' });
      } else {
        matchResults.push({ expected: exp.name, expectedQty: expQty, matched: null, receivedQty: 0, status: 'missing', source: '主品' });
      }
    });

    // 赠品子品匹配（有 giftProductArchive 时）
    // 如果赠品和主品是同一种商品（名称包含匹配），合并到主品的 expectedQty，不单独占用入库行
    const giftAfterSaleNum = (gifts[0] && gifts[0].afterSaleNum) || 1;
    giftArchiveSubItems.forEach(exp => {
      const isExempt = EXEMPT_ACCESSORY_KEYWORDS.some(kw => (exp.name || '').includes(kw));
      if (isExempt) return;
      const expQty = (exp.qty || 1) * giftAfterSaleNum;
      const giftNameNorm = (exp.name || '').replace(/\s+/g, '');

      // 先检查是否和某个已匹配的主品是同一种商品 → 合并
      const sameItemMain = matchResults.find(m => {
        if (!m.matched) return false;
        const mainName = (m.matched || '').replace(/\s+/g, '');
        return mainName.includes(giftNameNorm) || giftNameNorm.includes(mainName);
      });
      if (sameItemMain) {
        // 合并：增加期望数，重新判断状态
        sameItemMain.expectedQty += expQty;
        sameItemMain.status = sameItemMain.receivedQty >= sameItemMain.expectedQty ? 'ok' : 'short';
        sameItemMain.source = '主品+赠品';
        return;
      }

      // 赠品和主品不同 → 独立匹配
      let bestIdx = -1;
      let bestScore = 0;
      receivedItems.forEach((ri, idx) => {
        if (usedReceived.has(idx)) return;
        const nameA = giftNameNorm;
        const nameB = (ri.name || '').replace(/\s+/g, '');
        if (nameA.includes(nameB) || nameB.includes(nameA)) {
          const score = Math.min(nameA.length, nameB.length);
          if (score > bestScore) { bestScore = score; bestIdx = idx; }
        }
      });

      if (bestIdx >= 0) {
        usedReceived.add(bestIdx);
        const ri = receivedItems[bestIdx];
        const status = ri.qtyGood >= expQty ? 'ok' : 'short';
        matchResults.push({ expected: exp.name, expectedQty: expQty, matched: ri.name, receivedQty: ri.qtyGood, status, source: '赠品' });
      } else {
        matchResults.push({ expected: exp.name, expectedQty: expQty, matched: null, receivedQty: 0, status: 'missing', source: '赠品' });
      }
    });

    // 输出匹配结果
    matchResults.forEach(m => {
      const label = m.status === 'ok' ? '✓' : m.status === 'short' ? '✗不足' : '✗缺失';
      const srcTag = m.source === '赠品' ? '[赠]' : '';
      s({ type: 'check', condition: `${srcTag}${m.expected}`, result: `${label} 期望${m.expectedQty}件，入库${m.receivedQty}件${m.matched ? `（匹配：${m.matched}）` : ''}` });
    });

    // 检查赠品是否在入库中（未匹配的入库项可能是赠品或 archive 缺失的品类）
    const unmatchedReceived = receivedItems.filter((_, idx) => !usedReceived.has(idx));
    if (unmatchedReceived.length > 0) {
      const giftDesc = unmatchedReceived.map(i => `${i.name}(${i.qtyGood}件)`).join('、');
      s({ type: 'read', label: '入库额外项（可能为赠品）', value: giftDesc });
    }

    // 判断结果
    const hasShortage = matchResults.some(m => m.status !== 'ok');
    if (hasShortage) {
      const shortItems = matchResults.filter(m => m.status !== 'ok');
      const shortDesc = shortItems.map(m => {
        const name = (m.expected || '').replace(/\s+/g, '');
        if (m.status === 'missing') return `${name}（退货里没有）`;
        return `${name}（退了${m.receivedQty}件，应退${m.expectedQty}件）`;
      }).join('，');
      s({ type: 'branch', text: `上报 → 入库不足：${shortDesc}` });
      issues.push({ type: 'shortage', message: `退货数量不足：${shortDesc}` });
    }

    // 汇总所有问题统一上报
    if (issues.length > 0) {
      return fin(escalate(issues.map(i => i.message).join('；'), {
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '退货异常→上报人工' }],
      }));
    }

    // 全部已知品匹配通过，但有未匹配的入库项
    if (unmatchedReceived.length > 0) {
      const matchedSummary = matchResults.map(m => {
        const name = (m.matched || m.expected || '').replace(/\s+/g, '');
        return `${name}×${m.receivedQty}`;
      }).join('、');
      const unmatchedSummary = unmatchedReceived.map(i => {
        const name = (i.name || '').replace(/\s+/g, '');
        return `${name}×${i.qtyGood}件`;
      }).join('、');
      s({ type: 'branch', text: `上报 → ${unmatchedSummary} 未在对应表中` });
      return fin(escalate(
        `对应表查无此规格：${unmatchedSummary}（已匹配 ${matchedSummary}），请确认是否为赠品或活动搭配`,
        {
          confidence: 'medium',
          rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '对应表缺规格→上报' }],
          warnings: [`未匹配商品：${unmatchedReceived.map(i => i.name).join('、')}`],
        }
      ));
    }

    // 全部品匹配通过且无未匹配项
    const totalExpected = matchResults.reduce((s, m) => s + m.expectedQty, 0);
    const summary = matchResults.map(m => {
      const name = (m.expected || '').replace(/\s+/g, '');
      return `${name}×${m.expectedQty}`;
    }).join('、');
    const surplus = totalGood - totalExpected;
    const surplusWarning = surplus > 0
      ? [`入库${totalGood}件，比期望多${surplus}件（可能少申请了退货份数）`]
      : [];
    if (surplus > 0) {
      s({ type: 'read', label: '入库多于期望', value: `多${surplus}件` });
    }
    s({ type: 'branch', text: `同意退款 → ${summary}，入库${totalGood}件 ≥ 期望${totalExpected}件` });
    const approveResult = approve(
      `核对通过：${summary}，实退${totalGood}件${surplus > 0 ? `（多${surplus}件）` : ''}`,
      [{ doc: 'flow-5.1', section: 'Step4', summary: '逐商品对比通过→同意退款' }]
    );
    if (surplusWarning.length) approveResult.warnings = surplusWarning;
    return fin(approveResult);
  }

  // ── 无 productArchive 时的降级逻辑：上报人工 ─────────────────────
  let expectedMainQty = 0;
  subOrders.forEach(so => {
    expectedMainQty += (so.afterSaleNum || 1);
  });
  let expectedGiftQty = 0;
  gifts.forEach(g => {
    const attr = g.attr1 || '';
    const parts = attr.split(/[+＋、]/).filter(Boolean);
    expectedGiftQty += parts.length > 0 ? parts.length : 1;
  });
  const expectedQty = expectedMainQty + expectedGiftQty;
  const qtyDesc = gifts.length > 0 ? `主品${expectedMainQty}件+赠品${expectedGiftQty}件` : `${expectedMainQty}件`;

  s({ type: 'check', condition: `良品 ${totalGood} ≥ 应退 ${expectedQty}（${qtyDesc}，无商品档案按单品算）`, result: totalGood >= expectedQty });

  // 无 productArchive 时无法准确计算应退数量，禁止自动批准
  s({ type: 'branch', text: `上报 → 缺少商品档案，无法核对应退数量` });
  return fin(escalate(
    `缺少商品档案，无法核对明细（入库${totalGood}件，申请退${expectedMainQty}件）`,
    [{ doc: 'flow-5.1', section: 'Step4', summary: '无档案→上报人工（安全优先）' }]
  ));
}

// ── 主入口：校验 + 路由 ───────────────────────────────────────────
// 变更规则：只修改此函数时，不影响 inferRefundOnly / inferRefundReturn；
// 修改某个 flow 函数时，只影响该类型工单，不影响其他类型。
function inferDecision(sim, queueItem) {
  const steps = [];
  function s(step) { steps.push(step); return step; }
  function fin(decision) { return { ...decision, steps }; }

  const cd = sim.collectedData || {};
  const type = queueItem.type;
  const ticket = cd.ticket || {};

  // ── hint 覆盖 ─────────────────────────────────────────────────
  const hint = queueItem.hint || '';
  if (hint) {
    s({ type: 'read', label: '用户评价指令', value: hint });
    const hintAction = parseHintAction(hint);
    s({ type: 'check', condition: '解析评价指令', result: hintAction ? `→ ${hintAction}` : '未识别' });
    if (hintAction) {
      s({ type: 'branch', text: `执行评价指令覆盖 → ${hintAction}` });
      const constrainedReasons = [
        ...(MERCHANT_FAULT_REASONS.some(kw => String(ticket.afterSaleReason || '').includes(kw)) ? ['商责'] : []),
        ...(type === '换货' ? ['换货'] : []),
      ];
      const hintedDecision = {
        action: hintAction,
        reason: `根据评价内容调整：${hint}`,
        confidence: 'high',
        rulesApplied: [],
        warnings: [],
        hinted: true,
      };
      if (constrainedReasons.length) {
        hintedDecision.requiresHumanReview = true;
        hintedDecision.autoExecutionBlocked = true;
        hintedDecision.humanTriggeredExecutionAllowed = hintAction === 'approve' || hintAction === 'reject';
        hintedDecision.manualReviewReasons = constrainedReasons;
        hintedDecision.recommendedActionLabel = type === '换货' && hintAction === 'approve'
          ? '同意换货'
          : (type === '换货' && hintAction === 'reject' ? '拒绝换货' : undefined);
        hintedDecision.warnings = [
          `⚠️ ${constrainedReasons.join('+')}工单禁止无人自动执行；当前动作只能由人工确认后触发`,
          ...(type === '换货' ? ['请确认正确商品是否已提前补发/换出，避免再次生成发货单'] : []),
        ];
      }
      return fin(hintedDecision);
    }
    s({ type: 'branch', text: '评价指令未识别为操作，继续规则推理' });
  }

  // ── 平台终态检测（优先于一切校验）────────────────────────────────
  // 工单已终结（退款成功/已关闭等）→ 无需操作，自动归档
  // 注意：此检测不依赖 erpSearch，必须在 validateCollectedData 之前执行
  const workOrderStatus = ticket.workOrderStatus || '';

  // 已取消/取消中 → 上报人工确认（可能恢复，不入终态 skip）
  const CANCELLED_STATES = ['已取消', '用户已取消', '取消中'];
  if (workOrderStatus && CANCELLED_STATES.some(cs => workOrderStatus.includes(cs))) {
    s({ type: 'read', label: '工单状态', value: workOrderStatus });
    s({ type: 'branch', text: `等待归档 → 客户取消退款，建议人工取消拦截快递` });
    return fin({
      action: 'wait_archive',
      reason: `工单状态：${workOrderStatus}，客户取消退款，建议人工取消拦截快递`,
      confidence: 'high',
      rulesApplied: [{ doc: 'INDEX.md', section: '工单取消', summary: '取消状态→等待归档+提醒取消拦截' }],
      warnings: ['客户取消退款，如有拦截记录请取消快递拦截'],
    });
  }

  const TERMINAL_STATES = ['已退款', '退款成功', '已完成退款', '已关闭', '已撤销', '客服-已同意', '客服-已拒绝'];
  if (workOrderStatus && TERMINAL_STATES.some(ts => workOrderStatus.includes(ts))) {
    s({ type: 'read', label: '工单状态', value: workOrderStatus });
    s({ type: 'branch', text: `工单已终结（${workOrderStatus}），平台已自动处理，无需操作` });
    return fin({
      action: 'skip',
      reason: `工单状态：${workOrderStatus}，平台已自动处理，无需操作`,
      confidence: 'high',
      rulesApplied: [],
      warnings: [],
    });
  }

  // ── 工单不可访问 → 按来源分流 ───────────────────────────────
  // 必须在 validateCollectedData 之前，因为此时 ticket 为 null
  // 扫描刚发现的 live 工单：列表反查未命中不是明确终态，保留待复查。
  // 非扫描来源保留旧行为，避免历史/手工场景重复卡住。
  // 注意："不属于当前商家" 不在此处处理——这是账号注入异常，不是工单终态。
  //       下方 validateCollectedData (ticket=null) 会捕获并 escalate 到人工。
  const goneFromList = (cd.collectErrors || []).find(e =>
    e.startsWith('read-ticket:') && (
      e.includes('已不在待处理列表') || e.includes('已处理或已关闭')
    )
  );
  if (goneFromList) {
    if (isLiveScanItem(sim, queueItem)) {
      s({ type: 'branch', text: `详情页未确认，保留待复查 → ${goneFromList}` });
      return fin(escalate(`详情页未确认，需复查：${goneFromList}`, {
        rulesApplied: [{ doc: 'terminal', section: 'gone', summary: '扫描工单详情页未确认→保留待复查' }],
        warnings: ['扫描刚发现的工单详情页暂时不可确认，未自动归档'],
      }));
    }
    s({ type: 'branch', text: `工单不可访问 → ${goneFromList}` });
    return fin({
      action: 'skip',
      reason: goneFromList,
      confidence: 'high',
      rulesApplied: [{ doc: 'terminal', section: 'gone', summary: '工单不可访问→自动归档' }],
      warnings: [],
    });
  }

  // ── 采集数据完整性校验 ────────────────────────────────────────
  // 必填字段缺失 → 立即 escalate，禁止走默认分支（无声失败的根本防护）
  const validationErr = validateCollectedData(cd, type);
  if (validationErr) {
    s({ type: 'branch', text: `采集数据不完整：${validationErr}` });
    return fin(escalate(validationErr));
  }

  s({ type: 'read', label: '工单类型', value: type || '未知' });

  // ── 关键采集失败 → 上报 ───────────────────────────────────────
  const criticalErrors = (cd.collectErrors || []).filter(e =>
    e.startsWith('read-ticket') || e.startsWith('erp-search:')
  );
  s({ type: 'check', condition: '关键数据采集成功 (read-ticket + erp-search)', result: criticalErrors.length === 0 });
  if (criticalErrors.length) {
    s({ type: 'branch', text: `关键采集失败，上报 → ${criticalErrors[0]}` });
    return fin(escalate(`关键数据采集失败：${criticalErrors[0]}`));
  }

  // ── 操作约束不阻断事实采集：换货/商责有退货单号时先核验退回商品 ──
  const afterSaleReason = ticket.afterSaleReason || '';
  const isMerchantFault = MERCHANT_FAULT_REASONS.some(kw => afterSaleReason.includes(kw));
  const isReturnReviewType = type === '换货' || type === '退货退款';
  if (isReturnReviewType && (type === '换货' || isMerchantFault)) {
    return inferManualReturnReview({ cd, ticket, queueItem, s, fin, isMerchantFault });
  }

  // ── 其他商责售后原因仍固定人工 ─────────────────────────────────
  if (isMerchantFault) {
    s({ type: 'read', label: '售后原因', value: afterSaleReason });
    s({ type: 'branch', text: `上报 → 商责售后原因「${afterSaleReason}」，有罚款风险，需人工处理` });
    return fin(escalate(`商责售后原因「${afterSaleReason}」，需人工核实处理（商责有罚款风险）`, {
      rulesApplied: [{ doc: 'INDEX.md', section: '商责拦截', summary: '商责原因→上报人工' }],
    }));
  }

  // ── 路由到独立 flow 函数 ──────────────────────────────────────
  const ctx = { cd, ticket, queueItem, s, fin };

  if (type === '仅退款') return inferRefundOnly(ctx);
  if (type === '退货退款') {
    const result = inferRefundReturn(ctx);
    // 退货退款检测已有拦截记录 → 追加 warning 但不改变决策
    if (cd.intercepted && !result.warnings.some(w => w.includes('已有拦截记录'))) {
      result.warnings.push(`该工单关联运单 ${cd.intercepted.tracking} 已有拦截记录（来自 ${cd.intercepted.workOrderNum}），请核实是否重复`);
    }
    return result;
  }

  s({ type: 'branch', text: `上报 → 工单类型未识别: ${type || '未知'}` });
  return fin(escalate(`工单类型未识别: ${type || '未知'}`));
}

module.exports = { inferDecision };
