#!/usr/bin/env node
'use strict';

function assertAccountNum(accountNum) {
  const value = String(accountNum || '').trim();
  if (!/^\d+$/.test(value) || Number(value) < 1) {
    throw new Error('缺少合法 accountNum');
  }
  return value;
}

function assertWorkOrderNum(workOrderNum) {
  const value = String(workOrderNum || '').trim();
  if (!/^\d{10,}$/.test(value)) {
    throw new Error('缺少合法 workOrderNum');
  }
  return value;
}

function loadDefaultDependencies() {
  return {
    openAccountFlow: require('./open-account').openAccountFlow,
    prepareAfterSaleList: require('./11-prepare-after-sale-list').prepareAfterSaleList,
    clickWorkOrderAction: require('./12-click-work-order-action').clickWorkOrderAction,
  };
}

function stepError(stepName, result, fallback) {
  const detail = result && result.error ? result.error : fallback;
  return new Error(`${stepName}: ${detail}`);
}

async function openSingleAccountWorkOrder(accountNum, workOrderNum, options = {}) {
  const account = assertAccountNum(accountNum);
  const order = assertWorkOrderNum(workOrderNum);
  const thresholdHours = options.thresholdHours == null ? 48 : Number(options.thresholdHours);
  const dependencies = options.dependencies || loadDefaultDependencies();

  const accountResult = await dependencies.openAccountFlow(account);
  if (!accountResult || !accountResult.success) {
    throw stepError('打开账号失败', accountResult, '未知错误');
  }

  const prepared = await dependencies.prepareAfterSaleList({
    targetId: accountResult.targetId,
    thresholdHours,
  });
  if (!prepared || !prepared.success) {
    throw stepError('准备售后列表失败', prepared, '未知错误');
  }

  const urgent = prepared.list && Array.isArray(prepared.list.urgent)
    ? prepared.list.urgent
    : [];
  const targetTicket = urgent.find(ticket =>
    ticket && String(ticket.workOrderNum) === order
  );
  if (!targetTicket) {
    throw new Error('目标工单不在48小时待处理列表');
  }

  const openedTicket = await dependencies.clickWorkOrderAction(order, {
    targetId: prepared.targetId,
  });
  if (!openedTicket || !openedTicket.success) {
    throw stepError('打开目标工单失败', openedTicket, '未知错误');
  }

  return {
    success: true,
    account: accountResult,
    list: prepared.list,
    openedTicket,
    detailTargetId: openedTicket.newTargetId,
  };
}

async function runCli(argv, options = {}) {
  const writeLine = options.writeLine || console.log;
  const thresholdHours = argv[4] == null ? 48 : Number(argv[4]);

  try {
    const result = await openSingleAccountWorkOrder(argv[2], argv[3], {
      thresholdHours,
      dependencies: options.dependencies,
    });
    writeLine(JSON.stringify(result));
    return 0;
  } catch (error) {
    writeLine(JSON.stringify({ success: false, error: error.message }));
    return 1;
  }
}

if (require.main === module) {
  runCli(process.argv).then(exitCode => process.exit(exitCode));
}

module.exports = {
  openSingleAccountWorkOrder,
  runCli,
  assertAccountNum,
  assertWorkOrderNum,
  loadDefaultDependencies,
};
