'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const {
  openSingleAccountWorkOrder,
  runCli,
} = require('../../scripts/jl-steps/13-open-single-account-work-order');

const WORK_ORDER_NUM = '100001781188621717210';

test('按账号打开目标工单时只返回详情 tab，不在处理完成前导航首页读提醒', async () => {
  const calls = [];
  const account = { success: true, accountNum: '3', targetId: 'account-tab' };
  const urgent = [{ workOrderNum: WORK_ORDER_NUM, totalHours: 12 }];
  const openedTicket = {
    success: true,
    workOrderNum: WORK_ORDER_NUM,
    targetId: 'list-tab',
    newTargetId: 'detail-tab',
  };
  const dependencies = {
    openAccountFlow: async accountNum => {
      calls.push(['openAccountFlow', accountNum]);
      return account;
    },
    prepareAfterSaleList: async options => {
      calls.push(['prepareAfterSaleList', options]);
      return { success: true, targetId: 'list-tab', list: { urgent } };
    },
    clickWorkOrderAction: async (workOrderNum, options) => {
      calls.push(['clickWorkOrderAction', workOrderNum, options]);
      return openedTicket;
    },
    fetchAndCacheAlerts: async () => {
      calls.push(['fetchAndCacheAlerts']);
      throw new Error('步骤 13 不应在工单处理完成前导航首页');
    },
  };

  const result = await openSingleAccountWorkOrder('3', WORK_ORDER_NUM, {
    thresholdHours: 36,
    dependencies,
  });

  assert.deepEqual(calls, [
    ['openAccountFlow', '3'],
    ['prepareAfterSaleList', { targetId: 'account-tab', thresholdHours: 36 }],
    ['clickWorkOrderAction', WORK_ORDER_NUM, { targetId: 'list-tab' }],
  ]);
  assert.deepEqual(result, {
    success: true,
    account,
    list: { urgent },
    openedTicket,
    detailTargetId: 'detail-tab',
  });
});

test('打开账号返回失败时转为明确错误，并停止后续步骤', async () => {
  const calls = [];
  const dependencies = {
    openAccountFlow: async () => {
      calls.push('openAccountFlow');
      return { success: false, error: '账号凭证失效' };
    },
    prepareAfterSaleList: async () => calls.push('prepareAfterSaleList'),
    clickWorkOrderAction: async () => calls.push('clickWorkOrderAction'),
  };

  await assert.rejects(
    openSingleAccountWorkOrder('3', WORK_ORDER_NUM, { dependencies }),
    /打开账号失败: 账号凭证失效/
  );
  assert.deepEqual(calls, ['openAccountFlow']);
});

test('目标工单不在 urgent 列表时不点击', async () => {
  const calls = [];
  const dependencies = {
    openAccountFlow: async () => {
      calls.push('openAccountFlow');
      return { success: true, targetId: 'account-tab' };
    },
    prepareAfterSaleList: async () => {
      calls.push('prepareAfterSaleList');
      return {
        success: true,
        targetId: 'list-tab',
        list: { urgent: [{ workOrderNum: '100001781188621717211' }] },
      };
    },
    clickWorkOrderAction: async () => calls.push('clickWorkOrderAction'),
  };

  await assert.rejects(
    openSingleAccountWorkOrder('3', WORK_ORDER_NUM, { dependencies }),
    /目标工单不在48小时待处理列表/
  );
  assert.deepEqual(calls, ['openAccountFlow', 'prepareAfterSaleList']);
});

test('准备售后列表返回失败时明确报错，且不点击工单', async () => {
  const calls = [];
  const dependencies = {
    openAccountFlow: async () => {
      calls.push('openAccountFlow');
      return { success: true, targetId: 'account-tab' };
    },
    prepareAfterSaleList: async () => {
      calls.push('prepareAfterSaleList');
      return { success: false, error: '排序校验失败' };
    },
    clickWorkOrderAction: async () => calls.push('clickWorkOrderAction'),
  };

  await assert.rejects(
    openSingleAccountWorkOrder('3', WORK_ORDER_NUM, { dependencies }),
    /准备售后列表失败: 排序校验失败/
  );
  assert.deepEqual(calls, ['openAccountFlow', 'prepareAfterSaleList']);
});

