'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { WANWU_SCAN_HOURS, getNextWanwuScanAt } = require('../../wanwu/schedule');

test('万物固定每天07点和15点扫描', () => {
  assert.deepEqual([...WANWU_SCAN_HOURS], [7, 15]);
  assert.equal(getNextWanwuScanAt(new Date('2026-09-12T06:30:00+08:00')).getHours(), 7);
  assert.equal(getNextWanwuScanAt(new Date('2026-09-12T07:30:00+08:00')).getHours(), 15);
  const nextDay = getNextWanwuScanAt(new Date('2026-09-12T15:30:00+08:00'));
  assert.equal(nextDay.getDate(), 13);
  assert.equal(nextDay.getHours(), 7);
});
