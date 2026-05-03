'use strict';

const { execSync, spawnSync } = require('child_process');
const cdp = require('../lib/cdp');
const { sleep, waitFor } = require('../lib/wait');

const BASE = '/Users/chat/claude/aftersales-automation';

// ── 页面复原 ─────────────────────────────────────────────────────────────────

/**
 * 复原鲸灵页面（刷新 + 等待加载完成）
 */
async function resetJl(targetId) {
  // 每次测试前等10秒，让上一次操作完全结束，避免刷新太频繁导致异常
  await sleep(10000);
  // reload：可能 ECONNRESET，retry 一次
  for (let i = 0; i < 3; i++) {
    try {
      await cdp.eval(targetId, 'location.reload()');
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(2000);
      } else {
        throw e;
      }
    }
  }
  // reload 后固定等 3s，让 CDP proxy 和页面完全稳定
  await sleep(3000);
  await waitFor(
    async () => {
      try {
        const state = await cdp.eval(targetId, 'document.readyState');
        return state === 'complete';
      } catch (e) {
        if (e.message && e.message.includes('ECONNRESET')) return false;
        throw e;
      }
    },
    { timeoutMs: 15000, intervalMs: 500, label: '鲸灵页面刷新' }
  );
  await sleep(1000);  // 额外等待 Vue 渲染

  const url = await cdp.eval(targetId, 'window.location.href');
  if (url.includes('login') || url.includes('sso')) {
    throw new Error(`鲸灵登录已失效，URL: ${url}，请手动重新登录`);
  }
}

/**
 * 复原 ERP 页面（刷新 + 等待加载 + 检查/恢复登录）
 */
async function resetErp(targetId) {
  // 每次测试前等10秒，让上一次操作完全结束，避免刷新太频繁导致异常
  await sleep(10000);
  // reload：可能 ECONNRESET，retry 一次
  for (let i = 0; i < 3; i++) {
    try {
      await cdp.eval(targetId, 'location.reload()');
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(2000);
      } else {
        throw e;
      }
    }
  }
  // reload 后固定等 3s，让 CDP proxy 和页面完全稳定
  await sleep(3000);

  // 检查是否弹出登录框（会话超时）；用 retry 防止 reload 后首次 eval ECONNRESET
  const CHECK_JS = `(function(){
    var sessionExpired = !!document.querySelector('.inner-login-wrapper');
    var notErp = !document.title.includes('快麦ERP--');
    return JSON.stringify({sessionExpired, notErp, title: document.title});
  })()`;
  let status;
  for (let i = 0; i < 3; i++) {
    try {
      status = await cdp.eval(targetId, CHECK_JS);
      break;
    } catch (e) {
      if (e.message && e.message.includes('ECONNRESET') && i < 2) {
        await sleep(1500);
      } else {
        throw e;
      }
    }
  }

  if (status.sessionExpired || status.notErp) {
    // 尝试恢复登录
    if (process.stderr) process.stderr.write('[runner] ERP 会话过期，尝试恢复登录\n');
    await cdp.clickAt(targetId, '.iCheck-helper');
    await sleep(500);
    const clickBtn = `(function(){
      var btn = Array.from(document.querySelectorAll('button')).find(function(b){
        return b.textContent.trim().includes('登');
      });
      if (btn) { btn.click(); return 'clicked'; }
      return 'not found';
    })()`;
    await cdp.eval(targetId, clickBtn);
    await sleep(5000);

    const check2 = await cdp.eval(targetId, CHECK_JS);
    if (check2.notErp || check2.sessionExpired) {
      throw new Error(`ERP 登录恢复失败，title: ${check2.title}`);
    }
  }

  await sleep(500);
}

// ── CLI 命令执行 ──────────────────────────────────────────────────────────────

/**
 * 执行 CLI 命令，返回解析后的 JSON 结果
 * @param {string[]} args - CLI 参数（不含 "node cli.js"）
 * @returns {{ success, data?, error? }}
 */
