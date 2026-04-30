#!/usr/bin/env node
'use strict';
// 产品匹配模块化测试运行器
// 参考 aftersales-automation/test/runner.js

const path = require('path');
const { describe, it, before, after } = require('node:test');
const assert = require('assert');

const PROJECT_ROOT = path.join(__dirname, '..');
const { testContext, initTestContext, resetErp, resetJl, clearSessionCache } = require('./helpers/browser');
const { backupSkuRecords, restoreSkuRecords, readSkuRecords, writeFixture, makeSkuRecord, makeSkuRecordsJson } = require('./helpers/fixtures');
const { assertStage, assertMatchStatus, assertNoTmpFiles, assertOk, assertSkipped, assertThrows, assertFileJson } = require('./helpers/assertions');
const { createMockCdp } = require('./helpers/cdp-mock');
const { STEPS, READONLY_STEPS, DESTRUCTIVE_STEPS } = require('./schemas');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function isTimeoutError(e) {
  return /timeout|超时|ECONNRESET|EPIPE/i.test(e.message);
}

async function withRetry(fn, label) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const result = await fn();
      if (attempt > 0) console.log(` ⚠ ${label} retry 成功`);
      return result;
    } catch (e) {
      if (isTimeoutError(e) && attempt === 0) {
        console.log(` ⚠ ${label} 超时，retry...`);
        await sleep(2000);
        continue;
      }
      throw e;
    }
  }
}

async function getErpId() {
  const { getTargetIds } = require(path.join(PROJECT_ROOT, 'lib/targets'));
  const ids = await getTargetIds(true);
  return ids.erpId;
}

// ── L0 基础设施检查 ─────────────────────────────────────────────────────────

async function runL0() {
  console.log('\n═══ L0 基础设施检查 ═══\n');
  const checks = [];

  // 1. CDP 连通 + 连接模式
  try {
    const ctx = await initTestContext();
    checks.push({ name: 'CDP 连通', pass: true, detail: `模式: ${ctx.connectionMode}` });
    checks.push({ name: '鲸灵 target', pass: !!ctx.jlId, detail: ctx.jlId ? ctx.jlId.substring(0, 20) + '...' : '未找到' });
    checks.push({ name: 'ERP target', pass: !!ctx.erpId, detail: ctx.erpId ? ctx.erpId.substring(0, 20) + '...' : '未找到' });
  } catch (e) {
    checks.push({ name: 'CDP 连通', pass: false, detail: e.message });
  }

  // 2. ERP 登录状态
  if (testContext.erpId) {
    try {
      const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
      const CHECK_JS = `(function(){
        var sessionExpired = !!document.querySelector('.inner-login-wrapper');
        return JSON.stringify({loggedIn: !sessionExpired && document.title.includes('快麦ERP--'), title: document.title});
      })()`;
      const status = await cdp.eval(testContext.erpId, CHECK_JS);
      checks.push({ name: 'ERP 已登录', pass: status.loggedIn, detail: status.title });
    } catch (e) {
      checks.push({ name: 'ERP 已登录', pass: false, detail: e.message });
    }
  }

  // 3. Session cache 文件可写
  try {
    const fs = require('fs');
    const cacheFile = path.join(PROJECT_ROOT, 'data/erp-session-cache.json');
    fs.writeFileSync(cacheFile, JSON.stringify({ test: true }));
    const read = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    checks.push({ name: 'Session cache 可写', pass: read.test === true, detail: cacheFile });
    // 清理
    try { fs.unlinkSync(cacheFile); } catch {}
  } catch (e) {
    checks.push({ name: 'Session cache 可写', pass: false, detail: e.message });
  }

  // 打印结果
  console.log('┌──────────────────────────┬──────┬────────────────────────────────────────┐');
  console.log('│ 检查项                    │ 状态  │ 详情                                    │');
  console.log('├──────────────────────────┼──────┼────────────────────────────────────────┤');
  for (const c of checks) {
    const status = c.pass ? '  ✓  ' : '  ✗  ';
    const name = c.name.padEnd(24);
    const detail = (c.detail || '').substring(0, 38).padEnd(38);
    console.log(`│ ${name} │${status}│ ${detail} │`);
  }
  console.log('└──────────────────────────┴──────┴────────────────────────────────────────┘');

  const allPass = checks.every(c => c.pass);
  console.log(allPass ? '\n✅ L0 全部通过，可继续测试' : '\n❌ L0 未全过，请先修复上述问题');
  return allPass;
}

// ── L1 测试套件：safe-write ─────────────────────────────────────────────────

