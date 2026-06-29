#!/usr/bin/env node
'use strict';
/**
 * 鲸灵 A1 — 原子步骤 09：选择「按逾期时间最近排序」。
 *
 * 本步只做一件事：在售后工单列表页点击「排序规则」下拉框，
 * 再点击「按逾期时间最近排序」选项。
 *
 * 约束：
 *   - 不主动刷新、不导航。
 *   - 不处理工单、不点击列表中的操作按钮。
 *   - 下拉框或选项匹配不唯一时直接失败，绝不猜坐标。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

const JL_DOMAIN = 'scrm.jlsupp.com';
const SORT_PLACEHOLDER = '排序规则';
const TARGET_SORT = '按逾期时间最近排序';
const SORT_OPTIONS = [
  TARGET_SORT,
  '按申请售后最近时间排序',
  '按申请售后最远时间排序',
];
const MOVE_DELAY_MS = 150;
const DROPDOWN_PRESS_DELAY_MS = 120;
const OPTION_MOVE_DELAY_MS = 140;
const OPTION_PRESS_DELAY_MS = 130;
const AFTER_DROPDOWN_WAIT_MS = 300;
const AFTER_DROPDOWN_MAX_WAIT_MS = 1800; // dropdown DOM 渲染超时上限
const AFTER_SELECT_WAIT_MS = 700;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function findJlPageTarget() {
  const targets = await cdp.getTargets();
  const page = (targets || []).find(t =>
    t &&
    t.type === 'page' &&
    t.url &&
    t.url.includes(JL_DOMAIN)
  );
  if (!page) throw new Error('未找到鲸灵后台页面');
  return page;
}

function visibleAndRectHelpers() {
  return `
function visible(el) {
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
    width: r.width,
    height: r.height,
    centerX: r.left + r.width / 2,
    centerY: r.top + r.height / 2
  };
}
  `;
}

function pickTargetSortOption(options, targetSort = TARGET_SORT) {
  const candidates = (options || []).filter(option => option && SORT_OPTIONS.includes(option.text));
  const seen = new Set(candidates.map(option => option.text));
  const missing = SORT_OPTIONS.filter(text => !seen.has(text));
  if (missing.length) {
    throw new Error(`排序下拉候选项不完整: 缺少 ${missing.join(' / ')}`);
  }

  const matches = candidates.filter(option => option.text === targetSort);
  if (matches.length !== 1) {
    throw new Error(`${targetSort} 选项匹配数量异常: ${matches.length}`);
  }
  const match = matches[0];
  if (!match.rect || !Number.isFinite(match.rect.centerX) || !Number.isFinite(match.rect.centerY)) {
    throw new Error(`${targetSort} 选项缺少有效点击坐标`);
  }
  return match;
}

async function findSortDropdownRect(targetId) {
  const result = await cdp.eval(targetId, `
(() => {
  ${visibleAndRectHelpers()}
  const selector = 'input[placeholder="${SORT_PLACEHOLDER}"]';
  const inputs = Array.from(document.querySelectorAll(selector)).filter(visible);
  if (inputs.length !== 1) {
    return { success: false, error: '排序规则 input 匹配数量异常: ' + inputs.length };
  }
  const box = inputs[0].closest('.el-select') || inputs[0];
  return { success: true, value: inputs[0].value || '', rect: rectOf(box) };
})()
`);
  if (!result || !result.success) {
    throw new Error(result && result.error ? result.error : '未找到排序规则下拉框');
  }
  return result;
}

async function findSortOptionRect(targetId) {
  const result = await cdp.eval(targetId, `
(() => {
  ${visibleAndRectHelpers()}
  const sortOptions = ${JSON.stringify(SORT_OPTIONS)};
  const options = Array.from(document.querySelectorAll('.el-select-dropdown li.el-select-dropdown__item'))
    .filter(visible)
    .map(el => ({ text: (el.innerText || el.textContent || '').trim(), rect: rectOf(el) }))
    .filter(option => sortOptions.includes(option.text));
  return {
    success: true,
    options
  };
})()
  `);
  if (!result || !result.success) {
    const detail = result && result.visibleOptions ? ` ${JSON.stringify(result.visibleOptions)}` : '';
    throw new Error((result && result.error ? result.error : '未找到排序选项') + detail);
  }
  return pickTargetSortOption(result.options);
}

async function clickPoint(targetId, x, y, pressDelayMs) {
  await cdp.cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x,
    y,
    button: 'none',
  });
  await sleep(MOVE_DELAY_MS);
  await cdp.cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
  await sleep(pressDelayMs);
  await cdp.cdpCall(targetId, 'Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
}

async function selectOverdueSort(options = {}) {
  const target = options.targetId
    ? { id: options.targetId }
    : await findJlPageTarget();

  const before = await findSortDropdownRect(target.id);
  if (before.value === TARGET_SORT) {
    return {
      success: true,
      targetId: target.id,
      before,
      selected: { text: TARGET_SORT, alreadySelected: true },
      after: before,
      alreadySelected: true,
    };
  }

  await clickPoint(
    target.id,
    before.rect.centerX,
    before.rect.centerY,
    DROPDOWN_PRESS_DELAY_MS
  );
  await sleep(AFTER_DROPDOWN_WAIT_MS);

  // Element UI dropdown DOM 渲染有延迟，轮询直到选项出现或超时
  let option = null;
  const pollStart = Date.now();
  while (!option) {
    try {
      option = await findSortOptionRect(target.id);
    } catch(e) {
      if (Date.now() - pollStart >= AFTER_DROPDOWN_MAX_WAIT_MS) throw e;
      await sleep(200);
    }
  }
  await clickPoint(
    target.id,
    option.rect.centerX,
    option.rect.centerY,
    OPTION_PRESS_DELAY_MS
  );
  await sleep(AFTER_SELECT_WAIT_MS);

  const after = await findSortDropdownRect(target.id);
  if (after.value !== TARGET_SORT) {
    throw new Error(`排序选择后校验失败: ${after.value || '(空)'}`);
  }

  return {
    success: true,
    targetId: target.id,
    before,
    selected: option,
    after,
  };
}

if (require.main === module) {
  selectOverdueSort()
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
  selectOverdueSort,
  findSortDropdownRect,
  findSortOptionRect,
  pickTargetSortOption,
  SORT_OPTIONS,
  TARGET_SORT,
};