test('点击工单返回失败时转为明确错误', async () => {
  const dependencies = {
    openAccountFlow: async () => ({ success: true, targetId: 'account-tab' }),
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: { urgent: [{ workOrderNum: WORK_ORDER_NUM }] },
    }),
    clickWorkOrderAction: async () => ({ success: false, error: '新标签页校验失败' }),
  };

  await assert.rejects(
    openSingleAccountWorkOrder('3', WORK_ORDER_NUM, { dependencies }),
    /打开目标工单失败: 新标签页校验失败/
  );
});

test('拒绝非法 accountNum，且不加载或调用依赖', async () => {
  await assert.rejects(
    openSingleAccountWorkOrder('abc', WORK_ORDER_NUM, {
      dependencies: {
        openAccountFlow: async () => assert.fail('不应调用 openAccountFlow'),
      },
    }),
    /缺少合法 accountNum/
  );
});

test('拒绝非法 workOrderNum，且不加载或调用依赖', async () => {
  await assert.rejects(
    openSingleAccountWorkOrder('3', 'bad-order', {
      dependencies: {
        openAccountFlow: async () => assert.fail('不应调用 openAccountFlow'),
      },
    }),
    /缺少合法 workOrderNum/
  );
});

test('CLI 按 accountNum、workOrderNum、thresholdHours 顺序执行，成功输出 JSON 并返回 0', async () => {
  const calls = [];
  const output = [];
  const dependencies = {
    openAccountFlow: async accountNum => {
      calls.push(['openAccountFlow', accountNum]);
      return { success: true, targetId: 'account-tab' };
    },
    prepareAfterSaleList: async options => {
      calls.push(['prepareAfterSaleList', options]);
      return {
        success: true,
        targetId: 'list-tab',
        list: { urgent: [{ workOrderNum: WORK_ORDER_NUM }] },
      };
    },
    clickWorkOrderAction: async (workOrderNum, options) => {
      calls.push(['clickWorkOrderAction', workOrderNum, options]);
      return { success: true, newTargetId: 'detail-tab' };
    },
  };

  const exitCode = await runCli(
    ['node', '13-open-single-account-work-order.js', '7', WORK_ORDER_NUM, '24'],
    { dependencies, writeLine: line => output.push(line) }
  );

  assert.equal(exitCode, 0);
  assert.equal(output.length, 1);
  assert.deepEqual(JSON.parse(output[0]), {
    success: true,
    account: { success: true, targetId: 'account-tab' },
    list: { urgent: [{ workOrderNum: WORK_ORDER_NUM }] },
    openedTicket: { success: true, newTargetId: 'detail-tab' },
    detailTargetId: 'detail-tab',
  });
  assert.deepEqual(calls, [
    ['openAccountFlow', '7'],
    ['prepareAfterSaleList', { targetId: 'account-tab', thresholdHours: 24 }],
    ['clickWorkOrderAction', WORK_ORDER_NUM, { targetId: 'list-tab' }],
  ]);
});

test('CLI 失败输出 JSON 并返回 1，且不继续后续步骤', async () => {
  const calls = [];
  const output = [];
  const dependencies = {
    openAccountFlow: async () => {
      calls.push('openAccountFlow');
      return { success: false, error: '登录态失效' };
    },
    prepareAfterSaleList: async () => calls.push('prepareAfterSaleList'),
    clickWorkOrderAction: async () => calls.push('clickWorkOrderAction'),
  };

  const exitCode = await runCli(
    ['node', '13-open-single-account-work-order.js', '7', WORK_ORDER_NUM],
    { dependencies, writeLine: line => output.push(line) }
  );

  assert.equal(exitCode, 1);
  assert.deepEqual(JSON.parse(output[0]), {
    success: false,
    error: '打开账号失败: 登录态失效',
  });
  assert.deepEqual(calls, ['openAccountFlow']);
});

test('仅导入模块时不会加载默认 CDP 依赖', () => {
  const projectRoot = path.join(__dirname, '../..');
  const probe = `
const Module = require('node:module');
const originalLoad = Module._load;
const blocked = new Set([
  './open-account',
  './11-prepare-after-sale-list',
  './12-click-work-order-action'
]);
Module._load = function(request, parent, isMain) {
  if (blocked.has(request)) throw new Error('默认依赖被提前加载: ' + request);
  return originalLoad.call(this, request, parent, isMain);
};
require('./scripts/jl-steps/13-open-single-account-work-order');
process.stdout.write('IMPORTED');
`;

  const result = spawnSync(process.execPath, ['-e', probe], {
    cwd: projectRoot,
    encoding: 'utf8',
  });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, 'IMPORTED');
});