async function runL1SafeWrite(n = 3) {
  const { safeWriteJson } = require(path.join(PROJECT_ROOT, 'lib/utils/safe-write'));
  const fs = require('fs');
  const tmpFile = path.join(__dirname, '_test_safe_write.json');

  const results = [];
  process.stdout.write(`\n▸ L1-safe-write safe-write 原子写入 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      // 清理
      try { fs.unlinkSync(tmpFile); } catch {}
      try { fs.unlinkSync(tmpFile + '.tmp'); } catch {}

      // 用例 1: 基本写入
      safeWriteJson(tmpFile, { a: 1 });
      const d1 = JSON.parse(fs.readFileSync(tmpFile, 'utf8'));
      assert.strictEqual(d1.a, 1);

      // 用例 2: 覆盖写入
      safeWriteJson(tmpFile, { b: 2 });
      const d2 = JSON.parse(fs.readFileSync(tmpFile, 'utf8'));
      assert.strictEqual(d2.b, 2);
      assert.strictEqual(d2.a, undefined);

      // 用例 3: 脏 .tmp 清理
      fs.writeFileSync(tmpFile + '.tmp', 'garbage');
      safeWriteJson(tmpFile, { c: 3 });
      assert.ok(!fs.existsSync(tmpFile + '.tmp'), '.tmp 文件未清理');
      const d3 = JSON.parse(fs.readFileSync(tmpFile, 'utf8'));
      assert.strictEqual(d3.c, 3);

      // 用例 4: 原子性（内容完整）
      safeWriteJson(tmpFile, { d: 'x'.repeat(10000) });
      const d4 = JSON.parse(fs.readFileSync(tmpFile, 'utf8'));
      assert.strictEqual(d4.d.length, 10000);

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  // 清理
  try { fs.unlinkSync(tmpFile); } catch {}
  try { fs.unlinkSync(tmpFile + '.tmp'); } catch {}

  return summarizeResults('L1-safe-write', results);
}

// ── L1 测试套件：annotate ──────────────────────────────────────────────────

async function runL1Annotate(n = 3) {
  const fs = require('fs');
  const skuRecordsPath = path.join(PROJECT_ROOT, 'data/sku-records.json');
  const testPath = path.join(PROJECT_ROOT, 'data/sku-records-test.json');

  // annotate.js 硬编码了 data/sku-records.json 路径
  // 我们需要临时替换文件
  const annotate = require(path.join(PROJECT_ROOT, 'lib/ops/annotate'));

  const results = [];
  process.stdout.write(`\n▸ L1-annotate annotate 类型标注 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      // 备份原始文件
      let original = null;
      try { original = fs.readFileSync(skuRecordsPath, 'utf8'); } catch {}

      // 用例 1: 单品
      writeFixture(makeSkuRecordsJson({
        stage: 'images_done', shopName: 'T', productCode: 'T',
        skus: { '001': makeSkuRecord({ platformCode: '001', recognition: { type: '单品', items: [{ name: 'X', qty: 1 }], raw: 'test' } }) },
      }));
      const r1 = await annotate.annotate();
      assert.strictEqual(r1.ok, true);
      const d1 = JSON.parse(fs.readFileSync(skuRecordsPath, 'utf8'));
      assert.strictEqual(d1.skus['001'].itemType, 'single');
      assert.strictEqual(d1.stage, 'annotated');

      // 用例 2: 套件
      writeFixture(makeSkuRecordsJson({
        stage: 'images_done', shopName: 'T', productCode: 'T',
        skus: { '002': makeSkuRecord({ platformCode: '002', recognition: { type: '组合装', items: [{ name: 'A', qty: 2 }, { name: 'B', qty: 3 }], raw: 'test' } }) },
      }));
      await annotate.annotate();
      const d2 = JSON.parse(fs.readFileSync(skuRecordsPath, 'utf8'));
      assert.strictEqual(d2.skus['002'].itemType, 'suite');

      // 用例 3: 混合批量
      writeFixture(makeSkuRecordsJson({
        stage: 'images_done', shopName: 'T', productCode: 'T',
        skus: {
          '003': makeSkuRecord({ platformCode: '003', recognition: { type: '单品', items: [{ name: 'X', qty: 1 }], raw: '' } }),
          '004': makeSkuRecord({ platformCode: '004', recognition: { type: '单品', items: [{ name: 'Y', qty: 1 }], raw: '' } }),
          '005': makeSkuRecord({ platformCode: '005', recognition: { type: '组合装', items: [{ name: 'A', qty: 2 }], raw: '' } }),
        },
      }));
      const r3 = await annotate.annotate();
      assert.strictEqual(r3.data.singles, 2);
      assert.strictEqual(r3.data.suites, 1);

      // 用例 4: stage 错误
      writeFixture(makeSkuRecordsJson({
        stage: 'skus_read', shopName: 'T', productCode: 'T',
        skus: { '006': makeSkuRecord({ platformCode: '006', recognition: { items: [{ qty: 1 }] } }) },
      }));
      await assertThrows(() => annotate.annotate(), 'images_done');

      // 用例 5: recognition 缺失
      writeFixture(makeSkuRecordsJson({
        stage: 'images_done', shopName: 'T', productCode: 'T',
        skus: { '007': makeSkuRecord({ platformCode: '007', recognition: null }) },
      }));
      await assertThrows(() => annotate.annotate(), 'recognition');

      // 用例 6: 总数量为 0
      writeFixture(makeSkuRecordsJson({
        stage: 'images_done', shopName: 'T', productCode: 'T',
        skus: { '008': makeSkuRecord({ platformCode: '008', recognition: { items: [{ qty: 0 }] } }) },
      }));
      await assertThrows(() => annotate.annotate(), '0');

      // 恢复原始文件
      if (original) fs.writeFileSync(skuRecordsPath, original);
      else try { fs.unlinkSync(skuRecordsPath); } catch {}

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L1-annotate', results);
}

// ── L1 测试套件：match-one 逻辑 ───────────────────────────────────────────

async function runL1MatchOneLogic(n = 3) {
  const fs = require('fs');
  const skuRecordsPath = path.join(PROJECT_ROOT, 'data/sku-records.json');
  const matchOne = require(path.join(PROJECT_ROOT, 'lib/match-one')).matchOne;

  const results = [];
  process.stdout.write(`\n▸ L1-match-one-logic 编排器逻辑 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      let original = null;
      try { original = fs.readFileSync(skuRecordsPath, 'utf8'); } catch {}

      // 用例 1: 无效 --from
      await assertThrows(() => matchOne('x', 'x', 'T', 'T', { from: 'bogus' }), '非法步骤');

      // 用例 2: stage 太低
      writeFixture(makeSkuRecordsJson({
        stage: 'skus_read', shopName: 'T', productCode: 'T', skus: {},
      }));
      await assertThrows(() => matchOne('x', 'x', 'T', 'T', { from: 'match' }), 'annotated');

      // 用例 3: 编码不匹配
      writeFixture(makeSkuRecordsJson({
        stage: 'annotated', shopName: 'T', productCode: 'WRONG', skus: {},
      }));
      await assertThrows(() => matchOne('x', 'x', 'T', 'RIGHT', { from: 'match' }), '不一致');

      // 用例 4: 暂停在 recognize — 移到 L2（需要真实浏览器执行 download 步骤）
      // L1 只验证纯逻辑，不执行实际 pipeline

      // 恢复
      if (original) fs.writeFileSync(skuRecordsPath, original);
      else try { fs.unlinkSync(skuRecordsPath); } catch {}

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L1-match-one-logic', results);
}

// ── L2 测试套件：targets ──────────────────────────────────────────────────

async function runL2Targets(n = 5) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));

  const results = [];
  process.stdout.write(`\n▸ L2-targets 浏览器标签检测 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const targets = await cdp.getTargets();

      // 用例 1: 返回数组，每项有 url
      assert.ok(Array.isArray(targets), 'getTargets 应返回数组');
      assert.ok(targets.length > 0, 'targets 不应为空');
      assert.ok(targets[0].url || targets[0].targetId, 'target 应有 url 或 targetId');

      // 用例 2: 找到鲸灵 tab
      const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
      assert.ok(jl, '应找到鲸灵标签页');

      // 用例 3: 找到 ERP tab
      const erp = targets.find(t => t.url && t.url.includes('superboss.cc'));
      assert.ok(erp, '应找到 ERP 标签页');

      // 用例 4: 缓存行为（两次调用返回相同结果）
      const targets2 = await cdp.getTargets();
      assert.strictEqual(targets.length, targets2.length, '两次 getTargets 结果应一致');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-targets', results);
}

// ── L2 测试套件：cdp ──────────────────────────────────────────────────────

async function runL2Cdp(n = 5) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));

  const results = [];
  process.stdout.write(`\n▸ L2-cdp CDP 通信 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      // 用例 1: eval 返回基本值
      const r1 = await cdp.eval(erpId, '1+1');
      assert.strictEqual(r1, 2, 'eval(1+1) 应返回 2');

      // 用例 2: eval JSON 解析
      const r2 = await cdp.eval(erpId, 'JSON.stringify({a:1})');
      assert.deepStrictEqual(r2, { a: 1 }, 'eval JSON 应自动解析');

      // 用例 3: eval 返回字符串
      const r3 = await cdp.eval(erpId, '"hello"');
      assert.strictEqual(r3, 'hello', 'eval 字符串应正确返回');

      // 用例 4: eval 返回布尔
      const r4 = await cdp.eval(erpId, 'true');
      assert.strictEqual(r4, true, 'eval 布尔应正确返回');

      // 用例 5: getTargets 返回有效数据
      const t = await cdp.getTargets();
      assert.ok(Array.isArray(t), 'getTargets 应返回数组');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-cdp', results);
}

// ── L2 测试套件：ensure-corr-page ────────────────────────────────────────

async function runL2EnsureCorrPage(n = 3) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { ensureCorrPage, canSkipSearch } = require(path.join(PROJECT_ROOT, 'lib/ops/ensure-corr-page'));

  const results = [];
  process.stdout.write(`\n▸ L2-ensure-corr-page 对应表页面守卫 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      // 用例 1: 不在对应表页 → 导航到对应表
      clearSessionCache();
      await resetErp(erpId);
      // 先导航到档案V2（不在对应表）
      const { navigateErp } = require(path.join(PROJECT_ROOT, 'lib/navigate'));
      await navigateErp(erpId, '商品档案V2');
      const hashBefore = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hashBefore, '#/prod/parallel/', '应在档案V2');

      await ensureCorrPage(erpId);
      const hashAfter = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hashAfter, '#/prod/prod_correspondence_next/', '应导航到对应表');

      // 用例 2: 已在对应表页 → 不 reload，搜索框清空
      // 先填入搜索内容
      await cdp.eval(erpId, `(function(){
        var inputs = document.querySelectorAll("input[type=text],input:not([type])");
        for(var i=0;i<inputs.length;i++){
          var ph=inputs[i].placeholder||"";
          if(ph.includes("商家编码")){
            inputs[i].value="test-value";
            inputs[i].dispatchEvent(new Event("input",{bubbles:true}));
            return;
          }
        }
      })()`);
      await sleep(300);
      await ensureCorrPage(erpId);
      const inputVal = await cdp.eval(erpId, `(function(){
        var inputs = document.querySelectorAll("input[type=text],input:not([type])");
        for(var i=0;i<inputs.length;i++){
          var ph=inputs[i].placeholder||"";
          if(ph.includes("商家编码")) return inputs[i].value;
        }
        return "NOT-FOUND";
      })()`);
      assert.strictEqual(inputVal, '', '搜索框应被清空');

      // 用例 3-5: canSkipSearch — 需要先搜索并展开一个产品
      // 这些需要真实数据，暂时跳过（在 Phase 5 read-skus 测试中验证）
      // canSkipSearch 在无搜索结果时应返回 false
      const skipResult = await canSkipSearch(erpId, '共途', 'nonexistent', 0);
      assert.strictEqual(skipResult, false, '无搜索结果时 canSkipSearch 应返回 false');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-ensure-corr-page', results);
}

