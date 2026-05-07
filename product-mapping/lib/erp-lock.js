'use strict';
/**
 * ERP 操作锁：product-mapping 操作 ERP 时临时暂停 aftersales server
 *
 * 为什么需要这个：aftersales server.js 有定时任务（心跳/扫描）会导航 ERP tab、
 * 关闭所有弹窗，与 product-mapping 操作同一个 ERP tab 时造成干扰。
 *
 * 设计：
 * - acquireErpLock() 调 aftersales POST /api/emergency-stop 暂停其活动
 * - releaseErpLock() 调 POST /api/resume 恢复
 * - 5 分钟超时保护：防止 product-mapping 异常退出导致 aftersales 永久暂停
 * - 重入安全：已加锁时再 acquire 只重置超时计时器，不重复 POST
 * - 降级：aftersales server 未运行时静默忽略
 */

const AFTERSALES_API = 'http://localhost:3457/api';
const MAX_LOCK_MS = 5 * 60 * 1000; // 5 分钟超时保护

let locked = false;
let lockTimer = null;

async function _doEmergencyStop() {
  const res = await fetch(`${AFTERSALES_API}/emergency-stop`, { method: 'POST' });
  if (process.env.VERBOSE) process.stderr.write('[erp-lock] aftersales 已暂停\n');
}

async function _doResume() {
  await fetch(`${AFTERSALES_API}/resume`, { method: 'POST' });
  if (process.env.VERBOSE) process.stderr.write('[erp-lock] aftersales 已恢复\n');
}

function _resetTimer() {
  if (lockTimer) clearTimeout(lockTimer);
  lockTimer = setTimeout(async () => {
    locked = false;
    lockTimer = null;
    try { await _doResume(); } catch (_) {}
  }, MAX_LOCK_MS);
}

/**
 * 在 ERP 操作前调用。已加锁时只重置超时计时器（延长保护窗口）。
 */
async function acquireErpLock() {
  _resetTimer();
  if (locked) return; // 已加锁，只重置计时器
  locked = true;
  try {
    await _doEmergencyStop();
  } catch (_) {
    // aftersales server 未运行，无需锁
    if (process.env.VERBOSE) process.stderr.write('[erp-lock] aftersales server 未运行，跳过\n');
  }
}

/**
 * 在 ERP 操作完成（或失败）后调用。通常放在 try/finally 里。
 */
async function releaseErpLock() {
  if (lockTimer) { clearTimeout(lockTimer); lockTimer = null; }
  if (!locked) return;
  locked = false;
  try {
    await _doResume();
  } catch (_) {
    // aftersales server 未运行，忽略
  }
}

module.exports = { acquireErpLock, releaseErpLock };
