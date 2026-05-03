'use strict';
/**
 * WHAT: 流程级纯逻辑推理测试——frozen fixtures 驱动的 inferDecision 回归测试
 * WHERE: CI (process.env.CI=true) 或本地 `node test/flow-test.js`
 * WHY: 项目核心价值在决策逻辑，必须有回归测试防止误批/漏批
 * ENTRY: CI .github/workflows/test.yml 或手动 node test/flow-test.js
 *
 * 此文件不 import CDP/DOM/wait/targets——纯逻辑纯函数，零浏览器依赖。
 */

const fs = require('fs');
const path = require('path');
const { inferDecision } = require('../lib/infer');

const FIXTURES_DIR = path.join(__dirname, 'fixtures');

function loadFixtures(name) {
  const file = path.join(FIXTURES_DIR, `${name}.json`);
  if (!fs.existsSync(file)) {
    console.log(`SKIP: ${name}.json 不存在`);
    return [];
  }
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function runTests(label, fixtures) {
  let passed = 0;
  let failed = 0;
  const failures = [];

  for (const f of fixtures) {
    const { collectedData, queueItem, expected, workOrderNum } = f;
    try {
      const result = inferDecision({ collectedData, id: 'test', workOrderNum, queueItemId: 'test-q' }, queueItem);

      if (result.action === expected.action) {
        passed++;
      } else {
        failed++;
        failures.push({
          workOrderNum,
          expected: expected.action,
          got: result.action,
          reason: result.reason,
        });
      }
    } catch (e) {
      failed++;
      failures.push({
        workOrderNum,
        expected: expected.action,
        error: e.message,
      });
    }
  }

  const pct = fixtures.length > 0 ? Math.round(passed / fixtures.length * 100) : 100;
  const icon = pct === 100 ? '✅' : pct >= 80 ? '⚠️' : '❌';
  console.log(`${icon} ${label}: ${passed}/${fixtures.length} 通过 (${pct}%)`);
  if (failures.length) {
    console.log('  失败明细:');
    failures.forEach(f => {
      console.log(`    ${f.workOrderNum}: 期望=${f.expected} 实际=${f.got || 'ERROR'}`);
      if (f.reason) console.log(`      原因: ${f.reason.slice(0, 100)}`);
      if (f.error) console.log(`      错误: ${f.error}`);
    });
  }
  return { passed, failed, failures };
}

async function main() {
  const start = Date.now();

  // CI 模式：跳过 CDP 加载检查
  // eslint-disable-next-line no-unused-vars
  const _ciGuard = typeof process.env.CI !== 'undefined';

  let totalPassed = 0;
  let totalFailed = 0;
  const allFailures = [];

  // 回归测试：frozen fixtures，expected = inferDecision 当前输出
  // 目的：防止意外修改导致行为变化
  const data = loadFixtures('decision-regression');
  if (data.length) {
    const r = runTests('决策回归（frozen）', data);
    totalPassed += r.passed;
    totalFailed += r.failed;
    allFailures.push(...r.failures);
  }

  const elapsed = Date.now() - start;
  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`  总计: ${totalPassed} 通过 / ${totalFailed} 失败 / ${totalPassed + totalFailed} 条`);
  console.log(`  耗时: ${elapsed}ms`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━`);

  process.exit(totalFailed > 0 ? 1 : 0);
}

main();