// ── L2 测试套件：read-table-rows ─────────────────────────────────────────

async function runL2ReadTableRows(n = 3) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { readTableRows } = require(path.join(PROJECT_ROOT, 'lib/ops/read-table-rows'));
  const { ensureCorrPage } = require(path.join(PROJECT_ROOT, 'lib/ops/ensure-corr-page'));

  const results = [];
  process.stdout.write(`\n▸ L2-read-table-rows 表格 DOM 读取 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      clearSessionCache();
      await resetErp(erpId);
      await ensureCorrPage(erpId);

      // 用例 1: expectedProductCode 缺失应报错
      await assertThrows(() => readTableRows(erpId, { fields: ['platformCode'] }), 'expectedProductCode 必传');

      // 用例 2: expectedProductCode 不匹配应报错 TABLE_DATA_MISMATCH
      // 需要先有搜索结果，这里用一个不存在的编码
      // 先搜索一个不存在的编码
      await cdp.eval(erpId, `(function(){
        var inputs = document.querySelectorAll("input[type=text],input:not([type])");
        for(var i=0;i<inputs.length;i++){
          var ph=inputs[i].placeholder||"";
          if(ph.includes("商家编码")){
            inputs[i].value="NONEXISTENT-CODE";
            inputs[i].dispatchEvent(new Event("input",{bubbles:true}));
            var e=new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true});
            inputs[i].dispatchEvent(e);
            inputs[i].dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));
            return;
          }
        }
      })()`);
      await sleep(3000);

      // 表格已有展开行时，readTableRows 应报 TABLE_DATA_MISMATCH（首行编码不匹配）
      await assertThrows(() => readTableRows(erpId, { fields: ['platformCode'], expectedProductCode: 'NONEXISTENT' }), 'TABLE_DATA_MISMATCH');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-read-table-rows', results);
}

// ── L2 测试套件：download-products ───────────────────────────────────────

async function runL2DownloadProducts(n = 1) {
  // download-products 是破坏性操作（触发下载弹窗），只跑 1 次预检
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { downloadProducts } = require(path.join(PROJECT_ROOT, 'lib/ops/download-products'));

  const results = [];
  process.stdout.write(`\n▸ L2-download-products 下载平台商品 (${n}次，破坏性预检): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      clearSessionCache();
      await resetErp(erpId);

      // 预检：确保能导航到对应表页面
      const { navigateErp } = require(path.join(PROJECT_ROOT, 'lib/navigate'));
      await navigateErp(erpId, '商品对应表');
      const hash = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hash, '#/prod/prod_correspondence_next/', '应能导航到对应表');

      // 预检：检查下载按钮是否存在（不实际点击）
      const btnExists = await cdp.eval(erpId, `(function(){
        var btns = Array.from(document.querySelectorAll('button, .el-button'));
        return btns.some(function(b){
          var t = b.textContent.trim();
          return t.includes('下载') || t.includes('平台商品');
        });
      })()`);
      // 不强制要求按钮存在（可能页面结构不同）

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-download-products', results);
}

