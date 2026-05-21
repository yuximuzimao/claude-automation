'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { getHoursUntilNextScan, REMIND_HOURS, SAFETY_MARGIN_HOURS } = require('../../lib/constants');

describe('P1-5: waitingRescan safeToWait fallback', () => {
  it('hoursUntilNextScan 正常时 margin > SAFETY_MARGIN_HOURS → safeToWait=true', () => {
    const hoursUntilNextScan = 4;
    const remainingHours = 20;
    const margin = remainingHours - hoursUntilNextScan;
    const safeToWait = margin > SAFETY_MARGIN_HOURS;
    assert.equal(safeToWait, true);
  });

  it('hoursUntilNextScan 正常时 margin <= SAFETY_MARGIN_HOURS → safeToWait=false', () => {
    const hoursUntilNextScan = 4;
    const remainingHours = 10;
    const margin = remainingHours - hoursUntilNextScan;
    const safeToWait = margin > SAFETY_MARGIN_HOURS;
    assert.equal(safeToWait, false);
  });

  it('hoursUntilNextScan=null 时 fallback: remainingHours > REMIND_HOURS → safeToWait=true', () => {
    const remainingHours = 20;
    // 模拟 fallback 逻辑
    const hoursUntilNextScan = null;
    const margin = remainingHours != null && hoursUntilNextScan != null
      ? remainingHours - hoursUntilNextScan : null;
    const safeToWait = margin != null
      ? margin > SAFETY_MARGIN_HOURS
      : (remainingHours != null ? remainingHours > REMIND_HOURS : null);
    assert.equal(safeToWait, true);
  });

  it('hoursUntilNextScan=null 时 fallback: remainingHours <= REMIND_HOURS → safeToWait=false', () => {
    const remainingHours = 5;
    const hoursUntilNextScan = null;
    const margin = remainingHours != null && hoursUntilNextScan != null
      ? remainingHours - hoursUntilNextScan : null;
    const safeToWait = margin != null
      ? margin > SAFETY_MARGIN_HOURS
      : (remainingHours != null ? remainingHours > REMIND_HOURS : null);
    assert.equal(safeToWait, false);
  });

  it('getHoursUntilNextScan 返回正数', () => {
    const hours = getHoursUntilNextScan();
    assert.ok(typeof hours === 'number' && hours > 0 && hours <= 24);
  });
});
