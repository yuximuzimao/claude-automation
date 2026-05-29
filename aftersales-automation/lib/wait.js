'use strict';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── 风控信号检测 ──────────────────────────────────────────────
// 精确匹配已知风控/反爬信号。不用"非 2xx 全部风控"这种粗暴规则
// ——登录过期 401、页面 302 跳转、iframe 加载失败 204 不是风控信号。
function isRiskControlError(errMsg) {
  const signals = [
    'HTTP 426', 'X-Tengine-Error', 'denied by http_ratelimit',
    'ratelimit', 'anti-bot', 'captcha', 'challenge',
    '访问过于频繁', '操作频率过高',
  ];
  return signals.some(s => (errMsg || '').toLowerCase().includes(s.toLowerCase()));
}

// ── 域名黑名单：这些域名下的操作报错即停，绝不重试 ──────────
// 鲸灵风控将重复失败操作识别为自动化攻击。单次失败不封，自动重试会封。
const FORCE_NO_RETRY_DOMAINS = ['scrm.jlsupp.com'];

// ── 重试 ──────────────────────────────────────────────────────
// maxRetries = 首次尝试之后的额外重试次数（不是总次数）:
//   maxRetries=0 → 执行 1 次，失败即停
//   maxRetries=1 → 执行 1 次，失败后重试 1 次（共 2 次）
//
// domain 参数可选，仅供文档化调用意图。缺省时不做域名检查。
// domain 命中 FORCE_NO_RETRY_DOMAINS 时强制 maxRetries=0，
// 忽略调用方传入值——风控不是靠纪律防的，基础设施层兜底。
async function retry(fn, { maxRetries = 2, delayMs = 2000, label = '', domain = '' } = {}) {
  // 域名自动识别：命中黑名单 → 强制不重试
  if (domain && FORCE_NO_RETRY_DOMAINS.some(d => domain.includes(d))) {
    maxRetries = 0;
  }

  let lastErr;
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      // 就地熔断检测：风控信号一旦出现，立即停止，不依赖上层
      if (isRiskControlError(e.message)) {
        if (typeof globalThis.__tripCircuitBreaker === 'function') {
          globalThis.__tripCircuitBreaker(e, label);
        }
        throw e;  // 原样抛出，不包装——保证错误传递链路完整
      }
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