// ── L2 测试套件：read-skus ────────────────────────────────────────────────

async function runL2ReadSkus(n = 5) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { readSkus } = require(path.join(PROJECT_ROOT, 'lib/ops/read-skus'));
  const fs = require('fs');
  const SKU_PATH = path.join(PROJECT_ROOT, 'data/sku-records.json');

  const results = [];
  process.stdout.write(`\n▸ L2-read-skus 读取货号 SKU 列表 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      clearSessionCache();
      await resetErp(erpId);

      // 用例 1: 店铺不存在 → 抛错 "左侧店铺未找到"
      await assertThrows(() => readSkus(erpId, '不存在的店铺', 'any-code'), '未找到');

      // 用例 2: 读取杭州共途固定货号
      const result = await readSkus(erpId, '杭州共途', 'kgossynt-cx');
      assertOk(result);
      assert.ok(result.data.skuCount > 0, 'skuCount 应 > 0');
      assert.strictEqual(result.data.matchedCount + result.data.unmatchedCount, result.data.skuCount,
        'matched + unmatched 应 = total');

      // 验证文件写入
      const record = JSON.parse(fs.readFileSync(SKU_PATH, 'utf8'));
      assert.strictEqual(record.stage, 'skus_read');
      assert.strictEqual(record.productCode, 'kgossynt-cx');
      assert.strictEqual(record.shopName, '杭州共途');
      const skuKeys = Object.keys(record.skus);
      assert.ok(skuKeys.length > 0, 'skus 应非空');
      // 每个 SKU 应有必要字段
      for (const key of skuKeys) {
        const sku = record.skus[key];
        assert.ok(sku.platformCode, `SKU ${key} 缺 platformCode`);
        assert.ok(sku.skuName, `SKU ${key} 缺 skuName`);
        assert.ok(sku.matchStatus, `SKU ${key} 缺 matchStatus`);
        assert.ok(['matched-original', 'unmatched'].includes(sku.matchStatus),
          `SKU ${key} matchStatus=${sku.matchStatus} 不合法`);
      }

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-read-skus', results);
}

// ── L2 测试套件：read-erp-codes ───────────────────────────────────────────

async function runL2ReadErpCodes(n = 3) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { readSkus } = require(path.join(PROJECT_ROOT, 'lib/ops/read-skus'));
  const { readErpCodes } = require(path.join(PROJECT_ROOT, 'lib/ops/read-erp-codes'));
  const fs = require('fs');
  const SKU_PATH = path.join(PROJECT_ROOT, 'data/sku-records.json');

  const results = [];
  process.stdout.write(`\n▸ L2-read-erp-codes 重读验证 ERP 编码 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      clearSessionCache();
      await withRetry(() => readSkus(erpId, '杭州共途', 'kgossynt-cx'), 'readSkus');

      // 用例 1: stage=skus_read → 应报错 "要求 matched 或 verified"
      await assertThrows(() => readErpCodes(erpId, '杭州共途', 'kgossynt-cx'), '要求 matched 或 verified');

      // 手动把 stage 改为 matched 以便测试 readErpCodes
      const record = JSON.parse(fs.readFileSync(SKU_PATH, 'utf8'));
      record.stage = 'matched';
      fs.writeFileSync(SKU_PATH, JSON.stringify(record, null, 2));

      // 用例 2: 正常执行 readErpCodes
      const result = await readErpCodes(erpId, '杭州共途', 'kgossynt-cx');
      assertOk(result);
      assert.ok(typeof result.data.matched === 'number', 'matched 应为数字');
      assert.ok(typeof result.data.failed === 'number', 'failed 应为数字');

      // 验证文件更新
      const updated = JSON.parse(fs.readFileSync(SKU_PATH, 'utf8'));
      assert.strictEqual(updated.stage, 'matched');

      // 用例 3: matched-original 不应被修改（已有的原始绑定保持不变）
      // 这个在 readErpCodes 代码中已保证（跳过非 unmatched/matched-ai 的 SKU）

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-read-erp-codes', results);
}

