#!/usr/bin/env node
/**
 * SKU 库存计算器 CLI
 *
 * 命令:
 *   node cli.js parse [excel文件]         解析加购 Excel（缺省自动找桌面最新 xlsx）→ data/cart-adds.json
 *   node cli.js calculate                 执行分配算法 → data/allocation-result.json
 *   node cli.js report [--output <路径>]  生成 Excel 报告（默认输出到桌面）
 *   node cli.js run [excel文件]           全流程一键执行
 */

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const DATA_DIR   = path.join(__dirname, 'data');
const DESKTOP    = path.join(os.homedir(), 'Desktop');

/** 从桌面找最新的 .xlsx 文件（排除已生成的库存分配报告） */
function findLatestDesktopExcel() {
  const files = fs.readdirSync(DESKTOP)
    .filter(f => f.endsWith('.xlsx') && !f.startsWith('库存分配'))
    .map(f => ({ name: f, mtime: fs.statSync(path.join(DESKTOP, f)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  if (!files.length) fail('桌面上没有找到 .xlsx 文件，请把加购 Excel 放到桌面');
  return path.join(DESKTOP, files[0].name);
}

function ok(data)   { console.log(JSON.stringify({ status: 'ok',    ...data  }, null, 2)); }
function fail(msg)  { console.error(JSON.stringify({ status: 'error', message: msg }, null, 2)); process.exit(1); }

function readJson(file) {
  const full = path.join(DATA_DIR, file);
  if (!fs.existsSync(full)) fail(`数据文件不存在: ${full}，请先执行前置步骤`);
  return JSON.parse(fs.readFileSync(full, 'utf-8'));
}

// ─── parse ───────────────────────────────────────────────────────────────────
function cmdParse(excelPath) {
  const { parseAndSave } = require('./lib/parse-cart-adds');
  const absPath = excelPath ? path.resolve(excelPath) : findLatestDesktopExcel();
  console.log(`解析加购数据: ${absPath}`);

  const { skus, warnings } = parseAndSave(absPath);
  for (const w of warnings) console.warn(w);

  const withCart = skus.filter(s => s.cartAddCount > 0).length;
  ok({
    totalSkus: skus.length,
    withCartData: withCart,
    coldSkus: skus.length - withCart,
    savedTo: 'data/cart-adds.json',
  });
}

// ─── calculate ───────────────────────────────────────────────────────────────
function cmdCalculate(opts = {}) {
  const { allocate } = require('./lib/allocate');

  const cartData   = readJson('cart-adds.json');
  const compData   = readJson('sku-components.json');
  const stockData  = readJson('warehouse-stock.json');

  const skus       = cartData.skus;
  const stock      = stockData.stock;
  const reserve    = parseFloat(opts.reserve   ?? 0.2);
  const coldFixed  = parseInt(opts.coldFixed   ?? 5, 10);

  console.log(`开始分配: ${skus.length} 个 SKU，余量比例 ${(reserve*100).toFixed(0)}%，冷门保底 ${coldFixed}`);

  const result = allocate(skus, compData, stock, { reserve, coldFixed });

  // 保存中间结果
  const outputFile = path.join(DATA_DIR, 'allocation-result.json');
  fs.writeFileSync(outputFile, JSON.stringify({ _warehouseStock: stock, ...result }, null, 2), 'utf-8');

  const { _meta } = result;
  if (_meta.warnings.length > 0) {
    console.warn('\n警告:');
    for (const w of _meta.warnings) console.warn(`  ${w}`);
  }

  ok({
    k: _meta.k,
    bottleneck: _meta.bottleneck,
    bottleneckRatio: _meta.bottleneckRatio,
    activeSkus: _meta.activeCount,
    coldSkus: _meta.coldCount,
    savedTo: 'data/allocation-result.json',
  });
}

// ─── report ──────────────────────────────────────────────────────────────────
function cmdReport(opts = {}) {
  const { writeReport } = require('./lib/write-report');

  const allocResult = readJson('allocation-result.json');
  const warehouseStock = allocResult._warehouseStock;
  if (!warehouseStock) fail('allocation-result.json 缺少 _warehouseStock 字段，请重新执行 calculate');

  const timestamp = new Date().toISOString().replace(/[T:]/g, '-').slice(0, 16);
  const defaultOutput = path.join(DESKTOP, `库存分配-${timestamp}.xlsx`);
  const outputPath = opts.output ? path.resolve(opts.output) : defaultOutput;

  writeReport(allocResult, warehouseStock, outputPath);
  ok({ reportPath: outputPath });
}

// ─── resolve-stock ────────────────────────────────────────────────────────────
async function cmdResolveStock(opts = {}) {
  const cdp = require('../product-mapping/lib/cdp');
  const { queryStockAndSave } = require('./lib/query-stock');

  const targets = await cdp.getTargets();
  console.log('可用 CDP targets:');
  targets.forEach(t => console.log(`  ${t.id}  ${t.url}`));

  const erpId = opts.erpId || targets.find(t => t.url && (t.url.includes('viperp') || t.url.includes('superboss')))?.targetId;
  if (!erpId) fail('找不到 ERP tab，请确认 Chrome 已打开 ERP 并连接 CDP proxy');

  console.log(`使用 ERP targetId: ${erpId}`);
  console.log('查询库存状态...');
  const output = await queryStockAndSave(erpId);

  ok({
    totalRawRows: output._meta.totalRawRows,
    mappedCount: output._meta.mappedCount,
    warnings: output._meta.warnings.length,
    savedTo: 'data/warehouse-stock.json',
  });
}

// ─── resolve-components ───────────────────────────────────────────────────────
async function cmdResolveComponents(opts = {}) {
  const cdp = require('../product-mapping/lib/cdp');
  const { resolveComponents } = require('./lib/resolve-components');

  const targets = await cdp.getTargets();
  const erpId = opts.erpId || targets.find(t => t.url && (t.url.includes('viperp') || t.url.includes('superboss')))?.targetId;
  if (!erpId) fail('找不到 ERP tab，请确认 Chrome 已打开 ERP 并连接 CDP proxy');

  console.log(`使用 ERP targetId: ${erpId}`);
  const shopName = opts.shop || '澜泽';
  console.log(`读取对应表（店铺: ${shopName}）...`);

  const output = await resolveComponents(erpId, shopName);
  const { _meta } = output;

  ok({
    totalSkus:    _meta.totalSkus,
    matchedSkus:  _meta.matchedSkus,
    resolvedSkus: _meta.resolvedSkus,
    warnings:     _meta.warnings.length,
    savedTo:      'data/sku-components.json',
  });
}

// ─── run（全流程）───────────────────────────────────────────────────────────
function cmdRun(excelPath, opts = {}) {
  console.log('=== 全流程执行（不含 ERP 查询）===\n');
  console.log('Step 1/3: 解析加购数据');
  cmdParse(excelPath || null);

  console.log('\nStep 2/3: 执行分配算法');
  cmdCalculate(opts);

  console.log('\nStep 3/3: 生成 Excel 报告');
  cmdReport(opts);
}

// ─── run-full（含 ERP 的全流程）──────────────────────────────────────────────
async function cmdRunFull(excelPath, opts = {}) {
  console.log('=== 全流程执行（含 ERP 查询）===\n');

  console.log('Step 1/5: 解析加购数据');
  cmdParse(excelPath || null);

  console.log('\nStep 2/5: 查询 ERP 库存状态');
  await cmdResolveStock(opts);

  console.log('\nStep 3/5: 查询 ERP 组合明细');
  await cmdResolveComponents(opts);

  console.log('\nStep 4/5: 执行分配算法');
  cmdCalculate(opts);

  console.log('\nStep 5/5: 生成 Excel 报告');
  cmdReport(opts);
}

// ─── 参数解析 ────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const cmd  = args[0];

// 解析 --key value 形式的参数
function parseOpts(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--') && i + 1 < argv.length) {
      const key = argv[i].slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      opts[key] = argv[i + 1];
      i++;
    }
  }
  return opts;
}

if (!cmd) {
  console.log(`用法:
  node cli.js parse [excel文件]                    解析加购数据（缺省自动找桌面最新 xlsx）
  node cli.js calculate [--reserve 0.2]           执行分配算法
  node cli.js report [--output <路径>]            生成 Excel 报告（默认输出到桌面）
  node cli.js run [excel文件]                      全流程（不含 ERP）
  node cli.js resolve-stock [--erp-id <id>]       查询 ERP 库存状态
  node cli.js resolve-components [--shop 澜泽]    查询 ERP 组合明细
  node cli.js run-full [excel文件] [--shop 澜泽]  全流程（含 ERP 查询）
`);
  process.exit(0);
}

async function main() {
  if (cmd === 'parse') {
    if (!args[1]) fail('缺少参数: <excel文件>');
    cmdParse(args[1]);
  } else if (cmd === 'calculate') {
    cmdCalculate(parseOpts(args.slice(1)));
  } else if (cmd === 'report') {
    cmdReport(parseOpts(args.slice(1)));
  } else if (cmd === 'run') {
    cmdRun(args[1] || null, parseOpts(args.slice(2)));
  } else if (cmd === 'resolve-stock') {
    await cmdResolveStock(parseOpts(args.slice(1)));
  } else if (cmd === 'resolve-components') {
    await cmdResolveComponents(parseOpts(args.slice(1)));
  } else if (cmd === 'run-full') {
    await cmdRunFull(args[1] || null, parseOpts(args.slice(2)));
  } else {
    fail(`未知命令: ${cmd}`);
  }
}

main().catch(e => fail(e.message));
