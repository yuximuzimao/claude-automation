#!/usr/bin/env node
'use strict';
/**
 * scan-all.js - 多账号工单巡检（只查询，写入 data/queue.json，不处理）
 *
 * 用法：
 *   node scan-all.js              扫描所有账号（accounts.json 里 file 存在的）
 *   node scan-all.js 1 3 5        只扫指定账号编号
 *   node scan-all.js --dry-run    不写 queue.json，只打印结果
 *
 * 输出：JSON 汇总 { scanned, urgent, errors, queueAdded }
 */

const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { addQueueItem, readQueue, updateQueueItem } = require('./lib/server/data');

const SESSIONS_DIR = path.join(__dirname, '../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');
const INJECT_DELAY_MS = 5000;  // 注入后等待浏览器稳定

const isDryRun = process.argv.includes('--dry-run');

function log(msg) {
  const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  process.stderr.write(`[${ts}] ${msg}\n`);
}

function injectAccount(num) {
  const r = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(num)], {
    timeout: 30000,
    encoding: 'utf8',
  });
  if (r.status !== 0) throw new Error(r.stderr || r.stdout || '注入失败');
  return true;
}

function listTickets() {
  const r = spawnSync('node', [path.join(__dirname, 'cli.js'), 'list'], {
    timeout: 120000,
    encoding: 'utf8',
    cwd: __dirname,
  });
  const out = JSON.parse(r.stdout || '{}');
  if (!out.success) throw new Error(out.error || 'list 失败');
  return {
    urgent: out.data.urgent || [],
    totalCollected: out.data.totalCollected || null,
    filterCount: out.data.filterCount || null,
    mismatchWarning: out.data.mismatchWarning || null,
  };
}

function writeToQueue(urgentTickets, isDryRun) {
  if (isDryRun || urgentTickets.length === 0) return { added: 0, updated: 0 };
  let added = 0, updated = 0, waitingReset = 0;
  const queue = readQueue();
  for (const t of urgentTickets) {
    const urgency = t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`;
    const deadlineAt = t.deadlineAt || new Date(Date.now() + (t.totalHours || 0) * 3600000).toISOString();
    // 找已存在的未完成工单（pending/collecting/inferring/simulated/waiting）
    const existing = queue.items.find(
      i => i.workOrderNum === t.workOrderNum && i.status !== 'done'
    );
    if (existing) {
      if (existing.status === 'waiting') {
        // 等待重查工单：重置为 pending 触发重新采集推理
        updateQueueItem(existing.id, { status: 'pending', urgency, deadlineAt });
        waitingReset++;
      } else {
        // 其他状态：只刷新 urgency 和 deadlineAt
        updateQueueItem(existing.id, { urgency, deadlineAt });
        updated++;
      }
    } else {
      const item = addQueueItem({
        workOrderNum: t.workOrderNum,
        accountNum: t.num,
        accountNote: t.note,
        mode: 'live',
        source: 'scan',
        type: t.type || null,
        urgency,
        deadlineAt,
      });
      if (item) added++;
    }
  }
  return { added, updated, waitingReset };
}

async function main() {
  const accounts = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));

  // 确定要扫的账号编号
  const specifiedNums = process.argv.slice(2)
    .filter(a => /^\d+$/.test(a))
    .map(Number);

  const numsToScan = specifiedNums.length > 0
    ? specifiedNums
    : Object.keys(accounts)
        .map(Number)
        .filter(n => {
          const a = accounts[String(n)];
          return a && fs.existsSync(path.join(SESSIONS_DIR, a.file));
        })
        .sort((a, b) => a - b);

  log(`开始巡检，共 ${numsToScan.length} 个账号${isDryRun ? '（dry-run）' : ''}`);

  // 输出初始账号列表（供 op-queue 解析后广播扫描进度）
  process.stderr.write(`SCAN_PROGRESS:${JSON.stringify({
    type: 'init',
    accounts: numsToScan.map(n => ({
      num: n,
      note: (accounts[String(n)] && (accounts[String(n)].note || accounts[String(n)].name)) || `账号${n}`,
      status: 'pending',
    })),
  })}\n`);

  const result = {
    time: new Date().toISOString(),
    scanned: [],
    urgent: [],
    errors: [],
    queueAdded: 0,
  };

  for (let i = 0; i < numsToScan.length; i++) {
    const num = numsToScan[i];
    const account = accounts[String(num)];
    const note = account?.note || account?.name || `账号${num}`;

    log(`[${i + 1}/${numsToScan.length}] 账号${num} ${note}`);
    process.stderr.write(`SCAN_PROGRESS:${JSON.stringify({ type: 'start', num, note, index: i + 1, total: numsToScan.length })}\n`);

    try {
      injectAccount(num);
      log(`  注入完成，等待 ${INJECT_DELAY_MS / 1000}s...`);
      await new Promise(r => setTimeout(r, INJECT_DELAY_MS));

      const listResult = listTickets();
      const tickets = listResult.urgent;
      log(`  发现 ${tickets.length} 张紧急工单（共采集 ${listResult.totalCollected || '?'} 条，筛选器 ${listResult.filterCount || '?'} 条）`);
      if (listResult.mismatchWarning) {
        log(`  ⚠️ ${listResult.mismatchWarning}`);
      }

      result.scanned.push({ num, note, count: tickets.length, totalCollected: listResult.totalCollected, filterCount: listResult.filterCount });
      process.stderr.write(`SCAN_PROGRESS:${JSON.stringify({ type: 'done', num, note, index: i + 1, total: numsToScan.length, count: tickets.length })}\n`);

      for (const t of tickets) {
        result.urgent.push({ num, note, ...t });
      }

    } catch (e) {
      log(`  ❌ 错误: ${e.message}`);
      process.stderr.write(`SCAN_PROGRESS:${JSON.stringify({ type: 'error', num, note, index: i + 1, total: numsToScan.length, error: e.message })}\n`);
      result.errors.push({ num, note, error: e.message });
    }
  }

  // 写入 data/queue.json（去重，live 模式）
  if (!isDryRun && result.urgent.length > 0) {
    try {
      const { added, updated, waitingReset } = writeToQueue(result.urgent, isDryRun);
      result.queueAdded = added;
      result.queueUpdated = updated;
      result.waitingReset = waitingReset || 0;
      log(`✅ 已写入 queue.json（新增 ${added} 条，时效更新 ${updated} 条，等待重查重置 ${waitingReset || 0} 条）`);
    } catch (e) {
      log(`⚠️ 写入 queue.json 失败: ${e.message}`);
    }
  }

  // 汇总输出
  log('\n=== 巡检完成 ===');
  if (result.urgent.length === 0) {
    log('无紧急工单');
  } else {
    log(`共 ${result.urgent.length} 张紧急工单：`);
    for (const t of result.urgent) {
      const timeStr = t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`;
      log(`  [${t.note}] ${t.workOrderNum} | ${t.type} | 剩余${timeStr}`);
    }
  }
  if (result.errors.length > 0) {
    log(`\n❌ ${result.errors.length} 个账号出错：`);
    result.errors.forEach(e => log(`  账号${e.num} ${e.note}: ${e.error}`));
  }

  console.log(JSON.stringify(result, null, 2));
}

main().catch(e => {
  console.error(JSON.stringify({ success: false, error: e.message }));
  process.exit(1);
});
