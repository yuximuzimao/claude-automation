'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  extractShippedTrackings,
  buildReminderTitle,
  buildReminderPayload,
  createReminder,
  SHORTCUT_INPUT_PATH,
} = require('../lib/helpers');

test('快递单号提取覆盖主品和赠品的多子订单搜索结果', () => {
  const row = tracking => ({ rows: { rows: [{ status: '卖家已发货', tracking }] } });
  assert.deepEqual(extractShippedTrackings({
    erpSearches: [row('YT-MAIN-1'), row('YT-MAIN-2')],
    giftErpSearches: [row('YT-GIFT-1')],
  }), ['YT-MAIN-1', 'YT-MAIN-2', 'YT-GIFT-1']);
});

test('快捷指令待办使用当前时间五分钟后的提醒时间', () => {
  const now = new Date(2026, 6, 18, 9, 0, 0);
  assert.equal(
    buildReminderPayload('有快递需要拦截', now),
    '有快递需要拦截｜2026-07-18 09:05'
  );
});

test('结构化拦截信息可生成待办标题', () => {
  assert.equal(buildReminderTitle({
    accountName: '测试店铺',
    shipTracking: 'YT123456',
    internalId: 'SUB-1',
    goodsName: '测试商品',
    qty: '2',
  }), '【拦截】YT123456（圆通） / 测试店铺 / 子订单SUB-1 / 测试商品×2');
});

test('创建提醒写入快捷指令输入文件并运行“创建提醒”', () => {
  const writes = [];
  const runs = [];
  const ok = createReminder('售后系统有待办', {
    now: new Date(2026, 6, 18, 9, 0, 0),
    writeFileSync: (...args) => writes.push(args),
    spawnSync: (...args) => {
      runs.push(args);
      return { status: 0, stdout: '', stderr: '' };
    },
  });

  assert.equal(ok, true);
  assert.deepEqual(writes, [[SHORTCUT_INPUT_PATH, '售后系统有待办｜2026-07-18 09:05', 'utf8']]);
  assert.equal(runs[0][0], 'shortcuts');
  assert.deepEqual(runs[0][1], ['run', '创建提醒']);
});

test('快捷指令失败且系统通知也异常时只返回失败，不中断扫描', () => {
  const ok = createReminder('售后系统有待办', {
    now: new Date(2026, 6, 18, 9, 0, 0),
    writeFileSync: () => {},
    spawnSync: command => {
      if (command === 'shortcuts') return { status: 1 };
      throw new Error('系统通知不可用');
    },
  });

  assert.equal(ok, false);
});