function runCmd(args) {
  const cmdStr = args.filter(Boolean).join(' ');
  const full = `node ${BASE}/cli.js ${cmdStr}`;
  if (process.env.VERBOSE) process.stderr.write(`[runner] ${full}\n`);
  // ECONNRESET 重试：CDP proxy 在页面刷新后短暂断连，等 2s 重试一次
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const raw = execSync(full, { timeout: 90000, cwd: BASE }).toString();
      return JSON.parse(raw);
    } catch (e) {
      const isConnReset = e.message && e.message.includes('ECONNRESET');
      if (isConnReset && attempt === 0) {
        spawnSync('sleep', ['2']);
        continue;
      }
      throw e;
    }
  }
}

// ── Schema 校验 ──────────────────────────────────────────────────────────────

/**
 * 校验 data 是否满足 schema
 * @param {object} data
 * @param {object} schema - { fieldName: { type, required, nonEmpty, minLen } }
 * @returns {string[]} 错误列表（空数组=通过）
 */
function validateSchema(data, schema) {
  const errors = [];
  for (const [field, rule] of Object.entries(schema)) {
    const value = data && data[field];
    const missing = value === undefined || value === null;

    if (missing) {
      if (rule.required !== false) errors.push(`字段缺失或为null: ${field}`);
      continue;
    }

    if (rule.type === 'array' && !Array.isArray(value)) {
      errors.push(`${field} 期望数组，实际 ${typeof value}`);
      continue;
    }
    if (rule.type && rule.type !== 'array' && typeof value !== rule.type) {
      errors.push(`${field} 类型错误: 期望 ${rule.type}，实际 ${typeof value}`);
    }
    if (rule.nonEmpty && (value === '' || (Array.isArray(value) && value.length === 0))) {
      errors.push(`${field} 不能为空`);
    }
    if (rule.minLen !== undefined && Array.isArray(value) && value.length < rule.minLen) {
      errors.push(`${field} 数组长度 ${value.length} < ${rule.minLen}`);
    }
  }
  return errors;
}

// ── 单步骤测试 ────────────────────────────────────────────────────────────────

/**
 * 运行单个步骤的稳定性测试（复原→执行→验证，重复 n 次）
 *
 * @param {object} stepDef   - 来自 schemas.js 的步骤定义
 * @param {object} args      - 该步骤所需的输入参数 { workOrderNum, sku, ... }
 * @param {number} n         - 测试次数（默认 10）
 * @param {object} targets   - { jlId, erpId }
 * @returns {{ id, name, passed, total, avgMs, failures, lastData }}
 */