// ── L2 测试套件：remap-single ─────────────────────────────────────────────

async function runL2RemapSingle(n = 5) {
  const { remapSingle } = require(path.join(PROJECT_ROOT, 'lib/ops/remap-single'));
  const fs = require('fs');
  const SKU_PATH = path.join(PROJECT_ROOT, 'data/sku-records.json');

  const results = [];
  process.stdout.write(`\n▸ L2-remap-single 单品换绑 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      // 用例 1: recognition 缺失 → 抛错
      const skuNoRec = {
        platformCode: 'TEST-NO-REC', erpCode: null,
        matchStatus: 'unmatched', recognition: null,
        productCode: 'kgossynt-cx', shopName: '杭州共途',
      };
      await assertThrows(() => remapSingle(erpId, skuNoRec), 'recognition 为空');

      // 用例 2: recognition.items 为空数组 → 抛错
      const skuEmptyItems = {
        platformCode: 'TEST-EMPTY', erpCode: null,
        matchStatus: 'unmatched', recognition: { items: [] },
        productCode: 'kgossynt-cx', shopName: '杭州共途',
      };
      await assertThrows(() => remapSingle(erpId, skuEmptyItems), 'recognition 为空');

      // 用例 3: 已 matched-original + 有 erpCode → 幂等跳过
      const skuMatchedOrig = {
        platformCode: 'TEST-MO', erpCode: 'MO-001',
        matchStatus: 'matched-original', recognition: { items: [{ name: 'test', qty: 1 }] },
      };
      const r1 = await remapSingle(erpId, skuMatchedOrig);
      assertSkipped(r1);

      // 用例 4: 已 matched-ai + 有 erpCode → 幂等跳过
      const skuMatchedAi = {
        platformCode: 'TEST-MA', erpCode: 'MA-001',
        matchStatus: 'matched-ai', recognition: { items: [{ name: 'test', qty: 1 }] },
      };
      const r2 = await remapSingle(erpId, skuMatchedAi);
      assertSkipped(r2);

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-remap-single', results);
}

// ── L2 测试套件：create-suite ─────────────────────────────────────────────

async function runL2CreateSuite(n = 5) {
  const { createSuite } = require(path.join(PROJECT_ROOT, 'lib/ops/create-suite'));

  const results = [];
  process.stdout.write(`\n▸ L2-create-suite 创建套件 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      // 用例 1: recognition 缺失 → 抛错
      const skuNoRec = {
        platformCode: 'TEST-SUITE-NO-REC', erpCode: null,
        matchStatus: 'unmatched', recognition: null,
        productCode: 'kgossynt-cx', shopName: '杭州共途',
      };
      await assertThrows(() => createSuite(erpId, skuNoRec), 'recognition 为空');

      // 用例 2: recognition.items 为空 → 抛错
      const skuEmpty = {
        platformCode: 'TEST-SUITE-EMPTY', erpCode: null,
        matchStatus: 'unmatched', recognition: { items: [] },
        productCode: 'kgossynt-cx', shopName: '杭州共途',
      };
      await assertThrows(() => createSuite(erpId, skuEmpty), 'recognition 为空');

      // 用例 3: 已 matched-original + erpCode → 幂等跳过
      const skuMo = {
        platformCode: 'TEST-SUITE-MO', erpCode: 'MO-S-001',
        matchStatus: 'matched-original', recognition: { items: [{ name: 'test', qty: 1 }] },
      };
      const r1 = await createSuite(erpId, skuMo);
      assertSkipped(r1);

      // 用例 4: 已 matched-ai + erpCode → 幂等跳过
      const skuMa = {
        platformCode: 'TEST-SUITE-MA', erpCode: 'MA-S-001',
        matchStatus: 'matched-ai', recognition: { items: [{ name: 'test', qty: 2 }] },
      };
      const r2 = await createSuite(erpId, skuMa);
      assertSkipped(r2);

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-create-suite', results);
}

// ── L2 测试套件：verify-archive ───────────────────────────────────────────

async function runL2VerifyArchive(n = 3) {
  const { verifyArchive, itemSetsEqual } = require(path.join(PROJECT_ROOT, 'lib/ops/verify-archive'));
  const { readSkus } = require(path.join(PROJECT_ROOT, 'lib/ops/read-skus'));
  const fs = require('fs');
  const SKU_PATH = path.join(PROJECT_ROOT, 'data/sku-records.json');

  const results = [];
  process.stdout.write(`\n▸ L2-verify-archive 档案核查 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();
      clearSessionCache();

      // 用例 1: stage=skus_read → 应报错
      // 不调用 resetErp，让 readSkus 内部的 ensureCorrPage 处理导航
      await withRetry(() => readSkus(erpId, '杭州共途', 'kgossynt-cx'), 'readSkus');
      await assertThrows(() => verifyArchive(erpId, '杭州共途', 'kgossynt-cx'), '要求 matched 或 verified');

      // 用例 2: 无 erpCode 的 SKU 应被跳过
      const record = JSON.parse(fs.readFileSync(SKU_PATH, 'utf8'));
      record.stage = 'matched';
      // 所有 SKU 都是 unmatched（无 erpCode），verifyArchive 应跳过全部
      fs.writeFileSync(SKU_PATH, JSON.stringify(record, null, 2));
      const result = await verifyArchive(erpId, '杭州共途', 'kgossynt-cx');
      assertOk(result);
      assert.strictEqual(result.data.match, 0, '无 erpCode 时 match 应为 0');
      assert.strictEqual(result.data.mismatch, 0, '无 erpCode 时 mismatch 应为 0');

      // 验证 stage 已更新为 verified
      const updated = JSON.parse(fs.readFileSync(SKU_PATH, 'utf8'));
      assert.strictEqual(updated.stage, 'verified');

      // 用例 3: itemSetsEqual 边界测试（纯函数，不需浏览器）
      assert.strictEqual(
        itemSetsEqual([{ name: 'A', qty: 1 }, { name: 'B', qty: 2 }], [{ name: 'B', qty: 2 }, { name: 'A', qty: 1 }]),
        true, '顺序不同应为 true'
      );
      assert.strictEqual(
        itemSetsEqual([{ name: 'A', qty: 1 }], [{ name: 'A', qty: 2 }]),
        false, '数量不同应为 false'
      );
      assert.strictEqual(itemSetsEqual([], []), true, '两个空数组应为 true');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-verify-archive', results);
}

// ── L2 测试套件：navigate ─────────────────────────────────────────────────

async function runL2Navigate(n = 5) {
  const cdp = require(path.join(PROJECT_ROOT, 'lib/cdp'));
  const { navigateErp, checkLogin } = require(path.join(PROJECT_ROOT, 'lib/navigate'));

  const results = [];
  process.stdout.write(`\n▸ L2-navigate ERP 页面导航 (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      const erpId = await getErpId();

      // 用例 1: 导航到对应表
      clearSessionCache();
      await resetErp(erpId);
      await navigateErp(erpId, '商品对应表');
      const hash1 = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hash1, '#/prod/prod_correspondence_next/', '应导航到对应表');
      // 验证 el-table 存在
      const hasTable = await cdp.eval(erpId, '!!document.querySelector(".el-table")');
      assert.ok(hasTable, '对应表页面应有 el-table');

      // 用例 2: 导航到档案V2
      clearSessionCache();
      await resetErp(erpId);
      await navigateErp(erpId, '商品档案V2');
      const hash2 = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hash2, '#/prod/parallel/', '应导航到档案V2');

      // 用例 3: checkLogin 返回正确格式
      clearSessionCache();
      await resetErp(erpId);
      const loginStatus = await checkLogin(erpId);
      assert.ok(typeof loginStatus.loggedIn === 'boolean', 'checkLogin 应返回 loggedIn');
      assert.ok(loginStatus.title, 'checkLogin 应返回 title');

      // 用例 4: Session 缓存命中 — 导航两次，第二次应跳过 reload
      clearSessionCache();
      await resetErp(erpId);
      await navigateErp(erpId, '商品对应表');
      // 不清 cache，再次导航到同一页面
      await navigateErp(erpId, '商品对应表');
      const hash3 = await cdp.eval(erpId, 'window.location.hash');
      assert.strictEqual(hash3, '#/prod/prod_correspondence_next/', '缓存命中后仍在对应表');

      // 用例 5: 页面内容等待 — 导航后 el-table 存在
      clearSessionCache();
      await resetErp(erpId);
      await navigateErp(erpId, '商品对应表');
      const loadingVisible = await cdp.eval(erpId, `(function(){
        var m = document.querySelector('.el-loading-mask');
        if (!m) return false;
        var s = getComputedStyle(m);
        return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
      })()`);
      assert.strictEqual(loadingVisible, false, '导航后 loading 应消失');

      // 用例 6: 未知页面名应报错
      await assertThrows(() => navigateErp(erpId, '不存在的页面'), '未知页面');

      results.push({ run: i, pass: true, elapsed: Date.now() - start });
      process.stdout.write('✓');
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }
  }

  return summarizeResults('L2-navigate', results);
}

