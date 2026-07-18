'use strict';

const path = require('node:path');

const REMINDER_SHORTCUT = '创建提醒';
const SHORTCUT_INPUT_PATH = path.join(
  process.env.HOME || '/Users/chat',
  '.qclaw/workspace-agent-a5b6f918/scripts/reminder/input.txt'
);

// 从 collectedData 中提取所有已发货包裹的快递单号（去重）
// 默认提取状态为 ['卖家已发货', '交易成功', '交易关闭'] 的行
function extractShippedTrackings(collectedData, statusFilter) {
  const filter = statusFilter || ['卖家已发货', '交易成功', '交易关闭'];
  const result = [];
  const seen = new Set();

  function addFrom(erpData) {
    const rows = (erpData && erpData.rows && erpData.rows.rows) || [];
    rows.forEach(row => {
      if (!filter.includes(row.status)) return;
      const ts = (row.trackings && row.trackings.length) ? row.trackings : (row.tracking ? [row.tracking] : []);
      ts.forEach(t => { if (t && !seen.has(t)) { seen.add(t); result.push(t); } });
    });
  }

  addFrom(collectedData.erpSearch);
  if (Array.isArray(collectedData.erpSearches)) {
    collectedData.erpSearches.forEach(s => addFrom(s));
  }
  addFrom(collectedData.giftErpSearch);
  if (Array.isArray(collectedData.giftErpSearches)) {
    collectedData.giftErpSearches.forEach(s => addFrom(s));
  }
  return result;
}

function buildReminderTitle(reminder) {
  if (typeof reminder === 'string') return reminder.trim();
  const data = reminder || {};
  if (!data.shipTracking) {
    return data.title || `【待人工】${data.accountName || '未知账号'}${data.workOrderNum ? ` 工单${data.workOrderNum}` : ''}`;
  }
  const carrierMap = { SF: '顺丰', YT: '圆通', ZT: '中通', STO: '申通', YD: '韵达', JD: '京东', EMS: '邮政', KY: '跨越', BS: '百世' };
  const carrierPrefix = String(data.shipTracking).match(/^([A-Z]{2,4})/)?.[1] || '';
  const carrier = carrierMap[carrierPrefix] || carrierPrefix;
  const parts = [`【拦截】${data.shipTracking}${carrier ? `（${carrier}）` : ''}`];
  parts.push(data.accountName || '未知账号');
  if (data.internalId) parts.push(`子订单${data.internalId}`);
  if (data.goodsName) parts.push(data.qty ? `${data.goodsName}×${data.qty}` : data.goodsName);
  return parts.join(' / ');
}

function buildReminderPayload(reminder, now = new Date()) {
  const title = buildReminderTitle(reminder).replace(/｜/g, '|');
  const remindAt = new Date(now.getTime() + 5 * 60 * 1000);
  const pad = value => String(value).padStart(2, '0');
  const time = `${remindAt.getFullYear()}-${pad(remindAt.getMonth() + 1)}-${pad(remindAt.getDate())} ${pad(remindAt.getHours())}:${pad(remindAt.getMinutes())}`;
  return `${title}｜${time}`;
}

// 通过用户的「创建提醒」快捷指令创建待办，统一在5分钟后提醒
function createReminder(reminder, dependencies = {}) {
  const { spawnSync } = require('node:child_process');
  const fs = require('node:fs');
  const run = dependencies.spawnSync || spawnSync;
  const write = dependencies.writeFileSync || fs.writeFileSync;
  const now = dependencies.now || new Date();
  const title = buildReminderTitle(reminder);
  try {
    write(SHORTCUT_INPUT_PATH, buildReminderPayload(reminder, now), 'utf8');
    const result = run('shortcuts', ['run', REMINDER_SHORTCUT], { timeout: 15000, encoding: 'utf8' });
    if (result.status === 0) return true;
  } catch {}
  try {
    run('osascript', ['-e',
      `display notification "${title.replace(/"/g, '\\"')}" with title "鲸灵售后预警" sound name "default"`
    ], { timeout: 5000, encoding: 'utf8' });
  } catch {}
  return false;
}

module.exports = {
  extractShippedTrackings,
  buildReminderTitle,
  buildReminderPayload,
  createReminder,
  REMINDER_SHORTCUT,
  SHORTCUT_INPUT_PATH,
};
