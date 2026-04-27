#!/usr/bin/env node
'use strict';

/**
 * 测试入口脚本
 *
 * 用法:
 *   node test.js l0
 *     — L0 基础设施检查（CDP/登录/CLI）
 *
 *   node test.js step <步骤ID> [参数...] [-n 次数]
 *     — 单步骤稳定性测试（默认10次，复原→执行→验证）
 *     — 步骤ID: JL-1, JL-2, PM-1, PA-1, ERP-1, ERP-2, ERP-3
 *     — 示例:
 *         node test.js step JL-1
 *         node test.js step JL-2 100001775181776855477
 *         node test.js step PM-1 kgoshkcx 默认
 *         node test.js step PA-1 1230-10
 *         node test.js step ERP-1 735871821
 *         node test.js step ERP-2 735871821
 *         node test.js step ERP-3 YT2585355836647
 *         node test.js step JL-2 100001775181776855477 -n 3
 *
 *   node test.js chain <工单号>
 *     — 运行5条数据链路（验证步骤间衔接，需工单有退货快递单号）
 *
 *   node test.js all <工单号>
 *     — 先执行 JL-2 获取上下文，再对所有只读步骤各跑10次
 */

const { getTargetIds } = require('./lib/targets');
const { runL0, runStepTest, runChainTest, printReport, runCmd } = require('./test/runner');
const { STEPS, READONLY_STEPS, CHAINS } = require('./test/schemas');

// 从队列中查出工单对应的 ERP 店铺名（accountNote 在 ticketData 里没有，需走队列）
function resolveShopName(workOrderNum) {
  try {
    const db = require('./lib/server/data');
    const { getErpShop } = require('./lib/erp/shop-map');
    const qi = db.readQueue().items.find(i => i.workOrderNum === workOrderNum);
    return (qi && qi.accountNote) ? getErpShop(qi.accountNote) : null;
  } catch (e) {
    process.stderr.write(`[test] resolveShopName(${workOrderNum}) 失败: ${e.message}\n`);
    return null;
  }
}

// 步骤参数的 CLI 用法说明
const STEP_USAGE = {
  'JL-1':   'node test.js step JL-1',
  'JL-2':   'node test.js step JL-2 <工单号>',
  'PM-1':   'node test.js step PM-1 <货号> [SKU属性] <ERP店铺名>',
  'PA-1':   'node test.js step PA-1 <specCode>',
  'ERP-1':  'node test.js step ERP-1 <子订单号>',
  'ERP-2':  'node test.js step ERP-2 <子订单号>  （自动先运行 erp-search）',
  'ERP-3':  'node test.js step ERP-3 <退货快递单号>',
  'JL-5':   'node test.js step JL-5 <工单号>',
  'JL-3':   'node test.js step JL-3 <工单号> <原因> <详情>  （预检，不提交）',
  'JL-4':   'node test.js step JL-4 <工单号>  （预检，不提交）',
  'NOTE-1': 'node test.js step NOTE-1 <工单号> <备注内容>  （预检，不提交）',
};

/**
 * 解析步骤 CLI args → args 对象
 * 步骤ID → args 字段映射
 */
function parseStepArgs(stepId, cliArgs) {
  switch (stepId) {
    case 'JL-1':   return {};
    case 'JL-2':   return { workOrderNum: cliArgs[0] };
    case 'PM-1':   return { sku: cliArgs[0], attr1: cliArgs[1], shopName: cliArgs[2] };
    case 'PA-1':   return { specCode: cliArgs[0] };
    case 'ERP-1':  return { subOrderId: cliArgs[0] };
    case 'ERP-2':  return { subOrderId: cliArgs[0], rowIndex: 0 };
    case 'ERP-3':  return { returnTracking: cliArgs[0] };
    case 'JL-5':   return { workOrderNum: cliArgs[0] };
    case 'JL-3':   return { workOrderNum: cliArgs[0], reason: cliArgs[1], detail: cliArgs[2] };
    case 'JL-4':   return { workOrderNum: cliArgs[0] };
    case 'NOTE-1': return { workOrderNum: cliArgs[0], note: cliArgs[1] };
    default: return {};
  }
}

