#!/usr/bin/env node
'use strict';
/**
 * collect.js - 数据采集脚本（读真实浏览器数据，不做决策，不执行操作）
 *
 * 用法：
 *   node collect.js [--live] [--sim] [--account 3] [--limit 5]
 *
 *   --live      只采集 mode=live 的工单（默认两者都采）
 *   --sim       只采集 mode=sim 的工单
 *   --account N 只采集该账号编号的工单
 *   --limit N   最多采集 N 条
 */

const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');
const db = require('./lib/server/data');
const { getErpShop } = require('./lib/erp/shop-map');

const BASE = __dirname;
const SESSIONS_DIR = path.join(BASE, '../sessions');

// ── CLI 解析 ──────────────────────────────────────────────────────
const args = process.argv.slice(2);
const onlyLive = args.includes('--live');
const onlySim = args.includes('--sim');
const accountFilter = args.includes('--account') ? parseInt(args[args.indexOf('--account') + 1]) : null;
const limit = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1]) : null;
const workOrderNumFilter = args.includes('--workOrderNum') ? args[args.indexOf('--workOrderNum') + 1] : null;

function log(msg) {
  const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  process.stderr.write(`[${ts}] ${msg}\n`);
}

// ── 账号注入 ──────────────────────────────────────────────────────
let currentAccount = null;

function injectAccount(num) {
  // 每次都重新注入并 reload，保证 Vue app 用新 session（不跳过同账号，避免页面状态残留）
  log(`  切换账号 ${num}...`);
  const r = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(num)], {
    timeout: 30000, encoding: 'utf8',
  });
  if (r.status !== 0) throw new Error(`账号注入失败: ${r.stderr || r.stdout || '未知错误'}`);
  currentAccount = num;
  // 全页重载，让 Vue app 以新 session 重新初始化（串行等待完成）
  runCmd(['reload-jl']);
  // reload-jl 等列表文字出现即返回，但 Vue Router 还需要额外时间稳定
  // 用同步 sleep 确保 router 完全就绪再进行下一步采集
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 4000);
  log(`  账号 ${num} 稳定，开始采集`);
}

// ── CLI 命令执行 ──────────────────────────────────────────────────
function runCmd(args) {
  const r = spawnSync('node', [path.join(BASE, 'cli.js'), ...args.filter(Boolean)], {
    timeout: 90000, encoding: 'utf8', cwd: BASE,
  });
  try {
    return JSON.parse(r.stdout || '{}');
  } catch {
    return { success: false, error: r.stderr || r.stdout || '解析失败' };
  }
}

