'use strict';

function normalizeAfterSaleType(value) {
  if (value == null) return null;
  const text = String(value).trim();
  if (!text) return null;
  if (text === '323') return '仅退款';
  if (text.includes('仅退款')) return '仅退款';
  if (text.includes('退货退款')) return '退货退款';
  if (text.includes('换货')) return '换货';
  if (text.includes('补寄')) return '补寄';
  return null;
}

module.exports = { normalizeAfterSaleType };