/**
 * 从工单详情输出中提取各步骤所需参数
 */
function extractArgsFromTicket(ticketData) {
  const sub = ticketData.subOrders && ticketData.subOrders[0];
  const gift = ticketData.gifts && ticketData.gifts[0];
  return {
    // JL-2 已有
    workOrderNum: ticketData.workOrderNum,
    // PM-1 / PA-1
    sku: sub && sub.sku,
    attr1: sub && sub.attr1,
    // ERP-1 / ERP-2
    subOrderId: sub && sub.id,
    giftSubOrderId: gift && gift.id,
    // ERP-3
    returnTracking: ticketData.returnTracking,
  };
}

async function main() {
  const rawArgs = process.argv.slice(2).filter(a => a !== '--verbose');
  const cmd = rawArgs[0];

  if (!cmd) {
    printUsage();
    process.exit(0);
  }

  if (cmd === 'l0') {
    await runL0();
    return;
  }

  if (cmd === 'step') {
    await runSingleStep(rawArgs.slice(1));
    return;
  }

  if (cmd === 'chain') {
    await runChains(rawArgs.slice(1));
    return;
  }

  if (cmd === 'all') {
    await runAll(rawArgs.slice(1));
    return;
  }

  console.error(`未知命令: ${cmd}`);
  printUsage();
  process.exit(1);
}

// ── step 命令 ────────────────────────────────────────────────────────────────

async function runSingleStep(args) {
  const stepId = args[0];
  if (!stepId) {
    console.error('缺少步骤ID');
    printUsage();
    process.exit(1);
  }

  const stepDef = STEPS[stepId];
  if (!stepDef) {
    console.error(`未知步骤: ${stepId}`);
    console.log('可用步骤:', Object.keys(STEPS).join(', '));
    process.exit(1);
  }

  // 解析 -n 参数
  let n = 10;
  const nIdx = args.indexOf('-n');
  let stepCliArgs = args.slice(1);
  if (nIdx !== -1) {
    n = parseInt(args[nIdx + 1]) || 10;
    stepCliArgs = args.slice(1, nIdx);
  }

  // 检查必要参数
  const stepArgs = parseStepArgs(stepId, stepCliArgs);
  const missing = (stepDef.argKeys || []).filter(k => !stepArgs[k]);
  if (missing.length > 0) {
    console.error(`缺少参数: ${missing.join(', ')}`);
    console.log(`用法: ${STEP_USAGE[stepId]}`);
    process.exit(1);
  }

  const targets = await getTargetIds();
  const result = await runStepTest(stepDef, stepArgs, n, targets);
  printReport([result]);

  process.exit(result.passed === result.total ? 0 : 1);
}

// ── chain 命令 ───────────────────────────────────────────────────────────────

async function runChains(args) {
  const workOrderNum = args[0];
  if (!workOrderNum) {
    console.error('缺少工单号');
    console.log('用法: node test.js chain <工单号>');
    process.exit(1);
  }

  const targets = await getTargetIds();
  let allPassed = true;

  const chainShopName = resolveShopName(workOrderNum);

  for (const chain of CHAINS) {
    const passed = await runChainTest(chain, { workOrderNum, subOrderId: args[1], shopName: chainShopName }, targets, STEPS);
    if (!passed) allPassed = false;
  }

  console.log(allPassed ? '\n✅ 所有链路通过' : '\n⚠  部分链路未通过，见上方详情');
  process.exit(allPassed ? 0 : 1);
}

// ── all 命令 ─────────────────────────────────────────────────────────────────

