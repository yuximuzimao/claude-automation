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

const { RETURN_KEYWORDS, SIGNED_KEYWORDS, NON_MERCHANT_REASONS, MERCHANT_FAULT_REASONS, REMIND_HOURS } = require('./constants');

// 免退配件关键词（不计入应退/实退数量）
const EXEMPT_ACCESSORY_KEYWORDS = ['悦希雪梨纸', '悦希印花礼袋', '悦希印花礼盒'];

// 解析 urgency 字符串（如 "1天3小时" / "3小时"）为总小时数
function parseUrgencyHours(urgency) {
  if (!urgency) return null;
  const dayMatch = urgency.match(/(\d+)天/);
  const hourMatch = urgency.match(/(\d+)小时/);
  return ((dayMatch ? parseInt(dayMatch[1]) : 0) * 24) + (hourMatch ? parseInt(hourMatch[1]) : 0);
}

// 判断售后说明是否实质为空（"无"/"无说明"/"/"等均视为空）
function isRemarkEmpty(remark) {
  if (!remark) return true;
  return /^[无\/\-\s]*$/.test(remark.trim());
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
  return (cd[field] && cd[field].rows && cd[field].rows.rows) || [];
}

// 聚合所有行的发货状态，替代只读第一行的 getErpStatus()
// 已发货状态：卖家已发货 / 交易成功 / 交易关闭（订单已关闭但曾是发货状态）
// 未发货状态：待审核 / 待打印快递单
function getAggregatedErpStatus(cd, field) {
  const rows = getErpRows(cd, field);
  if (!rows.length) return { raw: null, statuses: [], hasShipped: false, allNotShipped: false, hasTracking: false };
  const statuses = [...new Set(rows.map(r => r.status).filter(Boolean))];
  const SHIPPED = ['卖家已发货', '交易成功', '交易关闭'];
  const NOT_SHIPPED = ['待审核', '待打印快递单'];
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
  return packages.every(pkg =>
    RETURN_KEYWORDS.some(kw => (pkg.text || '').includes(kw))
  );
}

