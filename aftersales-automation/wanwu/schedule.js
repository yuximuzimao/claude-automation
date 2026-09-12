'use strict';

const WANWU_SCAN_HOURS = Object.freeze([7, 15]);

function getNextWanwuScanAt(now = new Date(), hours = WANWU_SCAN_HOURS) {
  const sorted = [...hours].map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (sorted.length === 0) throw new Error('万物扫描时间不能为空');

  for (const hour of sorted) {
    const candidate = new Date(now);
    candidate.setHours(hour, 0, 0, 0);
    if (candidate.getTime() > now.getTime()) return candidate;
  }

  const next = new Date(now);
  next.setDate(next.getDate() + 1);
  next.setHours(sorted[0], 0, 0, 0);
  return next;
}

module.exports = { WANWU_SCAN_HOURS, getNextWanwuScanAt };
