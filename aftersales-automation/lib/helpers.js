'use strict';

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
  return result;
}

// 创建 Mac 提醒：优先 Reminders.app，失败降级为系统通知
function createReminder(title) {
  const { spawnSync } = require('child_process');
  const remind = spawnSync('osascript', ['-e',
    `tell application "Reminders" to make new reminder at end of list "待办" of default account with properties {name:"${title.replace(/"/g, '\\"')}"}`
  ], { timeout: 10000, encoding: 'utf8' });
  if (remind.status === 0) return true;
  spawnSync('osascript', ['-e',
    `display notification "${title.replace(/"/g, '\\"')}" with title "鲸灵售后预警" sound name "default"`
  ], { timeout: 5000 });
  return false;
}

module.exports = { extractShippedTrackings, createReminder };
