'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');

const {
  SORT_OPTIONS,
  TARGET_SORT,
  pickTargetSortOption,
  selectOverdueSort,
} = require('../../scripts/jl-steps/09-select-overdue-sort');

test('排序下拉识别三种合法排序选项，并优先选择逾期时间最近', () => {
  assert.deepEqual(SORT_OPTIONS, [
    '按逾期时间最近排序',
    '按申请售后最近时间排序',
    '按申请售后最远时间排序',
  ]);

  const option = pickTargetSortOption([
    { text: '全部', rect: { centerX: 1, centerY: 1 } },
    { text: '按申请售后最近时间排序', rect: { centerX: 2, centerY: 2 } },
    { text: '按逾期时间最近排序', rect: { centerX: 3, centerY: 3 } },
    { text: '按申请售后最远时间排序', rect: { centerX: 4, centerY: 4 } },
  ]);

  assert.equal(option.text, TARGET_SORT);
  assert.deepEqual(option.rect, { centerX: 3, centerY: 3 });
});

test('排序下拉缺少三种合法排序项时不猜测坐标', () => {
  assert.throws(
    () => pickTargetSortOption([
      { text: '按逾期时间最近排序', rect: { centerX: 3, centerY: 3 } },
    ]),
    /排序下拉候选项不完整/
  );
});

test('当前已经是逾期时间最近排序时，步骤09直接通过且不强行打开下拉', async () => {
  const originalEval = cdp.eval;
  const originalCall = cdp.cdpCall;
  let calls = 0;

  cdp.eval = async () => ({
    success: true,
    value: TARGET_SORT,
    rect: { centerX: 100, centerY: 100 },
  });
  cdp.cdpCall = async () => {
    calls += 1;
  };

  try {
    const result = await selectOverdueSort({ targetId: 'list-tab' });
    assert.equal(result.success, true);
    assert.equal(result.alreadySelected, true);
    assert.equal(calls, 0);
  } finally {
    cdp.eval = originalEval;
    cdp.cdpCall = originalCall;
  }
});