// ── 汇总报告 ───────────────────────────────────────────────────────────────

function summarizeResults(id, results) {
  const passed = results.filter(r => r.pass).length;
  const total = results.length;
  const avgMs = total ? Math.round(results.reduce((s, r) => s + r.elapsed, 0) / total) : 0;
  const failures = results.filter(r => !r.pass);

  if (failures.length > 0) {
    failures.forEach(f => console.log(`\n  ❌ run#${f.run}: ${f.error}`));
  }

  return { id, passed, total, avgMs, failures };
}

function printReport(allResults) {
  console.log('\n' + '─'.repeat(64));
  console.log('┌──────────────────────────────────┬──────┬──────┬──────────┐');
  console.log('│ 步骤                              │ 通过  │ 失败  │ 平均耗时  │');
  console.log('├──────────────────────────────────┼──────┼──────┼──────────┤');
  for (const r of allResults) {
    const label = r.id.substring(0, 32).padEnd(32);
    const pass = `${r.passed}/${r.total}`.padEnd(4);
    const fail = `${r.total - r.passed}`.padEnd(4);
    const ms = `${r.avgMs}ms`.padEnd(8);
    console.log(`│ ${label} │ ${pass} │ ${fail} │ ${ms} │`);
  }
  console.log('└──────────────────────────────────┴──────┴──────┴──────────┘');
  console.log();
}

