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
  addFrom(collectedData.giftErpSearch);
  return result;
}

module.exports = { extractShippedTrackings };