// 检查是否有包裹已被买家签收（且无退回节点）
function anyPackageSignedByBuyer(packages) {
  if (!packages || !packages.length) return false;
  return packages.some(pkg => {
    const text = pkg.text || '';
    const hasReturn = RETURN_KEYWORDS.some(kw => text.includes(kw));
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

function escalate(reason, extra) {
  return { action: 'escalate', reason, confidence: 'low', rulesApplied: [], warnings: [], ...extra };
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
  s({ type: 'read', label: 'ERP主商品状态', value: erpAgg.statuses.length ? erpAgg.statuses.join('/') : '未获取' });

  if (!erpStatus && !erpAgg.statuses.length) {
    s({ type: 'branch', text: '上报 → ERP状态未获取' });
    return fin(escalate('未获取到ERP状态，需人工核查'));
  }

  // 5.2：未发货
  // 待审核：订单未审核，可退款
  // 待打印快递单：已审核，分两种情况：有快递单号→需拦截，无快递单号→可退款
  const isNotShipped = erpAgg.allNotShipped;
  s({ type: 'check', condition: `所有ERP行 ∈ [待审核, 待打印快递单]（全部未发货）`, result: isNotShipped });

  if (isNotShipped) {
    // 待打印快递单时检查是否已有快递单号（扫所有行，防止分包场景只读 rows[0] 漏判）
    if (erpStatus === '待打印快递单') {
      const printReadyRow = getErpRows(cd, 'erpSearch').find(r =>
        r.status === '待打印快递单' && (r.tracking || (r.trackings && r.trackings.length))
      );
      const mainTracking = printReadyRow && (printReadyRow.tracking || (printReadyRow.trackings && printReadyRow.trackings[0]));
      s({ type: 'read', label: '主商品快递单号', value: mainTracking || '无' });
      if (mainTracking) {
        s({ type: 'branch', text: `上报 → 待打印快递单且已有快递单号 ${mainTracking}，需人工拦截` });
        return fin(escalate(`订单已审核且快递单号已生成(${mainTracking})，需人工拦截后退款`, {
          rulesApplied: [{ doc: 'flow-5.2', section: 'Step4b', summary: '待打印快递单+有运单号→上报人工拦截' }],
        }));
      }
    }

    s({ type: 'branch', text: '进入「仅退款-未发货」流程 (flow-5.2)' });
    const gifts = ticket.gifts || [];
    s({ type: 'read', label: '赠品数量', value: `${gifts.length} 件` });

    if (gifts.length > 0) {
      const giftAgg = getAggregatedErpStatus(cd, 'giftErpSearch');
      const giftErpStatus = giftAgg.raw;
      s({ type: 'read', label: 'ERP赠品状态', value: giftAgg.statuses.length ? giftAgg.statuses.join('/') : '未获取' });

      if (!giftErpStatus && !giftAgg.statuses.length) {
        s({ type: 'branch', text: '上报 → 赠品ERP状态未获取' });
        return fin(escalate('赠品ERP状态未获取，需人工核查'));
      }
      const giftOk = giftAgg.allNotShipped;
      s({ type: 'check', condition: `赠品所有ERP行 ∈ [待审核, 待打印快递单]（全部未发货）`, result: giftOk });
      if (!giftOk && giftAgg.hasShipped) {
        s({ type: 'branch', text: `上报 → 主商品未发货但赠品有已发货分包（${giftAgg.statuses.join('/')}），需人工拦截赠品快递后处理` });
        return fin(escalate(`主商品未发货但赠品有已发货分包（${giftAgg.statuses.join('/')}），需人工拦截赠品快递后处理`, {
          rulesApplied: [{ doc: 'flow-5.2', section: 'Step4c', summary: '主商品未发货+赠品已发货→上报人工' }],
        }));
      }
      if (!giftOk) {
        s({ type: 'branch', text: `上报 → 赠品ERP状态异常: ${giftAgg.statuses.join('/')}` });
        return fin(escalate(`赠品ERP状态异常: ${giftAgg.statuses.join('/')}，需人工核查`));
      }

      // 赠品待打印快递单时同样检查快递单号（扫所有行）
      if (giftErpStatus === '待打印快递单') {
        const printReadyGiftRow = getErpRows(cd, 'giftErpSearch').find(r =>
          r.status === '待打印快递单' && (r.tracking || (r.trackings && r.trackings.length))
        );
        const giftTracking = printReadyGiftRow && (printReadyGiftRow.tracking || (printReadyGiftRow.trackings && printReadyGiftRow.trackings[0]));
        s({ type: 'read', label: '赠品快递单号', value: giftTracking || '无' });
        if (giftTracking) {
          s({ type: 'branch', text: `上报 → 赠品已有快递单号 ${giftTracking}，需人工拦截` });
          return fin(escalate(`赠品快递单号已生成(${giftTracking})，需人工拦截后退款`, {
            rulesApplied: [{ doc: 'flow-5.2', section: 'Step4b', summary: '赠品待打印快递单+有运单号→上报人工拦截' }],
          }));
        }
      }
    }

    s({ type: 'branch', text: `同意退款 → 主商品${gifts.length ? '+赠品' : ''}均未发货（无快递单号）` });
    return fin(approve(
      `主商品${gifts.length ? '+赠品' : ''}均未发货（无快递单号）`,
      [{ doc: 'flow-5.2', section: 'Step4', summary: '主商品+赠品未发货→同意退款' }]
    ));
  }

  // 待发货（补发单或人工备货中）→ 一般上报人工
  // 例外：若 ERP 行中有快递单号，说明实际已发货（可能因退款导致状态未回传平台）→ 进入已发货流程
  if (erpStatus === '待发货' && !erpAgg.hasTracking) {
    s({ type: 'branch', text: '上报 → ERP状态为待发货且无快递单号，可能为补发单正在备货，需人工确认' });
    return fin(escalate('ERP状态为「待发货」，可能存在补发单正在备货，请人工确认后操作', {
      rulesApplied: [{ doc: 'flow-5.3', section: 'Step4', summary: '待发货→可能补发单→上报人工' }],
    }));
  }
  if (erpStatus === '待发货' && erpAgg.hasTracking) {
    s({ type: 'branch', text: '注意 → ERP状态待发货但已有快递单号，可能因退款导致状态未同步，按已发货处理' });
  }

  // 5.3：已发货（卖家已发货 / 交易成功 / 交易关闭 / 待发货但有快递单号）
  const isShipped = erpAgg.hasShipped || (erpStatus === '待发货' && erpAgg.hasTracking);
  s({ type: 'check', condition: `ERP有已发货行（卖家已发货/交易成功/交易关闭）或待发货+有快递`, result: isShipped });

  if (isShipped) {
    s({ type: 'branch', text: '进入「仅退款-已发货」流程 (flow-5.3)' });

    // 已拦截检测：同一快递已经被我们拦截过，直接上报等退回，不再重复拒绝+创建提醒
    if (cd.intercepted) {
      const it = cd.intercepted;
      s({ type: 'read', label: '拦截记录', value: `快递 ${it.tracking} 已拦截（首次工单 ${it.workOrderNum}，${it.executedAt ? it.executedAt.slice(0, 10) : '未知时间'}）` });
      s({ type: 'branch', text: '上报 → 快递已拦截等退回，请勿重复拒绝' });
      return fin(escalate(`快递 ${it.tracking} 已拦截，等待退回后退款（首次工单 ${it.workOrderNum}）`, {
        confidence: 'high',
        rulesApplied: [{ doc: 'flow-5.3', section: 'intercept', summary: '同快递已拦截→上报人工，等退回' }],
      }));
    }

    const packages = cd.logistics && cd.logistics.packages;
    s({ type: 'read', label: '物流包裹数', value: packages ? `${packages.length} 个` : '未获取' });

    // ERP双源：同时检查 ERP 物流文本（鲸灵有时不更新退回状态）
    // erpLogistics 格式：{ results: [{ tracking, logisticsText }, ...] }（多行）或旧格式 { logisticsText }（单行兼容）
    const erpLogResults = cd.erpLogistics && cd.erpLogistics.results
      ? cd.erpLogistics.results
      : (cd.erpLogistics && cd.erpLogistics.logisticsText ? [cd.erpLogistics] : []);
    const erpReturned = erpLogResults.some(r => r.logisticsText && RETURN_KEYWORDS.some(kw => r.logisticsText.includes(kw)));
    const erpLogSummary = erpLogResults.length ? erpLogResults.map(r => r.tracking || '?').join(',') : '';
    s({ type: 'read', label: 'ERP物流退回状态', value: erpLogResults.length ? (erpReturned ? `已退回（${erpLogSummary}）` : `未退回（${erpLogSummary}）`) : '未采集' });

    if (!packages || !packages.length) {
      if (erpReturned) {
        s({ type: 'branch', text: '同意退款 → 鲸灵物流未读到，但ERP物流显示已退回' });
        return fin(approve(
          'ERP物流显示已退回（鲸灵物流未读到）',
          [{ doc: 'flow-5.3', section: 'Step3', summary: 'ERP双源核查→已退回→同意退款' }]
        ));
      }
      s({ type: 'branch', text: '上报 → 已发货但无法读取物流信息' });
      return fin(escalate('已发货但无法读取物流信息'));
    }

    const pkgSummary = packages.map(p => {
      const text = p.text || '';
      const hasRet = RETURN_KEYWORDS.some(kw => text.includes(kw));
      const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
      return `${p.num || '?'}：${hasRet ? '已退回' : hasSigned ? '已签收' : '在途'}`;
    }).join('；');
    s({ type: 'read', label: '各包裹物流状态', value: pkgSummary });

    // 交叉核查：合并 ERP 全部 tracking（主品+赠品）+ 鲸灵全部包裹 tracking → 去重
    // 鲸灵工单详情页不显示赠品物流，因此必须从 ERP 补充赠品 tracking
    const mainShippedRows = getErpRows(cd, 'erpSearch').filter(r => ['卖家已发货', '交易成功', '交易关闭'].includes(r.status));
    const giftShippedRows = getErpRows(cd, 'giftErpSearch').filter(r => ['卖家已发货', '交易成功', '交易关闭'].includes(r.status));
    const totalShipRows = mainShippedRows.length + giftShippedRows.length;
    s({ type: 'read', label: 'ERP发货行总数', value: `${totalShipRows}（主品${mainShippedRows.length}+赠品${giftShippedRows.length}）` });

    // 提取所有已知 tracking：ERP主品 + ERP赠品 + 鲸灵物流包裹
    const erpTrackings = [...mainShippedRows, ...giftShippedRows]
      .flatMap(r => r.trackings || (r.tracking ? [r.tracking] : []));
    const jlTrackings = (packages || []).map(p => {
      const m = (p.text || '').match(/物流单号：\n(\S+)/);
      return m ? m[1] : null;
    }).filter(Boolean);
    const allTrackings = [...new Set([...erpTrackings, ...jlTrackings])];
    s({ type: 'read', label: '合并去重包裹', value: `${allTrackings.length}个（ERP:${erpTrackings.length} 鲸灵:${jlTrackings.length} 去重后:${allTrackings.length}）` });

    // 双源判断：鲸灵全部退回 OR ERP显示退回 → 同意
    // 采集完整性：去重后的包裹数 >= ERP发货行数
    const allJLReturned = allPackagesReturned(packages);
    const collectionComplete = totalShipRows <= 1 || allTrackings.length >= totalShipRows;
    s({ type: 'check', condition: `物流采集完整（去重${allTrackings.length}包裹 vs ERP ${totalShipRows}发货行）`, result: collectionComplete });

    if (allJLReturned && !collectionComplete) {
      s({ type: 'branch', text: `上报 → 去重后${allTrackings.length}个包裹，但ERP有${totalShipRows}行发货，采集不完整` });
      return fin(escalate(`物流采集不完整（去重后${allTrackings.length}/${totalShipRows}个包裹），无法确认全部退回，需人工核查`));
    }

    const allReturned = collectionComplete && (allJLReturned || erpReturned);
    s({ type: 'check', condition: `全部包裹有退回物流节点（鲸灵:${allJLReturned}，ERP:${erpReturned}，采集完整:${collectionComplete}）`, result: allReturned });

    if (allReturned) {
      s({ type: 'branch', text: `同意退款 → 全部包裹已退回（来源：${allJLReturned ? '鲸灵' : 'ERP'}）` });
      return fin(approve(
        `全部包裹物流显示已退回（${allJLReturned ? '鲸灵' : 'ERP'}物流）`,
        [{ doc: 'flow-5.3', section: 'Step3', summary: '所有包裹已退回→同意退款' }]
      ));
    }

    // 逐包裹分类：已签收 vs 在途（可拦截）
    const signedPkgs = [];
    const inTransitPkgs = [];
    const returnedPkgs = [];
    packages.forEach(pkg => {
      const text = pkg.text || '';
      const hasReturn = RETURN_KEYWORDS.some(kw => text.includes(kw));
      const hasSigned = SIGNED_KEYWORDS.some(kw => text.includes(kw));
      const numMatch = text.match(/物流单号[：:]\s*([A-Za-z0-9]+)/);
      const tracking = numMatch ? numMatch[1] : (pkg.num || '?');
      if (hasReturn) returnedPkgs.push(tracking);
      else if (hasSigned) signedPkgs.push(tracking);
      else inTransitPkgs.push(tracking);
    });
    s({ type: 'read', label: '包裹分类', value: `已签收:${signedPkgs.join(',') || '无'} 在途:${inTransitPkgs.join(',') || '无'} 已退回:${returnedPkgs.join(',') || '无'}` });

    const anySigned = signedPkgs.length > 0;

    if (anySigned) {
      // 有包裹已签收：如果同时有在途包裹 → escalate（需拦截在途件+已签收需退货退款）
      // 如果全部已签收 → reject（无件可拦截）
      if (inTransitPkgs.length > 0) {
        const desc = `已签收包裹（${signedPkgs.join('、')}）需买家申请退货退款；在途包裹（${inTransitPkgs.join('、')}）需拦截`;
        s({ type: 'branch', text: `上报 → 混合状态：${desc}` });
        return fin(escalate(desc, {
          rulesApplied: [{ doc: 'flow-5.3', section: 'Step4', summary: '部分签收+部分在途→拦截在途件+签收件走退货退款' }],
        }));
      }
      // 全部已签收，无在途件
      s({ type: 'branch', text: '拒绝退款 → 全部包裹已签收，无件可拦截，请申请退货退款' });
      return fin(reject(
        '商品已签收，无法拦截，请自行申请退货退款',
        [],
        [{ doc: 'flow-5.3', section: 'Step4', summary: '已签收→拒绝，让改退货退款' }]
      ));
    }

    // 驿站/快递柜待取件：货到了买家未取，应拒绝并通知拦截（驿站/快递柜可退件）
    const YIZHAN_KEYWORDS = ['驿站待取件', '已到驿站', '驿站自提', '到驿站', '投递驿站', '快递柜', '菜鸟驿站', '菜鸟', '代收点'];
    const anyAtYizhan = packages.some(pkg => {
      const text = pkg.text || '';
      const hasReturn = RETURN_KEYWORDS.some(kw => text.includes(kw));
      return !hasReturn && YIZHAN_KEYWORDS.some(kw => text.includes(kw));
    });
    s({ type: 'check', condition: '有包裹处于驿站待取件状态（未签收）', result: anyAtYizhan });

    if (anyAtYizhan) {
      s({ type: 'branch', text: '拒绝退款 → 商品已到驿站待取件，可联系驿站退件拦截' });
      return fin(reject(
        '商品已到驿站待取件，可联系快递公司/驿站拦截退件，拦截成功后退款',
        ['需创建快递拦截提醒'],
        [{ doc: 'flow-5.3', section: 'Step4', summary: '驿站待取件→拒绝+创建拦截提醒' }]
      ));
    }

    // 超时安全阀：已等待 ≥ REMIND_HOURS 仍未拦截成功 → 拒绝退款
    if (queueItem.firstWaitingAt) {
      const waitingDuration = (Date.now() - new Date(queueItem.firstWaitingAt).getTime()) / 3600000;
      if (waitingDuration >= REMIND_HOURS) {
        s({ type: 'branch', text: `超时安全阀触发 → 已等待${waitingDuration.toFixed(0)}h ≥ ${REMIND_HOURS}h，拒绝退款` });
        return fin(reject(
          `已等待${waitingDuration.toFixed(0)}h未拦截成功（阈值${REMIND_HOURS}h），拒绝退款，建议客户重新下单`,
          ['⚠️ 超时安全阀自动拒绝'],
          [{ doc: 'flow-5.3', section: 'Step4', summary: '等待超时→自动拒绝' }]
        ));
      }
    }

    // 时间分支：在途拦截件，剩余时效 > 距下次扫描时间 → 自动标记等待重查
    const remainingHours = queueItem.deadlineAt
      ? Math.max(0, (new Date(queueItem.deadlineAt).getTime() - Date.now()) / 3600000)
      : parseUrgencyHours(queueItem.urgency);
    const hoursUntilNextScan = queueItem.hoursUntilNextScan != null ? queueItem.hoursUntilNextScan : null;
    const remainingDisplay = remainingHours != null ? `${remainingHours.toFixed(1)}小时` : (queueItem.urgency || '未知');
    s({ type: 'read', label: '剩余时效', value: remainingDisplay });
    s({ type: 'read', label: '距下次扫描', value: hoursUntilNextScan != null ? `${hoursUntilNextScan.toFixed(1)}小时` : '未知' });

    const safeToWait = remainingHours != null && hoursUntilNextScan != null
      ? remainingHours > hoursUntilNextScan
      : null;  // 未知时不自动标记

    if (safeToWait === true) {
      s({ type: 'branch', text: `自动标记等待重查 → 在途拦截件，剩余${remainingHours.toFixed(1)}h > 下次扫描${hoursUntilNextScan.toFixed(1)}h` });
      return fin({
        ...escalate(
          `订单在途，剩余${remainingHours.toFixed(1)}h，等拦截退回后下次扫描自动重查`,
          {
            confidence: 'high',
            rulesApplied: [{ doc: 'flow-5.3', section: 'Step4', summary: '在途拦截件+剩余>下次扫描→自动等待重查' }],
          }
        ),
        waitingRescan: true,
      });
    }

    s({ type: 'branch', text: `拒绝退款 → 在途拦截件，剩余${remainingHours != null ? remainingHours.toFixed(1) : '?'}h，立即处理` });
    return fin(reject(
      '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
      ['需创建快递拦截提醒'],
      [{ doc: 'flow-5.3', section: 'Step4', summary: '在途拦截件+剩余时效不足→拒绝+创建拦截提醒' }]
    ));
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
    // 无快递单号时：多层判断是否为超售后期的无理由诉求（可自动拒绝）
    const reason = ticket.afterSaleReason || '';
    const remark = ticket.buyerRemark || '';

    s({ type: 'read', label: '售后原因', value: reason || '无' });
    s({ type: 'read', label: '售后说明', value: remark || '无' });

    // 平台标准非商责原因（无理由/个人原因类），无快递单号→直接拒绝
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
      return fin(d);
    }

    // 其他质量问题类（无法自动判断）→ 上报人工
    s({ type: 'branch', text: `上报 → 售后原因"${reason}"，无退货快递单号，需人工核查` });
    return fin(escalate(`退货退款无快递单号，售后原因：${reason || '未知'}，需人工核查`));
  }

  // 退货快递单号被多个工单共用 → 人工核查（防止一单两退）
  if (ticket.returnTrackingMultiUse) {
    const usedBy = ticket.returnTrackingUsedBy && ticket.returnTrackingUsedBy.length
      ? `，已关联工单：${ticket.returnTrackingUsedBy.join('、')}`
      : '';
    s({ type: 'check', condition: '退货快递单号是否被多个售后工单使用', result: true });
    s({ type: 'branch', text: `上报 → 快递单号多次使用${usedBy}，防止一单两退` });
    return fin(escalate(`退货快递单号已被多个工单共用${usedBy}，需人工核查防止重复退款`));
  }

  const aftersale = cd.erpAftersale;
  const hasRows = aftersale && aftersale.rows && aftersale.rows.length;
  s({ type: 'read', label: 'ERP售后入库记录', value: hasRows ? `${aftersale.rows.length} 条记录` : '无记录' });

  // 超时安全阀：已等待 ≥ REMIND_HOURS 仍未入库 → 拒绝退款
  if (queueItem.firstWaitingAt) {
    const waitingDuration = (Date.now() - new Date(queueItem.firstWaitingAt).getTime()) / 3600000;
    if (waitingDuration >= REMIND_HOURS) {
      s({ type: 'branch', text: `超时安全阀触发 → 已等待${waitingDuration.toFixed(0)}h ≥ ${REMIND_HOURS}h，拒绝退款` });
      return fin(reject(
        `已等待${waitingDuration.toFixed(0)}h未入库（阈值${REMIND_HOURS}h），拒绝退款，等入库后再处理`,
        ['⚠️ 超时安全阀自动拒绝'],
        [{ doc: 'flow-5.1', section: 'Step3', summary: '等待超时未入库→自动拒绝' }]
      ));
    }
  }

  // 场景B/C公共变量（无记录和有记录未入库两种情况共用相同判断逻辑）
  const buyerRemark = ticket.buyerRemark || '';
  const hasImages = !!(ticket.images && ticket.images.length);
  const remainingHoursWait = queueItem.deadlineAt
    ? Math.max(0, (new Date(queueItem.deadlineAt).getTime() - Date.now()) / 3600000)
    : parseUrgencyHours(queueItem.urgency);
  const hoursUntilNextScanWait = queueItem.hoursUntilNextScan != null ? queueItem.hoursUntilNextScan : null;
  const safeToWait = remainingHoursWait != null && hoursUntilNextScanWait != null
    ? remainingHoursWait > hoursUntilNextScanWait
    // fallback：deadlineAt 缺失时，用 urgency 文本估算，>12小时视为安全等待
    : (remainingHoursWait != null ? remainingHoursWait > 12 : null);

  if (!hasRows) {
    // 场景B自动等待：无入库记录 + 无售后说明 + 无图片 → 快递刚到未拆包，可自动等待
    s({ type: 'read', label: '售后说明', value: buyerRemark || '无' });
    s({ type: 'read', label: '售后图片', value: hasImages ? '有' : '无' });

    if (isRemarkEmpty(buyerRemark) && !hasImages && safeToWait === true) {
      const waitMsg = hoursUntilNextScanWait != null
        ? `剩余${remainingHoursWait != null ? remainingHoursWait.toFixed(1) : '?'}h > 下次扫描${hoursUntilNextScanWait.toFixed(1)}h`
        : `剩余${remainingHoursWait != null ? remainingHoursWait.toFixed(1) : '?'}h > 12h兜底阈值`;
      s({ type: 'branch', text: `自动标记等待重查 → 无入库记录+无说明+无图片，快递可能刚到未拆包，${waitMsg}` });
      return fin({
        ...escalate('退货快递在途或仓库待拆包，下次扫描自动重查', {
          confidence: 'high',
          rulesApplied: [{ doc: 'flow-5.1', section: 'Step3', summary: '无入库+无说明+无图片+剩余时效>下次扫描→自动等待重查' }],
        }),
        waitingRescan: true,
      });
    }

    s({ type: 'branch', text: '上报 → ERP售后工单无入库记录' });
    return fin(escalate('退货尚未入库确认，需人工核查'));
  }

  // 必须有「卖家已收到退货」状态
  const hasConfirmedReceipt = aftersale.rows.some(row =>
    row.goodsStatus && row.goodsStatus.includes('已收到退货')
  );
  const statusList = aftersale.rows.map(r => r.goodsStatus || '?').join('；');
  s({ type: 'check', condition: `存在「卖家已收到退货」状态的入库行（实际：${statusList}）`, result: hasConfirmedReceipt });

  if (!hasConfirmedReceipt) {
    // 场景C：有ERP记录但未入库（在途/已签收待仓库拆包）
    if (isRemarkEmpty(buyerRemark) && !hasImages && safeToWait === true) {
      const waitMsgC = hoursUntilNextScanWait != null
        ? `剩余${remainingHoursWait != null ? remainingHoursWait.toFixed(1) : '?'}h > 下次扫描${hoursUntilNextScanWait.toFixed(1)}h`
        : `剩余${remainingHoursWait != null ? remainingHoursWait.toFixed(1) : '?'}h > 12h兜底阈值`;
      s({ type: 'branch', text: `自动标记等待重查 → ERP有记录但未入库（状态：${statusList}）+无说明+无图片，在途或待仓库拆包，${waitMsgC}` });
      return fin({
        ...escalate('退货快递在途或仓库待拆包，下次扫描自动重查', {
          confidence: 'high',
          rulesApplied: [{ doc: 'flow-5.1', section: 'Step3', summary: '有ERP记录未入库+无说明+无图片+剩余时效>下次扫描→自动等待重查' }],
        }),
        waitingRescan: true,
      });
    }

    s({ type: 'branch', text: '上报 → 退货快递单存在，货物尚未入库确认' });
    return fin(escalate('退货尚未入库确认，需人工核查'));
  }

  // ── 收集入库明细 ─────────────────────────────────────────────────
  const receivedItems = [];  // { name, qtyGood, qtyBad }
  aftersale.rows.forEach(row => {
    (row.items || []).forEach(item => {
      const name = item.name || '';
      if (EXEMPT_ACCESSORY_KEYWORDS.some(kw => name.includes(kw))) return;
      receivedItems.push({
        name,
        qtyGood: parseInt(item.qtyGood) || 0,
        qtyBad: parseInt(item.qtyBad) || 0,
      });
    });
  });
  const totalGood = receivedItems.reduce((s, i) => s + i.qtyGood, 0);
  const totalBad = receivedItems.reduce((s, i) => s + i.qtyBad, 0);
  s({ type: 'read', label: '入库数量', value: `良品 ${totalGood} 件，次品 ${totalBad} 件` });

  // ── 次品检查：逐商品报告 ────────────────────────────────────────
  const badItems = receivedItems.filter(i => i.qtyBad > 0);
  if (badItems.length > 0) {
    const badDesc = badItems.map(i => `${i.name}（次品${i.qtyBad}件）`).join('、');
    s({ type: 'branch', text: `上报 → 次品：${badDesc}` });
    return fin(escalate(`退货含次品：${badDesc}，需人工处理`, {
      confidence: 'high',
      rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '次品→上报人工' }],
    }));
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
  } else {
    for (const pa of productArchives) {
      if (pa && pa.subItems) {
        for (const item of pa.subItems) {
          archiveSubItems.push({ ...item, _subOrderId: pa.subOrderId });
        }
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
      const shortDesc = shortItems.map(m =>
        m.status === 'missing' ? `${m.expected}（完全缺失）` : `${m.expected}（期望${m.expectedQty}件，入库${m.receivedQty}件）`
      ).join('、');
      s({ type: 'branch', text: `上报 → 主品入库不足：${shortDesc}` });
      return fin(escalate(`入库商品明细不符：${shortDesc}，需人工核查`, {
        rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '逐商品对比→主品不足→上报' }],
      }));
    }

    // 全部已知品匹配通过，但有未匹配的入库项 → 部分商品档案缺失
    if (unmatchedReceived.length > 0) {
      // 汇总已知品名称（用于人工快速判断）
      const knownNames = matchResults.map(m => {
        const short = (m.matched || m.expected || '').split(' ')[0].slice(0, 10);
        return `${short}×${m.receivedQty}`;
      }).join(' + ');
      const unknownNames = unmatchedReceived.map(i => {
        const short = (i.name || '').replace(/\s+/g, '').slice(0, 15);
        return `${short}×${i.qtyGood}`;
      }).join(' + ');
      const expectedSummary = matchResults.map(m => {
        const short = (m.expected || '').split(' ')[0].slice(0, 10);
        return `${short}×${m.expectedQty}`;
      }).join(' + ');
      s({ type: 'branch', text: `上报 → 入库含未匹配品类：${unknownNames}` });
      return fin(escalate(
        `需核对：已知品 ${knownNames}（期望 ${expectedSummary}），额外入库 ${unknownNames}`,
        {
          confidence: 'medium',
          rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '部分品类未匹配→上报' }],
          warnings: [`入库额外项：${unmatchedReceived.map(i => i.name).join('、')}`],
        }
      ));
    }

    // 全部品匹配通过且无未匹配项
    const totalExpected = matchResults.reduce((s, m) => s + m.expectedQty, 0);
    const summary = matchResults.map(m => `${m.expected}${m.expectedQty}件`).join('+');
    const surplus = totalGood - totalExpected;
    const surplusWarning = surplus > 0
      ? [`入库${totalGood}件比期望${totalExpected}件多${surplus}件（可能客户少申请了退货份数）`]
      : [];
    if (surplus > 0) {
      s({ type: 'read', label: '入库多于期望', value: `多${surplus}件（入库${totalGood} vs 期望${totalExpected}）` });
    }
    s({ type: 'branch', text: `同意退款 → 全部匹配（${summary}），入库${totalGood}件 ≥ 期望${totalExpected}件 (flow-5.1)` });
    const approveResult = approve(
      `入库商品明细核对通过（${summary}），良品${totalGood}件${surplus > 0 ? `（多${surplus}件，可能客户少申请）` : ''}`,
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
  s({ type: 'branch', text: `上报 → 无商品档案，无法核对应退数量，需人工核查 (flow-5.1)` });
  return fin(escalate(
    `无商品档案，无法核对应退数量（入库${totalGood}件，申请${expectedMainQty}件），需人工核查`,
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

  // ── hint 覆盖 ─────────────────────────────────────────────────
  const hint = queueItem.hint || '';
  if (hint) {
    s({ type: 'read', label: '用户评价指令', value: hint });
    const hintAction = parseHintAction(hint);
    s({ type: 'check', condition: '解析评价指令', result: hintAction ? `→ ${hintAction}` : '未识别' });
    if (hintAction) {
      s({ type: 'branch', text: `执行评价指令覆盖 → ${hintAction}` });
      return fin({
        action: hintAction,
        reason: `根据评价内容调整：${hint}`,
        confidence: 'high',
        rulesApplied: [],
        warnings: [],
        hinted: true,
      });
    }
    s({ type: 'branch', text: '评价指令未识别为操作，继续规则推理' });
  }

  const cd = sim.collectedData || {};
  const type = queueItem.type;
  const ticket = cd.ticket || {};

  // ── 平台终态检测（优先于一切校验）────────────────────────────────
  // 工单已终结（退款成功/用户取消）→ 无需操作，自动归档
  // 注意：此检测不依赖 erpSearch，必须在 validateCollectedData 之前执行
  const workOrderStatus = ticket.workOrderStatus || '';
  const TERMINAL_STATES = ['已退款', '退款成功', '已完成退款', '已关闭', '已撤销', '已取消', '用户已取消', '客服-已同意', '客服-已拒绝'];
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

  // ── 商责售后原因前置拦截（有罚款风险，一律人工）────────────────
  const afterSaleReason = ticket.afterSaleReason || '';
  const isMerchantFault = MERCHANT_FAULT_REASONS.some(kw => afterSaleReason.includes(kw));
  if (isMerchantFault) {
    s({ type: 'read', label: '售后原因', value: afterSaleReason });
    s({ type: 'branch', text: `上报 → 商责售后原因「${afterSaleReason}」，有罚款风险，需人工处理` });
    return fin(escalate(`商责售后原因「${afterSaleReason}」，需人工核实处理（商责有罚款风险）`, {
      rulesApplied: [{ doc: 'INDEX.md', section: '商责拦截', summary: '商责原因→上报人工' }],
    }));
  }

  // ── 换货 → 始终人工 ───────────────────────────────────────────
  if (type === '换货') {
    s({ type: 'branch', text: '换货类型固定上报人工 (flow-5.4)' });
    return fin(escalate('换货类型，需人工处理', {
      rulesApplied: [{ doc: 'flow-5.4', section: '总则', summary: '换货→上报人工' }],
    }));
  }

  // ── 路由到独立 flow 函数 ──────────────────────────────────────
  const ctx = { cd, ticket, queueItem, s, fin };

  if (type === '仅退款') return inferRefundOnly(ctx);
  if (type === '退货退款') return inferRefundReturn(ctx);

  s({ type: 'branch', text: `上报 → 工单类型未识别: ${type || '未知'}` });
  return fin(escalate(`工单类型未识别: ${type || '未知'}`));
}

module.exports = { inferDecision };
