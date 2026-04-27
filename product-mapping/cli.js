'use strict';
const { getTargetIds } = require('./lib/targets');
const { ok, fail } = require('./lib/result');

const [,, cmd, ...args] = process.argv;

async function main() {
  // 解析参数
  const opts = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--shop') opts.shop = args[++i];
    else if (!opts._cmd) opts._cmd = args[i];
  }

  if (!cmd || cmd === '--help') {
    console.log(`用法:
  node cli.js targets                         — 检查浏览器标签页连通性
  node cli.js jl-products                     — 抓取鲸灵活动商品列表
  node cli.js km-read <货号>                  — 查商品对应表
  node cli.js km-archive <编码>               — 查商品档案V2
  node cli.js check --shop <店铺>             — 完整核查流程
  node cli.js visual-pending --shop <店铺>    — 列出待视觉核查的组合装
  node cli.js visual-ok <平台编码> "<描述>"   — 记录识图确认（图片内容正确）
  node cli.js visual-flag <平台编码> "<描述>" — 记录识图不符（图片内容有误）
  node cli.js match-test "<SKU名>" "<识图描述>" — 测试 SKU名 vs 识图结果比对
  node cli.js fetch-archive-names             — 读取档案V2普通商品全列表（含简称）
  node cli.js mark-suite <店铺> <货号> <平台编码> — 对应表标记套件（只处理单个SKU）
  node cli.js match --shop <店铺> [--limit N]    — 自动匹配（组合装套件+单品，任何异常立即停止）`);
    process.exit(0);
  }

  if (cmd === 'targets') {
    const ids = await getTargetIds();
    console.log(JSON.stringify(ok(ids), null, 2));
    return;
  }

  // ── 不需要浏览器连接的命令 ──
  if (cmd === 'visual-pending') {
    const fs = require('fs');
    const path = require('path');
    const { listPending } = require('./lib/visual');
    const shopName = opts.shop || '';
    // 找最新的报告文件
    const reportDir = path.join(__dirname, 'data/reports');
    const files = fs.existsSync(reportDir)
      ? fs.readdirSync(reportDir).filter(f => f.endsWith('.json') && (!shopName || f.includes(shopName))).sort()
      : [];
    if (!files.length) { console.error('未找到核查报告，请先运行 check'); process.exit(1); }
    const latestReport = JSON.parse(fs.readFileSync(path.join(reportDir, files[files.length - 1]), 'utf8'));
    const pending = listPending(latestReport);
    if (!pending.length) {
      console.log('✅ 无待视觉核查项');
    } else {
      console.log(`⚠️  待视觉核查 ${pending.length} 项:\n`);
      pending.forEach((item, i) => {
        console.log(`[${i + 1}] ${item.productCode} | ${item.skuName}`);
        console.log(`    platformCode: ${item.platformCode}`);
        console.log(`    erpName: ${item.erpName}`);
        console.log(`    imgPath: ${item.imgPath || '无本地图片'}`);
        console.log('');
      });
    }
    return;
  }

  if (cmd === 'visual-ok' || cmd === 'visual-flag') {
    const platformCode = args[0];
    const notes = args[1] || '';
    if (!platformCode) {
      console.error(`用法: node cli.js ${cmd} <平台编码> "<识图描述>"`);
      process.exit(1);
    }
    const { recordVerdict } = require('./lib/visual');
    const { matchSku } = require('./lib/match');
    const fs = require('fs');
    const path = require('path');
    // 从报告里找该 platformCode 的完整 SKU 对象
    let skuObj = null;
    const reportDir = path.join(__dirname, 'data/reports');
    const files = fs.existsSync(reportDir)
      ? fs.readdirSync(reportDir).filter(f => f.endsWith('.json')).sort()
      : [];
    if (files.length) {
      const report = JSON.parse(fs.readFileSync(path.join(reportDir, files[files.length - 1]), 'utf8'));
      skuObj = report.products.flatMap(p => p.skus).find(s => s.platformCode === platformCode) || null;
    }
    const verdict = cmd === 'visual-ok' ? 'ok' : 'mismatch';
    let matchDetail = '';
    if (notes && skuObj) {
      const r = matchSku(skuObj, notes);
      matchDetail = r.detail;
    }
    const saved = recordVerdict(platformCode, verdict, notes, matchDetail);
    console.log(JSON.stringify(ok({ platformCode, ...saved }), null, 2));
    return;
  }

  if (cmd === 'match-test') {
    const skuName = args[0];
    const visionText = args[1];
    if (!skuName || !visionText) {
      console.error('用法: node cli.js match-test "<SKU名>" "<识图描述>"');
      process.exit(1);
    }
    const { matchSku } = require('./lib/match');
    const result = matchSku(skuName, visionText);
    console.log(JSON.stringify(ok(result), null, 2));
    return;
  }

  // ── 其他命令需要浏览器标签页 ID ──
  const { jlId, erpId } = await getTargetIds();

  switch (cmd) {
    case 'sku-detail': {
      const spuId = args[0];
      if (!spuId) { console.error('用法: node cli.js sku-detail <spuId>'); process.exit(1); }
      const { getSkuDetails } = require('./lib/jl-sku-detail');
      const result = await getSkuDetails(jlId, spuId);
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'jl-products': {
      const { listActiveProducts } = require('./lib/jl-products');
      const result = await listActiveProducts(jlId);
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'km-read': {
      const productCode = args[0];
      if (!productCode) { console.error('用法: node cli.js km-read <货号>'); process.exit(1); }
      const { readCorrespondence } = require('./lib/correspondence');
      const shop = opts.shop || '';
      const result = await readCorrespondence(erpId, shop, productCode);
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'km-archive': {
      const code = args[0];
      if (!code) { console.error('用法: node cli.js km-archive <编码>'); process.exit(1); }
      const { queryArchive, initArchiveComp } = require('./lib/archive');
      await initArchiveComp(erpId);
      const result = await queryArchive(erpId, code);
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'check': {
      if (!opts.shop) { console.error('用法: node cli.js check --shop <店铺名>'); process.exit(1); }
      const { runCheck } = require('./lib/check');
      const result = await runCheck(jlId, erpId, opts.shop);
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'fetch-archive-names': {
      const { main: fetchMain } = require('./lib/fetch-archive-names');
      await fetchMain(erpId);
      break;
    }
    case 'mark-suite': {
      const [shopName, productCode, platformCode] = args;
      if (!shopName || !productCode || !platformCode) {
        console.error('用法: node cli.js mark-suite <店铺> <货号> <平台编码>');
        process.exit(1);
      }
      const { main: markMain } = require('./lib/mark-suite');
      await markMain(erpId, shopName, productCode, platformCode);
      break;
    }
    case 'match': {
      if (!opts.shop) { console.error('用法: node cli.js match --shop <店铺> [--limit N]'); process.exit(1); }
      const limitIdx = args.indexOf('--limit');
      const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1]) : Infinity;
      const { main: matchMain } = require('./lib/auto-match2');
      await matchMain(erpId, opts.shop, limit);
      break;
    }
    default:
      console.error(`未知命令: ${cmd}`);
      process.exit(1);
  }
}

main().catch(e => {
  console.error(JSON.stringify(fail(e)));
  process.exit(1);
});
