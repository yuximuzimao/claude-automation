'use strict';
/**
 * 商品匹配与售后系统共享同一个 ERP 标签页。
 *
 * 当前规则：
 * - 商品匹配开始前由用户手动停止售后系统；
 * - product-mapping 只验证售后确实处于 paused 状态，不再自动 emergency-stop，也不设置定时恢复；
 * - 任一异常/中断后保持售后停止，避免破坏 ERP 现场；
 * - 只有最终 check 完整通过完成门禁后，才自动调用 /api/resume 恢复售后。
 */

const AFTERSALES_API = 'http://localhost:3457/api';

async function ensureAftersalesPaused() {
  let res;
  try {
    res = await fetch(`${AFTERSALES_API}/op-queue`);
  } catch (e) {
    // 售后服务本身未运行时不存在并发扫描风险。
    if (process.env.VERBOSE) {
      process.stderr.write(`[aftersales-guard] 售后服务未运行，跳过暂停状态检查: ${e.message}\n`);
    }
    return { reachable: false, paused: true };
  }

  if (!res.ok) {
    throw new Error(`无法确认售后系统停止状态（HTTP ${res.status}），请先手动确认售后系统已停止再继续`);
  }

  const state = await res.json();
  if (!state || state.paused !== true) {
    throw new Error('商品匹配开始前请先手动停止售后系统；当前检测到售后仍在运行');
  }

  return { reachable: true, paused: true };
}

async function resumeAftersales() {
  let res;
  try {
    res = await fetch(`${AFTERSALES_API}/resume`, { method: 'POST' });
  } catch (e) {
    throw new Error(`最终核查已通过，但售后系统自动恢复失败，请手动恢复：${e.message}`);
  }

  if (!res.ok) {
    throw new Error(`最终核查已通过，但售后系统自动恢复失败（HTTP ${res.status}），请手动恢复`);
  }

  if (process.env.VERBOSE) process.stderr.write('[aftersales-guard] 最终核查通过，售后系统已恢复\n');
  return { resumed: true };
}

module.exports = { ensureAftersalesPaused, resumeAftersales };
