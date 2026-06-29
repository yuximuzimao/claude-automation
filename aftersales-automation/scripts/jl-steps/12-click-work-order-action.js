#!/usr/bin/env node
'use strict';
/**
 * 鲸灵 A1 — 原子步骤 12：点击指定售后工单的「处理/查看/售后处理」按钮。
 *
 * 本步只做一件事：在当前售后列表页里按工单号精确定位该工单容器，
 * 用真实鼠标事件点击它自己的操作按钮，并校验新打开标签页属于该工单。
 *
 * 约束：
 *   - 找不到当前页目标工单时直接失败，不翻页、不猜测、不点第一个按钮。
 *   - 容器或按钮不唯一时直接失败。
 *   - 滚动使用 Input.dispatchMouseEvent 的 mouseWheel 事件。
 *   - 不在新标签页里继续点击任何按钮。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

const JL_DOMAIN = 'scrm.jlsupp.com';
const ACTION_TEXTS = ['处理', '查看', '售后处理'];
const MOVE_DELAY_MS = 150;
const PRESS_DELAY_MS = 130;
const AFTER_CLICK_WAIT_MS = 500;
const WHEEL_STEP_PX = 520;
const WHEEL_WAIT_MS = 180;
const MAX_WHEEL_STEPS = 16;
const NEW_TARGET_TIMEOUT_MS = 15000;
const NEW_TARGET_INTERVAL_MS = 500;
const VIEWPORT_MARGIN_PX = 12;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function assertWorkOrderNum(workOrderNum) {
  const value = String(workOrderNum || '').trim();
  if (!/^\d{10,}$/.test(value)) {
    throw new Error('缺少合法 workOrderNum');
  }
  return value;
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function countExactWorkOrder(text, workOrderNum) {
  const re = new RegExp(`(^|\\D)${escapeRegExp(workOrderNum)}(?=\\D|$)`, 'g');
  return (String(text || '').match(re) || []).length;
}

function extractWorkOrderNums(text) {
  return String(text || '').match(/100001\d{12,}/g) || [];
}

function findUniqueWorkOrderContainerData(containers, workOrderNum) {
  const order = assertWorkOrderNum(workOrderNum);
  const matches = (containers || []).filter(container => {
    const text = container && container.text ? container.text : '';
    return countExactWorkOrder(text, order) === 1;
  });

  if (matches.length === 0) {
    throw new Error(`工单号匹配数量异常: 0 (${order})`);
  }

  const uniqueContainers = matches.filter(container => {
    const nums = extractWorkOrderNums(container.text);
    return nums.length === 1 && nums[0] === order;
  });
  if (uniqueContainers.length !== 1) {
    throw new Error(`唯一工单容器匹配数量异常: ${uniqueContainers.length} (${order})`);
  }

  const container = uniqueContainers[0];
  if (container.actionButtonCount !== 1) {
    throw new Error(`处理按钮匹配数量异常: ${container.actionButtonCount} (${order})`);
  }
  return container;
}

function buildFindActionButtonExpression(workOrderNum) {
  const order = assertWorkOrderNum(workOrderNum);
  return `
(() => {
  const workOrderNum = ${JSON.stringify(order)};
  const actionTexts = ${JSON.stringify(ACTION_TEXTS)};

  function visible(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rect.width > 0 &&
      rect.height > 0;
  }
  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return {
      left: r.left,
      top: r.top,
      right: r.right,
      bottom: r.bottom,
      width: r.width,
      height: r.height,
      centerX: r.left + r.width / 2,
      centerY: r.top + r.height / 2
    };
  }
  function escapeRegExp(value) {
    return String(value);
  }
  function countExact(text, value) {
    const re = new RegExp('(^|\\\\D)' + escapeRegExp(value) + '(?=\\\\D|$)', 'g');
    return ((String(text || '').match(re)) || []).length;
  }
  function allWorkOrders(text) {
    return String(text || '').match(/100001\\d{12,}/g) || [];
  }
  function textOf(el) {
    return (el.innerText || el.textContent || '').trim();
  }
  function isActionButton(el) {
    if (!visible(el)) return false;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
    const text = textOf(el);
    return actionTexts.includes(text);
  }
  function actionButtonsIn(el) {
    return Array.from(el.querySelectorAll('button,[role="button"],a,.el-button'))
      .filter(isActionButton);
  }
  function summary(el, actionButtons, sourceText) {
    const btn = actionButtons[0] || null;
    return {
      elementText: textOf(el),
      sourceText,
      className: el.className || '',
      tagName: el.tagName,
      actionButtonCount: actionButtons.length,
      actionButtonText: btn ? textOf(btn) : null,
      rect: btn ? rectOf(btn) : null,
      containerRect: rectOf(el),
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        scrollX: window.scrollX,
        scrollY: window.scrollY
      }
    };
  }

  const exactNodeRe = new RegExp('(^|\\\\D)' + escapeRegExp(workOrderNum) + '(?=\\\\D|$)');
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (exactNodeRe.test(node.nodeValue || '')) textNodes.push(node);
  }
  if (textNodes.length === 0) {
    return JSON.stringify({
      success: false,
      error: '当前页未找到工单号文本节点: ' + workOrderNum,
      workOrderNum,
      textNodeCount: 0
    });
  }

  const candidateContainers = [];
  for (const node of textNodes) {
    let el = node.parentElement;
    while (el && el !== document.body && el !== document.documentElement) {
      const containerText = textOf(el);
      const nums = allWorkOrders(containerText);
      const actionButtons = actionButtonsIn(el);
      if (
        countExact(containerText, workOrderNum) === 1 &&
        nums.length === 1 &&
        nums[0] === workOrderNum &&
        actionButtons.length === 1
      ) {
        candidateContainers.push(summary(el, actionButtons, node.nodeValue || ''));
        break;
      }
      el = el.parentElement;
    }
  }

  const seen = new Set();
  const unique = [];
  for (const item of candidateContainers) {
    const key = [
      item.tagName,
      item.className,
      Math.round(item.containerRect.left),
      Math.round(item.containerRect.top),
      Math.round(item.containerRect.width),
      Math.round(item.containerRect.height)
    ].join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }

  if (unique.length !== 1) {
    return JSON.stringify({
      success: false,
      error: '唯一工单容器匹配数量异常: ' + unique.length,
      workOrderNum,
      textNodeCount: textNodes.length,
      candidates: unique.map(item => ({
        tagName: item.tagName,
        className: item.className,
        actionButtonText: item.actionButtonText,
        actionButtonCount: item.actionButtonCount,
        rect: item.rect,
        containerRect: item.containerRect
      }))
    });
  }

  return JSON.stringify({
    success: true,
    workOrderNum,
    textNodeCount: textNodes.length,
    button: unique[0]
  });
})()
`;
}

async function findJlPageTarget() {
  const targets = await cdp.getTargets();
  const pages = (targets || []).filter(t =>
    t &&
    t.type === 'page' &&
    t.url &&
    t.url.includes(JL_DOMAIN)
  );
  const page = pages.find(t => t.url.includes('after-sale-list')) || pages[0];
  if (!page) throw new Error('未找到鲸灵后台页面');
  return page;
}

async function findActionButton(targetId, workOrderNum) {
  const result = await cdp.eval(targetId, buildFindActionButtonExpression(workOrderNum));
  if (!result || !result.success) {
    throw new Error(result && result.error ? result.error : '未找到指定工单处理按钮');
  }
  return result.button;
}

function isRectInViewport(rect, viewport) {
  if (!rect || !viewport) return false;
  return rect.centerX >= VIEWPORT_MARGIN_PX &&
    rect.centerX <= viewport.width - VIEWPORT_MARGIN_PX &&
    rect.centerY >= VIEWPORT_MARGIN_PX &&
    rect.centerY <= viewport.height - VIEWPORT_MARGIN_PX;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

async function scrollActionButtonIntoView(targetId, workOrderNum) {
  let found = await findActionButton(targetId, workOrderNum);
  for (let step = 0; step <= MAX_WHEEL_STEPS; step++) {
    if (isRectInViewport(found.rect, found.viewport)) {
      return { button: found, wheelSteps: step };
    }
    const viewport = found.viewport || { width: 1200, height: 800 };
    const deltaY = found.rect && found.rect.centerY < VIEWPORT_MARGIN_PX
      ? -WHEEL_STEP_PX
      : WHEEL_STEP_PX;
    await cdp.dispatchMouseEvent(targetId, {
      type: 'mouseWheel',
      x: clamp(found.rect ? found.rect.centerX : viewport.width / 2, 20, viewport.width - 20),
      y: clamp(viewport.height / 2, 20, viewport.height - 20),
      deltaX: 0,
      deltaY,
      button: 'none',
    });
    await sleep(WHEEL_WAIT_MS);
    found = await findActionButton(targetId, workOrderNum);
  }
  throw new Error(`处理按钮滚动后仍不在可视区: ${workOrderNum}`);
}

async function clickPointLikeHuman(targetId, x, y) {
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mouseMoved',
    x,
    y,
    button: 'none',
  });
  await sleep(MOVE_DELAY_MS);
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mousePressed',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
  await sleep(PRESS_DELAY_MS);
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mouseReleased',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
}

async function readTargetPageInfo(targetId, workOrderNum, targetUrl) {
  try {
    const info = await cdp.eval(targetId, `
(() => {
  const bodyText = document.body ? (document.body.innerText || document.body.textContent || '') : '';
  const url = location.href;
  const title = document.title;
  const readyState = document.readyState;
  const workOrderNum = ${JSON.stringify(workOrderNum)};
  return JSON.stringify({
    url,
    title,
    readyState,
    urlContainsWorkOrderNum: url.includes(workOrderNum),
    bodyContainsWorkOrderNum: bodyText.includes(workOrderNum),
    containsWorkOrderNum: url.includes(workOrderNum) || bodyText.includes(workOrderNum)
  });
})()
`, 10000);
    return info;
  } catch (error) {
    return {
      url: targetUrl || '',
      title: '',
      readyState: '',
      urlContainsWorkOrderNum: String(targetUrl || '').includes(workOrderNum),
      bodyContainsWorkOrderNum: false,
      containsWorkOrderNum: String(targetUrl || '').includes(workOrderNum),
      readError: error.message,
    };
  }
}

async function waitForNewWorkOrderTarget(beforeTargetIds, workOrderNum, options = {}) {
  const timeoutMs = options.timeoutMs || NEW_TARGET_TIMEOUT_MS;
  const startedAt = Date.now();
  let lastNewTargets = [];

  while (Date.now() - startedAt <= timeoutMs) {
    const targets = await cdp.getTargets();
    const newTargets = (targets || []).filter(t =>
      t &&
      t.type === 'page' &&
      t.id &&
      !beforeTargetIds.has(t.id)
    );
    lastNewTargets = newTargets.map(t => ({
      id: t.id,
      url: t.url || '',
      title: t.title || '',
    }));

    for (const target of newTargets) {
      const page = await readTargetPageInfo(target.id, workOrderNum, target.url);
      if (page.containsWorkOrderNum) {
        return {
          newTargetId: target.id,
          url: page.url || target.url || '',
          title: page.title || target.title || '',
          readyState: page.readyState || '',
          containsWorkOrderNum: true,
          urlContainsWorkOrderNum: page.urlContainsWorkOrderNum,
          bodyContainsWorkOrderNum: page.bodyContainsWorkOrderNum,
        };
      }
    }
    await sleep(options.intervalMs || NEW_TARGET_INTERVAL_MS);
  }

  const error = new Error(`未识别到属于工单 ${workOrderNum} 的新标签页: ${JSON.stringify(lastNewTargets)}`);
  error.newTargetIds = lastNewTargets.map(target => target.id);
  throw error;
}

async function clickWorkOrderAction(workOrderNum, options = {}) {
  const order = assertWorkOrderNum(workOrderNum);
  const target = options.targetId
    ? { id: options.targetId }
    : await findJlPageTarget();

  const beforeTargets = await cdp.getTargets();
  const beforeTargetIds = new Set((beforeTargets || [])
    .filter(t => t && t.type === 'page' && t.id)
    .map(t => t.id));

  const positioned = await scrollActionButtonIntoView(target.id, order);
  const rect = positioned.button.rect;
  await clickPointLikeHuman(target.id, rect.centerX, rect.centerY);
  await sleep(AFTER_CLICK_WAIT_MS);

  const newTab = await waitForNewWorkOrderTarget(beforeTargetIds, order, options);
  return {
    success: true,
    targetId: target.id,
    workOrderNum: order,
    clicked: {
      text: positioned.button.actionButtonText,
      rect,
      wheelSteps: positioned.wheelSteps,
      moveDelayMs: MOVE_DELAY_MS,
      pressDelayMs: PRESS_DELAY_MS,
    },
    newTargetId: newTab.newTargetId,
    url: newTab.url,
    title: newTab.title,
    readyState: newTab.readyState,
    containsWorkOrderNum: newTab.containsWorkOrderNum,
    urlContainsWorkOrderNum: newTab.urlContainsWorkOrderNum,
    bodyContainsWorkOrderNum: newTab.bodyContainsWorkOrderNum,
  };
}

if (require.main === module) {
  clickWorkOrderAction(process.argv[2])
    .then(result => {
      console.log(JSON.stringify(result));
      process.exit(0);
    })
    .catch(error => {
      console.log(JSON.stringify({ success: false, error: error.message }));
      process.exit(1);
    });
}

module.exports = {
  clickWorkOrderAction,
  buildFindActionButtonExpression,
  findUniqueWorkOrderContainerData,
  countExactWorkOrder,
  extractWorkOrderNums,
  scrollActionButtonIntoView,
  waitForNewWorkOrderTarget,
  MOVE_DELAY_MS,
  PRESS_DELAY_MS,
};
