#!/usr/bin/env node
/**
 * SKU 库存计算器 CLI
 *
 * 命令:
 *   node cli.js parse <excel文件>         解析加购 Excel → data/cart-adds.json
 *   node cli.js calculate                 执行分配算法 → data/allocation-result.json
 *   node cli.js report [--output <路径>]  生成 Excel 报告
 *   node cli.js run <excel文件>           全流程一键执行
 */

const fs   = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');

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
  const absPath = path.resolve(excelPath);
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
  const defaultOutput = path.join(__dirname, `output/库存分配-${timestamp}.xlsx`);
  const outputPath = opts.output ? path.resolve(opts.output) : defaultOutput;

  // 确保 output 目录存在
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  writeReport(allocResult, warehouseStock, outputPath);
  ok({ reportPath: outputPath });
}

// ─── run（全流程）───────────────────────────────────────────────────────────
function cmdRun(excelPath, opts = {}) {
  console.log('=== 全流程执行 ===\n');
  console.log('Step 1/3: 解析加购数据');
  cmdParse(excelPath);

  console.log('\nStep 2/3: 执行分配算法');
  cmdCalculate(opts);

  console.log('\nStep 3/3: 生成 Excel 报告');
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
  node cli.js parse <excel文件>           解析加购数据
  node cli.js calculate [--reserve 0.2]  执行分配算法
  node cli.js report [--output <路径>]   生成 Excel 报告
  node cli.js run <excel文件>             全流程一键执行
`);
  process.exit(0);
}

try {
  if (cmd === 'parse') {
    if (!args[1]) fail('缺少参数: <excel文件>');
    cmdParse(args[1]);
  } else if (cmd === 'calculate') {
    cmdCalculate(parseOpts(args.slice(1)));
  } else if (cmd === 'report') {
    cmdReport(parseOpts(args.slice(1)));
  } else if (cmd === 'run') {
    if (!args[1]) fail('缺少参数: <excel文件>');
    cmdRun(args[1], parseOpts(args.slice(2)));
  } else {
    fail(`未知命令: ${cmd}`);
  }
} catch (e) {
  fail(e.message);
}