// ── 采集单条工单 ──────────────────────────────────────────────────
async function collectOne(item) {
  log(`采集 ${item.workOrderNum} (${item.accountNote}, mode=${item.mode})`);

  // 更新状态为 collecting
  db.updateQueueItem(item.id, { status: 'collecting', collectStartedAt: new Date().toISOString() });

  const collected = {
    ticket: null,
    erpSearch: null,
    erpLogistics: null,
    logistics: null,
    erpAftersale: null,
    productMatch: null,
    productArchive: null,
    giftErpSearch: null,
    giftProductMatch: null,
    giftProductArchive: null,
    collectErrors: [],
  };

  try {
    // Step 1: read-ticket
    const ticketRes = runCmd(['read-ticket', item.workOrderNum]);
    if (!ticketRes.success) {
      collected.collectErrors.push(`read-ticket: ${ticketRes.error}`);
    } else {
      collected.ticket = ticketRes.data;
    }

    const ticket = collected.ticket;
    const subOrder = ticket && ticket.subOrders && ticket.subOrders[0];
    const giftOrder = ticket && ticket.gifts && ticket.gifts[0];
    const subOrderId = subOrder && subOrder.id;
    const sku = subOrder && subOrder.sku;
    const attr1 = subOrder && subOrder.attr1;
    const returnTracking = ticket && ticket.returnTracking;
    const giftSubOrderId = giftOrder && giftOrder.id;

    // Step 2: erp-search（主订单）
    if (subOrderId) {
      const erpRes = runCmd(['erp-search', subOrderId]);
      if (!erpRes.success) {
        collected.collectErrors.push(`erp-search: ${erpRes.error}`);
      } else {
        collected.erpSearch = erpRes.data;
      }
    } else {
      collected.collectErrors.push('erp-search: 无子订单号，跳过');
    }

    // Step 3: logistics（鲸灵物流）
    const logRes = runCmd(['logistics', item.workOrderNum]);
    if (!logRes.success) {
      collected.collectErrors.push(`logistics: ${logRes.error}`);
    } else {
      collected.logistics = logRes.data;
    }

    // Step 4: product-match（商品对应表：展开货号行→抓规格属性→ERP编码）
    //          + product-archive（商品档案V2：查类型+子品数量）
    if (sku) {
      let shopName;
      try { shopName = getErpShop(item.accountNote); } catch (e) {
        collected.collectErrors.push(`product-match: 无法获取ERP店铺名 (${e.message})`);
      }
      if (!shopName) {
        collected.collectErrors.push('product-match: 跳过（无店铺名）');
      } else {
        const pmArgs = ['product-match', sku, attr1 || '', shopName];
        log(`  product-match: sku=${sku} attr1=${attr1 || '(空)'} shop=${shopName}`);
        const pmRes = runCmd(pmArgs);
        if (!pmRes.success) {
          collected.collectErrors.push(`product-match: ${pmRes.error}`);
          log(`  product-match 失败: ${pmRes.error}`);
        } else {
          collected.productMatch = pmRes.data;
          const exactMatch = pmRes.data && pmRes.data.specCode;
          const specCode = exactMatch || null;
          // ⚠️ matched=false 时禁止用 specCodes[0] 猜测——attr1 匹配失败说明规格属性与对应表不符，
          // 用第一条兜底 specCode 调 product-archive 会拿到错误的 subItemNum，导致数量判断出错。
          // 改为写入 collectErrors，由推理引擎感知并上报人工核查。
          if (pmRes.data && pmRes.data.matched === false) {
            const allCodes = (pmRes.data.specCodes || []).map(c => c.code).join(',');
            collected.collectErrors.push(`product-match: attr1「${attr1}」在对应表中未精确匹配，候选编码=[${allCodes}]，跳过 product-archive 以防 subItemNum 误判`);
            log(`  product-match attr1 未精确匹配，候选编码: ${allCodes}`);
          } else if (specCode) {
            log(`  product-match 成功: specCode=${specCode}`);
            const paRes = runCmd(['product-archive', specCode]);
            if (!paRes.success) {
              collected.collectErrors.push(`product-archive: ${paRes.error}`);
              log(`  product-archive 失败: ${paRes.error}`);
            } else {
              collected.productArchive = paRes.data;
              const pa = paRes.data;
              log(`  product-archive: type=${pa.type} subItemNum=${pa.subItemNum} title=${pa.title}`);
            }
          } else {
            collected.collectErrors.push('product-archive: product-match 未返回 specCode，跳过');
          }
        }
      } // end if shopName
    } else {
      collected.collectErrors.push('product-match: 无货号，跳过');
    }

    // Step 5: erp-aftersale（有退货快递单号时）
    if (returnTracking) {
      const afRes = runCmd(['erp-aftersale', returnTracking]);
      if (!afRes.success) {
        collected.collectErrors.push(`erp-aftersale: ${afRes.error}`);
      } else {
        collected.erpAftersale = afRes.data;
      }
    } else {
      collected.collectErrors.push('erp-aftersale: 无退货快递单号，跳过（非退货退款类型正常）');
    }

    // Step 5b: erp-logistics（遍历所有ERP行采集物流，作为双源核查依据）
    // 注：ERP物流需在 erp-search 成功后执行（页面已停留在ERP订单管理搜索结果页）
    // 失败时静默跳过——属于补充来源，不影响推理
    if (collected.erpSearch && !collected.collectErrors.some(e => e.startsWith('erp-search:'))) {
      const erpLogRes = runCmd(['erp-logistics-all']);
      if (erpLogRes.success) {
        collected.erpLogistics = erpLogRes.data;
      }
      // erp-logistics 失败不计入 collectErrors，推理引擎降级为只用鲸灵物流
    }

    // Step 6: 赠品 erp-search（如有赠品子订单号）
    if (giftSubOrderId) {
      const giftRes = runCmd(['erp-search', giftSubOrderId]);
      if (!giftRes.success) {
        collected.collectErrors.push(`erp-search(gift): ${giftRes.error}`);
      } else {
        collected.giftErpSearch = giftRes.data;
      }
    }

    // Step 6b: 赠品 product-match + product-archive（如有赠品 sku）
    const giftSku = giftOrder && giftOrder.sku;
    const giftAttr1 = giftOrder && giftOrder.attr1;
    if (giftSku) {
      let giftShopName;
      try { giftShopName = getErpShop(item.accountNote); } catch {}
      if (giftShopName) {
        const gpmArgs = ['product-match', giftSku, giftAttr1 || '', giftShopName];
        log(`  gift product-match: sku=${giftSku} attr1=${giftAttr1 || '(空)'} shop=${giftShopName}`);
        const gpmRes = runCmd(gpmArgs);
        if (!gpmRes.success) {
          collected.collectErrors.push(`product-match(gift): ${gpmRes.error}`);
        } else {
          collected.giftProductMatch = gpmRes.data;
          const giftSpecCode = gpmRes.data && gpmRes.data.specCode;
          if (gpmRes.data && gpmRes.data.matched === false) {
            const allCodes = (gpmRes.data.specCodes || []).map(c => c.code).join(',');
            collected.collectErrors.push(`product-match(gift): attr1「${giftAttr1}」未精确匹配，候选编码=[${allCodes}]`);
          } else if (giftSpecCode) {
            log(`  gift product-match 成功: specCode=${giftSpecCode}`);
            const gpaRes = runCmd(['product-archive', giftSpecCode]);
            if (!gpaRes.success) {
              collected.collectErrors.push(`product-archive(gift): ${gpaRes.error}`);
            } else {
              collected.giftProductArchive = gpaRes.data;
              log(`  gift product-archive: type=${gpaRes.data.type} subItemNum=${gpaRes.data.subItemNum}`);
            }
          }
        }
      }
    }

  } catch (e) {
    collected.collectErrors.push(`采集异常: ${e.message}`);
  }

  // 写入 simulations.jsonl
  // 重采时保留已有的 feedbackStatus / groundTruth（不重置用户已评价的标记）
  const existingSims = db.readSimulations();
  const prevSim = [...existingSims].reverse().find(s => s.queueItemId === item.id && s.id !== undefined);
  const inheritedFeedbackStatus = prevSim && prevSim.feedbackStatus !== 'pending' ? prevSim.feedbackStatus : 'pending';
  const inheritedGroundTruth = item.groundTruth || (prevSim && prevSim.groundTruth) || null;

  const sim = {
    id: `sim-${Date.now()}`,
    queueItemId: item.id,
    workOrderNum: item.workOrderNum,
    accountNote: item.accountNote,
    mode: item.mode,
    createdAt: new Date().toISOString(),
    collectedData: collected,
    decision: null,
    groundTruth: inheritedGroundTruth,
    feedbackStatus: inheritedFeedbackStatus,
  };
  db.appendSimulation(sim);

  // 更新队列状态
  db.updateQueueItem(item.id, { status: 'collected', collectDoneAt: new Date().toISOString() });

  log(`  ✓ 完成 (${collected.collectErrors.length} 个采集异常)`);
  return sim;
}

