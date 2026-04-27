'use strict';
// DEPRECATED: 已被 auto-match2.js 替代（分阶段批量处理，更稳定）。保留仅供参考，勿直接运行。
/**
 * 自动匹配主控：从 sku-records.json 读取未匹配且有识图数据的 SKU，
 * 按类型串行处理：单品 → remapSku，组合装 → mark-suite + copy-as-suite
 *
 * 运行: node lib/auto-match.js [--shop 澜泽] [--start <platformCode>]
 *   --start: 断点续跑，从指定 platformCode 开始（跳过之前的）
 */

const path = require('path');
const fs = require('fs');
const { remapSku } = require('./remap-sku');
const { main: markSuite } = require('./mark-suite');
const { main: copyAsSuite } = require('./copy-as-suite');
const { sleep } = require('./wait');

const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');
const LOG_PATH = path.join(__dirname, '../data/auto-match-log.json');

function loadLog() {
  if (!fs.existsSync(LOG_PATH)) return { done: [], failed: [] };
  return JSON.parse(fs.readFileSync(LOG_PATH, 'utf8'));
}

function saveLog(log) {
  fs.writeFileSync(LOG_PATH, JSON.stringify(log, null, 2));
}

async function main(erpId, shopName = '澜泽', startFrom = null) {
  const records = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
  const log = loadLog();
  const doneCodes = new Set(log.done);

  // 收集未匹配 + 有识图数据
  const todo = Object.values(records).filter(r =>
    r.shopName === shopName &&
    !r.erpCode &&
    r.recognition &&
    r.recognition.items &&
    r.recognition.items.length > 0 &&
    !doneCodes.has(r.platformCode)
  );

  // 断点续跑
  let startIdx = 0;
  if (startFrom) {
    const idx = todo.findIndex(r => r.platformCode === startFrom);
    if (idx >= 0) startIdx = idx;
  }

  const pending = todo.slice(startIdx);
  console.error(`[auto-match] 待处理: ${pending.length} 条（已完成 ${doneCodes.size}）`);

  for (let i = 0; i < pending.length; i++) {
    const r = pending[i];
    const { platformCode, productCode, recognition } = r;
    const type = recognition.type; // '单品' | '组合装'

    console.error(`\n[${i + 1}/${pending.length}] ${platformCode} | ${type}`);
    recognition.items.forEach(it => console.error(`  ${it.name}×${it.qty}`));

    try {
      if (type === '单品') {
        // 单品：只有一个 item，取其 name 作为 erpName
        const erpName = recognition.items[0].name;
        await remapSku(erpId, platformCode, erpName, { confirm: true });
        console.error(`[${platformCode}] ✅ 单品换绑完成: ${erpName}`);

      } else {
        // 组合装：mark-suite → copy-as-suite（串行）
        // mark-suite 需要 shopName 和 productCode
        await markSuite(erpId, shopName, productCode, platformCode);
        console.error(`[${platformCode}] ✅ mark-suite 完成，开始 copy-as-suite`);
        await sleep(2000);

        const products = recognition.items.map(it => ({ name: it.name, qty: it.qty }));
        await copyAsSuite(erpId, shopName, productCode, platformCode, products);
        console.error(`[${platformCode}] ✅ copy-as-suite 完成`);
      }

      log.done.push(platformCode);
      saveLog(log);

    } catch (e) {
      console.error(`[${platformCode}] ❌ 失败: ${e.message}`);
      log.failed.push({ platformCode, type, error: e.message, time: new Date().toISOString() });
      saveLog(log);
      // 失败后等5s继续下一条，不中断整个流程
      await sleep(5000);
    }

    // 每条处理完等3s让页面稳定
    await sleep(3000);
  }

  console.error(`\n[auto-match] 完成！成功: ${log.done.length}, 失败: ${log.failed.length}`);
  if (log.failed.length) {
    console.error('失败列表:');
    log.failed.forEach(f => console.error(`  ${f.platformCode}: ${f.error}`));
  }
}

module.exports = { main };

if (require.main === module) {
  const args = process.argv.slice(2);
  const shopIdx = args.indexOf('--shop');
  const shopName = shopIdx >= 0 ? args[shopIdx + 1] : '澜泽';
  const startIdx = args.indexOf('--start');
  const startFrom = startIdx >= 0 ? args[startIdx + 1] : null;
  const erpId = '075D3D5770F69781F17A14C418D00338';

  main(erpId, shopName, startFrom).catch(e => {
    console.error('[FATAL]', e.message);
    process.exit(1);
  });
}