async function runStepTest(stepDef, args, n = 10, targets) {
  const { id, name, resetTarget, schema, customValidate, prerequisite, destructive } = stepDef;

  if (destructive) {
    console.log(`\n⚠  ${id} (${name}) 是破坏性操作，仅执行预检（1次，验证按钮可见）`);
    n = 1;
  }

  const targetId = resetTarget === 'jl' ? targets.jlId : targets.erpId;
  const reset = resetTarget === 'jl' ? resetJl : resetErp;

  const results = [];
  process.stdout.write(`\n▸ ${id} ${name} (${n}次): `);

  for (let i = 1; i <= n; i++) {
    const start = Date.now();
    try {
      // ① 复原
      await reset(targetId);

      // ② 前置步骤（ERP-2 等依赖页面状态的步骤）
      if (prerequisite) {
        const preCmd = prerequisite.cliCmd(args);
        const preResult = runCmd(preCmd);
        if (!preResult.success) {
          throw new Error(`前置步骤失败: ${preResult.error}`);
        }
      }

      // ③ 执行
      const cliArgs = stepDef.cliCmd(args);
      const result = runCmd(cliArgs);
      const elapsed = Date.now() - start;

      if (!result.success) {
        results.push({ run: i, pass: false, error: result.error, elapsed });
        process.stdout.write('✗');
        continue;
      }

      // ④ 验证
      const schemaErrors = validateSchema(result.data, schema || {});
      const customErrors = customValidate ? customValidate(result.data, args) : [];
      const allErrors = [...schemaErrors, ...customErrors];

      if (allErrors.length > 0) {
        results.push({ run: i, pass: false, error: allErrors.join('; '), elapsed, data: result.data });
        process.stdout.write('✗');
      } else {
        results.push({ run: i, pass: true, elapsed, data: result.data });
        process.stdout.write('✓');
      }
    } catch (e) {
      results.push({ run: i, pass: false, error: e.message, elapsed: Date.now() - start });
      process.stdout.write('✗');
    }

    // 每5次换行，方便观察
    if (i % 5 === 0 && i < n) process.stdout.write(`  ${i}/${n}\n  `);
  }

  process.stdout.write('\n');

  const passed = results.filter(r => r.pass).length;
  const avgMs = results.length
    ? Math.round(results.reduce((s, r) => s + r.elapsed, 0) / results.length)
    : 0;
  const failures = results.filter(r => !r.pass);
  const lastData = results.filter(r => r.pass).pop()?.data;

  // 打印失败详情
  if (failures.length > 0) {
    failures.forEach(f => {
      console.log(`  ❌ run#${f.run}: ${f.error}`);
    });
  }

  return { id, name, passed, total: n, avgMs, failures, lastData };
}

// ── 数据链路测试 ─────────────────────────────────────────────────────────────

/**
 * 运行一条数据链路（验证步骤间输入/输出衔接）
 * @param {object} chainDef  - 来自 schemas.js 的链路定义
 * @param {object} initArgs  - 初始参数（如 workOrderNum）
 * @param {object} targets   - { jlId, erpId }
 */
async function runChainTest(chainDef, initArgs, targets, STEPS) {
  console.log(`\n─── 链路 ${chainDef.id}: ${chainDef.name} ───`);
  const ctx = {};  // 累积各步骤输出
  let allPassed = true;

  for (const { stepId, getArgs } of chainDef.steps) {
    const stepDef = STEPS[stepId];
    const stepArgs = getArgs(ctx, initArgs);

    // 检查必要参数
    const missingArgs = (stepDef.argKeys || []).filter(k => !stepArgs[k]);
    if (missingArgs.length > 0) {
      console.log(`  ⚠  ${stepId} 跳过（上游未提供参数: ${missingArgs.join(', ')}）`);
      allPassed = false;
      continue;
    }

    process.stdout.write(`  ${stepId} (${stepDef.name}): `);

    try {
      const targetId = stepDef.resetTarget === 'jl' ? targets.jlId : targets.erpId;
      const reset = stepDef.resetTarget === 'jl' ? resetJl : resetErp;
      await reset(targetId);

      if (stepDef.prerequisite) {
        const preCmd = stepDef.prerequisite.cliCmd(stepArgs);
        const preResult = runCmd(preCmd);
        if (!preResult.success) throw new Error(`前置失败: ${preResult.error}`);
      }

      const cliArgs = stepDef.cliCmd(stepArgs);
      const result = runCmd(cliArgs);

      if (!result.success) {
        console.log(`✗ ${result.error}`);
        allPassed = false;
        continue;
      }

      const schemaErrors = validateSchema(result.data, stepDef.schema || {});
      const customErrors = stepDef.customValidate ? stepDef.customValidate(result.data) : [];
      const errors = [...schemaErrors, ...customErrors];

      if (errors.length > 0) {
        console.log(`✗ 校验失败: ${errors.join('; ')}`);
        allPassed = false;
      } else {
        ctx[stepId] = result.data;
        // 验证下游字段
        if (stepDef.downstream) {
          const downstream = stepDef.downstream(result.data);
          const missingDownstream = Object.entries(downstream)
            .filter(([k, v]) => v === undefined || v === null || v === '')
            .map(([k]) => k);
          if (missingDownstream.length > 0) {
            console.log(`✓（但下游字段为空: ${missingDownstream.join(', ')}）`);
          } else {
            console.log('✓');
          }
        } else {
          console.log('✓');
        }
      }
    } catch (e) {
      console.log(`✗ ${e.message}`);
      allPassed = false;
    }
  }

  return allPassed;
}

