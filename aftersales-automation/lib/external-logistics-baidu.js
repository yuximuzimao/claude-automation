'use strict';

const cdp = require('./cdp');
const { hasConfirmedReturn, SIGNED_KEYWORDS, YIZHAN_KEYWORDS } = require('./constants');

const SHIPPED_STATUSES = new Set(['卖家已发货', '交易成功', '交易关闭']);
const NOT_PICKED_UP_KEYWORDS = ['未揽收', '等待揽收', '尚未揽收'];
const ACTUAL_SHIPMENT_RE = /揽收|在途|派件|签收|入站|到达|离开|运输/;
const BAIDU_SEARCH_URL = 'https://www.baidu.com/s?wd=';
const INITIAL_LOAD_WAIT_MS = 3000;
const MAX_WAIT_MS = 8000;
const POLL_MS = 400;
const POST_READ_HOLD_MS = 2000;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function trackingOfPackage(pkg) {
  const text = String(pkg && pkg.text || '');
  const match = text.match(/物流单号[：:]\s*\n?([A-Za-z0-9-]+)/);
  return match ? match[1] : null;
}

function getErpRows(cd, field) {
  if (field === 'erpSearch' && Array.isArray(cd && cd.erpSearches) && cd.erpSearches.length) {
    return cd.erpSearches.flatMap(item => item && item.rows && Array.isArray(item.rows.rows) ? item.rows.rows : []);
  }
  if (field === 'giftErpSearch' && Array.isArray(cd && cd.giftErpSearches) && cd.giftErpSearches.length) {
    return cd.giftErpSearches.flatMap(item => item && item.rows && Array.isArray(item.rows.rows) ? item.rows.rows : []);
  }
  const container = cd && cd[field];
  return container && container.rows && Array.isArray(container.rows.rows) ? container.rows.rows : [];
}

function getRowTrackings(row) {
  return [...new Set([
    ...(row && Array.isArray(row.trackings) ? row.trackings : []),
    row && row.tracking,
  ].filter(Boolean).map(String))];
}

function getBaseErpLogisticsResults(cd) {
  if (cd && cd.erpLogistics && Array.isArray(cd.erpLogistics.results)) return cd.erpLogistics.results;
  if (cd && cd.erpLogistics && cd.erpLogistics.logisticsText) return [cd.erpLogistics];
  return [];
}

function getExternalResults(cd) {
  return cd && cd.externalLogistics && Array.isArray(cd.externalLogistics.results)
    ? cd.externalLogistics.results
    : [];
}

function getKnownTextsForTracking(cd, tracking) {
  const texts = [];
  for (const result of getBaseErpLogisticsResults(cd)) {
    if (String(result && result.tracking || '') === tracking && result.logisticsText) texts.push(String(result.logisticsText));
  }
  for (const pkg of cd && cd.logistics && Array.isArray(cd.logistics.packages) ? cd.logistics.packages : []) {
    if (trackingOfPackage(pkg) === tracking && pkg.text) texts.push(String(pkg.text));
  }
  for (const result of getExternalResults(cd)) {
    if (String(result && result.tracking || '') === tracking && result.logisticsText) texts.push(String(result.logisticsText));
  }
  return texts;
}

function isLogisticsBlockingDecision(decision) {
  if (!decision || decision.action === 'approve') return false;
  if (decision.reasonCode === 'INTERCEPT_WAITING' ||
      decision.reasonCode === 'MIXED_SIGNED_INTERCEPTABLE' ||
      decision.reasonCode === 'SIGNED_NO_INTERCEPT') return true;
  return (decision.rulesApplied || []).some(rule => {
    if (!rule) return false;
    if (rule.doc === 'flow-5.3' && ['Step3', 'Step3-gift', 'Step4'].includes(rule.section)) return true;
    if (rule.doc === 'flow-5.2' && rule.section === 'Step4c') return true;
    return false;
  });
}

function findUnconfirmedShippedTrackings(cd) {
  const rows = [
    ...getErpRows(cd, 'erpSearch'),
    ...getErpRows(cd, 'giftErpSearch'),
  ];
  const candidates = [];
  for (const row of rows) {
    for (const tracking of getRowTrackings(row)) {
      const texts = getKnownTextsForTracking(cd, tracking);
      if (texts.some(hasConfirmedReturn)) continue;
      const hasActualShipment = texts.some(text => {
        let normalized = String(text || '');
        for (const keyword of NOT_PICKED_UP_KEYWORDS) normalized = normalized.split(keyword).join('');
        return ACTUAL_SHIPMENT_RE.test(normalized);
      });
      if (SHIPPED_STATUSES.has(row && row.status) || hasActualShipment) candidates.push(tracking);
    }
  }
  return [...new Set(candidates)];
}

function extractBaiduLogisticsCard(pageText) {
  const text = String(pageText || '');
  const marker = text.indexOf('物流追踪');
  if (marker < 0) return null;
  const start = Math.max(0, marker - 120);
  const tail = text.slice(start);
  const relativeMarker = marker - start;
  const endMarkers = ['\n官方电话', '\n我要寄件', '\n物流编号', '\n快递100', '\n大家还在搜'];
  const candidates = endMarkers
    .map(value => tail.indexOf(value, relativeMarker + 1))
    .filter(index => index > relativeMarker);
  const end = candidates.length ? Math.min(...candidates) : Math.min(tail.length, relativeMarker + 7000);
  const card = tail.slice(0, end).trim();
  if (!/\d{4}年\d{2}月\d{2}日/.test(card)) return null;
  return card;
}

