'use strict';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 重试直到成功或超出次数
async function retry(fn, { maxRetries = 2, delayMs = 2000, label = '' } = {}) {
  let lastErr;
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (i < maxRetries) {
        if (process.env.VERBOSE) process.stderr.write(`[retry] ${label} 第${i+1}次失败: ${e.message}，${delayMs}ms后重试\n`);
        await sleep(delayMs);
      }
    }
  }
  throw lastErr;
}

// 轮询直到条件成立
async function waitFor(fn, { timeoutMs = 10000, intervalMs = 500, label = '' } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await fn();
    if (result) return result;
    await sleep(intervalMs);
  }
  throw new Error(`waitFor 超时: ${label}`);
}

module.exports = { sleep, retry, waitFor };