// ── 主流程 ────────────────────────────────────────────────────────
async function main() {
  const queue = db.readQueue();
  let items = queue.items.filter(i => i.status === 'pending');

  // 模式过滤
  if (onlyLive) items = items.filter(i => i.mode === 'live');
  if (onlySim) items = items.filter(i => i.mode === 'sim');
  if (accountFilter) items = items.filter(i => i.accountNum === accountFilter);
  if (workOrderNumFilter) items = items.filter(i => i.workOrderNum === workOrderNumFilter);
  if (limit) items = items.slice(0, limit);

  if (!items.length) {
    log('没有待采集的工单（status=pending）');
    process.exit(0);
  }

  log(`开始采集，共 ${items.length} 条工单`);

  // 按账号分组，减少切换次数
  const byAccount = {};
  items.forEach(item => {
    const key = item.accountNum || 0;
    if (!byAccount[key]) byAccount[key] = [];
    byAccount[key].push(item);
  });

  let success = 0, failed = 0;

  for (const [accountNum, accountItems] of Object.entries(byAccount)) {
    // 注入账号（accountNum=0 表示无账号信息，不注入）
    if (parseInt(accountNum) > 0) {
      try {
        injectAccount(parseInt(accountNum));
      } catch (e) {
        log(`  账号 ${accountNum} 注入失败，跳过该账号的 ${accountItems.length} 条工单: ${e.message}`);
        accountItems.forEach(item => {
          db.updateQueueItem(item.id, { status: 'pending' }); // 保持 pending 待下次重试
        });
        failed += accountItems.length;
        continue;
      }
    }

    for (const item of accountItems) {
      try {
        await collectOne(item);
        success++;
      } catch (e) {
        log(`  ✗ 采集失败: ${e.message}`);
        db.updateQueueItem(item.id, { status: 'pending' }); // 回退到 pending 待重试
        failed++;
      }
    }
  }

  log(`\n采集完成：成功 ${success}，失败 ${failed}`);
}

main().catch(e => {
  process.stderr.write(`collect.js 错误: ${e.message}\n`);
  process.exit(1);
});