async function runAll(args) {
  const workOrderNum = args[0];
  if (!workOrderNum) {
    console.error('缺少工单号');
    console.log('用法: node test.js all <工单号>');
    process.exit(1);
  }

  const targets = await getTargetIds();
  const results = [];

  // 先用 JL-2 拿工单上下文
  console.log('\n═══ 读取工单上下文 ═══');
  const ticketResult = runCmd(['read-ticket', workOrderNum]);
  if (!ticketResult.success) {
    console.error(`读取工单失败: ${ticketResult.error}`);
    process.exit(1);
  }
  const ctx = extractArgsFromTicket(ticketResult.data);
  ctx.shopName = resolveShopName(workOrderNum);
  console.log('✓ 工单详情读取成功');
  console.log(`  货号: ${ctx.sku}  attr1: ${ctx.attr1 || '(无)'}  店铺: ${ctx.shopName || '(未知)'}`);
  console.log(`  子订单号: ${ctx.subOrderId}`);
  console.log(`  退货快递: ${ctx.returnTracking || '(无，非退货退款类型)'}`);

  console.log('\n═══ L1 全步骤稳定性测试（各10次）═══');

  // 准备各步骤的参数
  const stepArgMap = {
    'JL-1': {},
    'JL-2': { workOrderNum },
    'PM-1': { sku: ctx.sku, attr1: ctx.attr1, shopName: ctx.shopName },
    'PA-1': null,   // 需要先跑 PM-1 得到 specCode，延迟获取
    'ERP-1': { subOrderId: ctx.subOrderId },
    'ERP-2': { subOrderId: ctx.subOrderId, rowIndex: 0 },
    'ERP-3': ctx.returnTracking ? { returnTracking: ctx.returnTracking } : null,
  };

  for (const stepId of READONLY_STEPS) {
    const stepDef = STEPS[stepId];

    // PA-1 需要先拿 PM-1 的结果
    if (stepId === 'PA-1') {
      if (!ctx.sku) {
        console.log(`\n⏭  ${stepId} 跳过（sku 为空）`);
        continue;
      }
      // 跑一次 PM-1 拿 specCode
      const pmResult = runCmd(ctx.shopName
        ? ['product-match', ctx.sku, ctx.attr1 || '', ctx.shopName]
        : ['product-match', ctx.sku, ctx.attr1].filter(Boolean));
      if (!pmResult.success || !pmResult.data.specCode) {
        console.log(`\n⏭  ${stepId} 跳过（PM-1 未返回 specCode）`);
        continue;
      }
      stepArgMap['PA-1'] = { specCode: pmResult.data.specCode };
    }

    // ERP-3 在没有退货快递单号时跳过
    if (stepId === 'ERP-3' && !stepArgMap['ERP-3']) {
      console.log(`\n⏭  ERP-3 跳过（工单无退货快递单号，非退货退款类型）`);
      continue;
    }

    const stepArgs = stepArgMap[stepId];
    if (!stepArgs) continue;

    // 检查必要参数
    const missing = (stepDef.argKeys || []).filter(k => !stepArgs[k]);
    if (missing.length > 0) {
      console.log(`\n⏭  ${stepId} 跳过（参数不足: ${missing.join(', ')}）`);
      continue;
    }

    const result = await runStepTest(stepDef, stepArgs, 10, targets);
    results.push(result);
  }

  printReport(results);

  const allPassed = results.every(r => r.passed >= r.total * 0.9);  // ≥90% 为通过
  console.log(allPassed ? '\n✅ 全步骤测试通过（≥9/10）' : '\n⚠  部分步骤低于9/10，需修复');
  process.exit(allPassed ? 0 : 1);
}

// ── 帮助 ─────────────────────────────────────────────────────────────────────

function printUsage() {
  console.log(`
鲸灵售后自动化 - 测试框架

用法:
  node test.js l0                              L0 基础设施检查
  node test.js step <步骤ID> [参数] [-n 次数]  单步骤稳定性测试
  node test.js chain <工单号>                   数据链路验证
  node test.js all <工单号>                     所有只读步骤各10次

步骤ID和用法:
${Object.entries(STEP_USAGE).map(([id, usage]) => `  ${usage}`).join('\n')}

每次测试循环：刷新页面复原 → 执行完整操作 → 验证输出结果
`);
}

main().catch(e => {
  console.error('测试出错:', e.message);
  if (process.env.VERBOSE) console.error(e.stack);
  process.exit(1);
});
