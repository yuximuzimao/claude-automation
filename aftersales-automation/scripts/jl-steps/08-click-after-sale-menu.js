#!/usr/bin/env node
'use strict';
/**
 * 鲸灵 A1 — 原子步骤 08：点击左侧「售后工单」菜单进入列表。
 *
 * 本步只做一件事：在当前鲸灵后台页中找到左侧导航里的「售后工单」菜单，
 * 像真人一样 mouseMoved -> 短暂停顿 -> mousePressed -> 短暂停顿 -> mouseReleased。
 *
 * 约束：
 *   - 不因当前已经是 after-sale-list 而跳过点击。
 *   - 不处理工单、不排序、不执行任何审批动作。
 *   - 找不到唯一菜单时直接失败，绝不猜坐标。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));

const JL_DOMAIN = 'scrm.jlsupp.com';
const MOVE_DELAY_MS = 150;
const PRESS_DELAY_MS = 130;
const AFTER_CLICK_WAIT_MS = 800;

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

async function findAfterSaleMenuRect(targetId) {
  const result = await cdp.eval(targetId, `
(() => {
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

  const nav = document.querySelector('.nav');
  if (!nav) return { success: false, error: '未找到左侧导航 .nav' };

  const candidates = Array.from(nav.querySelectorAll('.nav-item, span, div'))
    .filter(visible)
    .filter(el => (el.innerText || el.textContent || '').trim() === '售后工单');

  const clickable = candidates
    .map(el => el.closest('.nav-item') || el)
    .filter(Boolean)
    .filter(visible);

  const unique = Array.from(new Set(clickable));
  if (unique.length !== 1) {
    return {
      success: false,
      error: '售后工单菜单匹配数量异常: ' + unique.length,
      matches: unique.map(el => ({
        text: (el.innerText || el.textContent || '').trim(),
        className: el.className || '',
        rect: rectOf(el)
      }))
    };
  }

  const el = unique[0];
  return {
    success: true,
    text: (el.innerText || el.textContent || '').trim(),
    className: el.className || '',
    rect: rectOf(el)
  };
})()
`);
  if (!result || !result.success) {
    throw new Error(result && result.error ? result.error : '未找到售后工单菜单');
  }
  return result;
}

async function clickAfterSaleMenu(options = {}) {
  const target = options.targetId
    ? { id: options.targetId }
    : await findJlPageTarget();
  const found = await findAfterSaleMenuRect(target.id);
  const { centerX: x, centerY: y } = found.rect;

  await cdp.cdpCall(target.id, 'Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x,
    y,
    button: 'none',
  });
  await sleep(MOVE_DELAY_MS);
  await cdp.cdpCall(target.id, 'Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
  await sleep(PRESS_DELAY_MS);
  await cdp.cdpCall(target.id, 'Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x,
    y,
    button: 'left',
    clickCount: 1,
  });
  await sleep(AFTER_CLICK_WAIT_MS);

  const info = await cdp.eval(
    target.id,
    `JSON.stringify({ url: location.href, title: document.title, readyState: document.readyState })`
  );
  return {
    success: true,
    targetId: target.id,
    clicked: {
      text: found.text,
      rect: found.rect,
      moveDelayMs: MOVE_DELAY_MS,
      pressDelayMs: PRESS_DELAY_MS,
    },
    page: info,
  };
}

if (require.main === module) {
  clickAfterSaleMenu()
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
  clickAfterSaleMenu,
  findAfterSaleMenuRect,
  MOVE_DELAY_MS,
  PRESS_DELAY_MS,
};