function classifyCard(card) {
  const text = String(card || '');
  if (hasConfirmedReturn(text)) return 'returned';
  if (SIGNED_KEYWORDS.some(keyword => text.includes(keyword))) return 'signed';
  if (YIZHAN_KEYWORDS.some(keyword => text.includes(keyword))) return 'yizhan';
  return 'transit';
}

async function queryBaiduLogistics(tracking, customDependencies) {
  const deps = customDependencies || {
    createTarget: cdp.createTarget,
    eval: cdp.eval,
    closeTarget: cdp.closeTarget,
    sleep,
  };
  const normalized = String(tracking || '').trim();
  if (!/^[A-Za-z0-9-]{8,40}$/.test(normalized)) {
    return { success: false, tracking: normalized, error: '非法快递单号' };
  }

  let targetId = null;
  let closeError = null;
  try {
    const created = await deps.createTarget(`${BAIDU_SEARCH_URL}${encodeURIComponent(normalized)}`);
    targetId = created && (created.id || created.targetId);
    if (!targetId) return { success: false, tracking: normalized, error: '百度查询页已创建但缺少 targetId' };

    // 真实浏览器查询保留基础加载时间，避免刚开页就高频读取/秒关。
    await deps.sleep(INITIAL_LOAD_WAIT_MS);
    const startedAt = Date.now();
    while (Date.now() - startedAt < MAX_WAIT_MS) {
      const page = await deps.eval(targetId, `(() => ({
        title: document.title || '',
        href: location.href || '',
        query: (document.querySelector('#kw') && document.querySelector('#kw').value) || '',
        text: (document.body && document.body.innerText) || ''
      }))()`);
      const pageText = String(page && page.text || '');
      if (/安全验证|请输入验证码|网络不给力|访问异常/.test(pageText)) {
        return { success: false, tracking: normalized, error: '百度页面触发验证或访问异常' };
      }
      const queryMatches = String(page && page.query || '').trim() === normalized ||
        String(page && page.title || '').includes(normalized);
      if (queryMatches) {
        const card = extractBaiduLogisticsCard(pageText);
        if (card) {
          // 已读到稳定物流卡片后再停留片刻，避免成功命中后立即关闭页面。
          await deps.sleep(POST_READ_HOLD_MS);
          return {
            success: true,
            tracking: normalized,
            source: 'baidu',
            fetchedAt: new Date().toISOString(),
            logisticsText: card,
            status: classifyCard(card),
            confirmedReturn: hasConfirmedReturn(card),
          };
        }
      }
      await deps.sleep(POLL_MS);
    }
    return { success: false, tracking: normalized, error: '百度物流卡片等待超时' };
  } catch (error) {
    return { success: false, tracking: normalized, error: error && error.message || '百度物流查询失败' };
  } finally {
    if (targetId) {
      try {
        await deps.closeTarget(targetId);
      } catch (error) {
        closeError = error && error.message || '关闭百度查询页失败';
      }
    }
    if (closeError) console.warn(`[baidu-logistics] ${normalized} ${closeError}`);
  }
}

async function supplementBaiduLogisticsIfNeeded(collectedData, decision, options = {}) {
  const type = String(options.type || '').trim();
  if (type !== '仅退款' || !isLogisticsBlockingDecision(decision)) {
    return { attempted: false, changed: false, trackings: [] };
  }
  const candidates = findUnconfirmedShippedTrackings(collectedData);
  if (!candidates.length) return { attempted: false, changed: false, trackings: [] };

  const query = options.queryBaiduLogistics || queryBaiduLogistics;
  const external = {
    source: 'baidu',
    attemptedAt: new Date().toISOString(),
    attemptedTrackings: [...candidates],
    results: [],
    errors: [],
  };
  for (const tracking of candidates) {
    const result = await query(tracking);
    if (result && result.success) external.results.push(result);
    else external.errors.push({ tracking, error: result && result.error || '百度物流查询失败' });
  }
  collectedData.externalLogistics = external;
  return {
    attempted: true,
    changed: external.results.length > 0,
    confirmedReturn: external.results.some(result => result.confirmedReturn),
    trackings: candidates,
  };
}

function mergeExternalLogisticsIntoErp(cd) {
  const base = getBaseErpLogisticsResults(cd).map(result => ({ ...result }));
  const externalResults = getExternalResults(cd);
  if (!externalResults.length) return base;

  for (const ext of externalResults) {
    const tracking = String(ext && ext.tracking || '');
    if (!tracking || !ext.logisticsText) continue;
    const existing = base.find(result => String(result && result.tracking || '') === tracking);
    const supplement = `[百度物流补证]\n${ext.logisticsText}`;
    if (existing) {
      existing.logisticsText = [existing.logisticsText, supplement].filter(Boolean).join('\n\n');
      existing.externalSource = 'baidu';
    } else {
      base.push({
        tracking,
        logisticsText: supplement,
        externalSource: 'baidu',
      });
    }
  }
  return base;
}

module.exports = {
  extractBaiduLogisticsCard,
  classifyCard,
  findUnconfirmedShippedTrackings,
  isLogisticsBlockingDecision,
  queryBaiduLogistics,
  supplementBaiduLogisticsIfNeeded,
  mergeExternalLogisticsIntoErp,
};