// ── L0 基础设施检查 ──────────────────────────────────────────────────────────

async function runL0() {
  console.log('\n═══ L0 基础设施检查 ═══\n');
  const checks = [];

  // 1. CDP 连通
  try {
    const targets = await cdp.getTargets();
    checks.push({ name: 'CDP 代理连通', pass: Array.isArray(targets), detail: `${targets.length} 个 targets` });

    // 2. 鲸灵 target
    const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
    checks.push({ name: '鲸灵 target 存在', pass: !!jl, detail: jl ? jl.url.substring(0, 60) : '未找到' });

    // 3. ERP target
    const erp = targets.find(t => t.url && t.url.includes('superboss.cc'));
    checks.push({ name: 'ERP target 存在', pass: !!erp, detail: erp ? erp.url.substring(0, 60) : '未找到' });

    if (jl) {
      // 4. 鲸灵已登录
      const jlUrl = await cdp.eval(jl.targetId, 'window.location.href');
      const jlLoggedIn = !jlUrl.includes('login') && !jlUrl.includes('sso');
      checks.push({ name: '鲸灵已登录', pass: jlLoggedIn, detail: jlUrl.substring(0, 80) });
    }

    if (erp) {
      // 5. ERP 已登录
      const CHECK_JS = `(function(){
        var sessionExpired = !!document.querySelector('.inner-login-wrapper');
        return JSON.stringify({loggedIn: !sessionExpired && document.title.includes('快麦ERP--'), title: document.title});
      })()`;
      const erpStatus = await cdp.eval(erp.targetId, CHECK_JS);
      checks.push({ name: 'ERP 已登录', pass: erpStatus.loggedIn, detail: erpStatus.title });
    }
  } catch (e) {
    checks.push({ name: 'CDP 代理连通', pass: false, detail: e.message });
  }

  // 6. CLI 基本可用
  try {
    const listResult = runCmd(['list']);
    checks.push({ name: 'CLI list 可用', pass: listResult.success !== undefined, detail: listResult.success ? '✓' : listResult.error });
  } catch (e) {
    checks.push({ name: 'CLI list 可用', pass: false, detail: e.message });
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

// ── 汇总报告 ─────────────────────────────────────────────────────────────────

function printReport(results) {
  console.log('\n' + '─'.repeat(64));
  console.log('┌──────────────────────────────────┬──────┬──────┬──────────┐');
  console.log('│ 步骤                              │ 通过  │ 失败  │ 平均耗时  │');
  console.log('├──────────────────────────────────┼──────┼──────┼──────────┤');
  for (const r of results) {
    const label = `${r.id} ${r.name}`.substring(0, 32).padEnd(32);
    const pass = `${r.passed}/${r.total}`.padEnd(4);
    const fail = `${r.total - r.passed}`.padEnd(4);
    const ms = `${r.avgMs}ms`.padEnd(8);
    console.log(`│ ${label} │ ${pass} │ ${fail} │ ${ms} │`);
  }
  console.log('└──────────────────────────────────┴──────┴──────┴──────────┘');

  const allFailures = results.flatMap(r =>
    r.failures.map(f => ({ ...f, stepId: r.id }))
  );
  if (allFailures.length > 0) {
    console.log('\n失败详情:');
    for (const f of allFailures) {
      console.log(`  ${f.stepId} run#${f.run} (${f.elapsed}ms): ${f.error}`);
    }
  }
}

module.exports = { runL0, runStepTest, runChainTest, printReport, runCmd, resetJl, resetErp };