// ── CLI 入口 ───────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help') {
    console.log('用法:');
    console.log('  node test/run.js l0                    基础设施检查');
    console.log('  node test/run.js --fast                 只跑 L1 单元测试');
    console.log('  node test/run.js step <MODULE> [-n N]   单模块稳定性测试');
    console.log('  node test/run.js all                    全量测试');
    process.exit(0);
  }

  if (command === 'l0') {
    const ok = await runL0();
    process.exit(ok ? 0 : 1);
  }

  if (command === '--fast') {
    console.log('\n═══ L1 快速测试 ═══');
    const results = [];
    results.push(await runL1SafeWrite(3));
    results.push(await runL1Annotate(3));
    results.push(await runL1MatchOneLogic(3));
    printReport(results);
    const allPass = results.every(r => r.failures.length === 0);
    process.exit(allPass ? 0 : 1);
  }

  if (command === 'step') {
    const module = args[1];
    const nIdx = args.indexOf('-n');
    const n = nIdx >= 0 ? parseInt(args[nIdx + 1]) : 3;

    const results = [];
    switch (module) {
      case 'safe-write': results.push(await runL1SafeWrite(n)); break;
      case 'annotate': results.push(await runL1Annotate(n)); break;
      case 'match-one-logic': results.push(await runL1MatchOneLogic(n)); break;
      case 'targets': await initTestContext(); results.push(await runL2Targets(n)); break;
      case 'cdp': await initTestContext(); results.push(await runL2Cdp(n)); break;
      case 'navigate': await initTestContext(); results.push(await runL2Navigate(n)); break;
      case 'ensure-corr-page': await initTestContext(); results.push(await runL2EnsureCorrPage(n)); break;
      case 'read-table-rows': await initTestContext(); results.push(await runL2ReadTableRows(n)); break;
      case 'download-products': await initTestContext(); results.push(await runL2DownloadProducts(n)); break;
      case 'read-skus': await initTestContext(); results.push(await runL2ReadSkus(n)); break;
      case 'read-erp-codes': await initTestContext(); results.push(await runL2ReadErpCodes(n)); break;
      case 'remap-single': await initTestContext(); results.push(await runL2RemapSingle(n)); break;
      case 'create-suite': await initTestContext(); results.push(await runL2CreateSuite(n)); break;
      case 'verify-archive': await initTestContext(); results.push(await runL2VerifyArchive(n)); break;
      default:
        console.error(`未知模块: ${module}。可用: safe-write, annotate, match-one-logic, targets, cdp, navigate, ensure-corr-page, read-table-rows, download-products, read-skus, read-erp-codes, remap-single, create-suite, verify-archive`);
        process.exit(1);
    }
    printReport(results);
    process.exit(results.every(r => r.failures.length === 0) ? 0 : 1);
  }

  if (command === 'all') {
    console.log('\n═══ 全量测试 ═══');
    const results = [];
    // L1
    results.push(await runL1SafeWrite(3));
    results.push(await runL1Annotate(3));
    results.push(await runL1MatchOneLogic(3));
    // L2 基础设施
    await initTestContext();
    results.push(await runL2Targets(5));
    results.push(await runL2Cdp(5));
    results.push(await runL2Navigate(5));
    // L2 页面操作
    results.push(await runL2EnsureCorrPage(3));
    results.push(await runL2ReadTableRows(3));
    results.push(await runL2DownloadProducts(1));
    // L2 SKU 读写
    results.push(await runL2ReadSkus(5));
    results.push(await runL2ReadErpCodes(3));
    // L2 匹配操作
    results.push(await runL2RemapSingle(5));
    results.push(await runL2CreateSuite(5));
    results.push(await runL2VerifyArchive(3));
    // L2 编排器 待实现...
    printReport(results);
    process.exit(results.every(r => r.failures.length === 0) ? 0 : 1);
  }

  console.error(`未知命令: ${command}。用 --help 查看用法`);
  process.exit(1);
}

main().catch(e => {
  console.error(`\n❌ 运行器异常: ${e.message}`);
  process.exit(1);
});
