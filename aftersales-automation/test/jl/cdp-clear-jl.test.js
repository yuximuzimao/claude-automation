'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');

// mock cdp.cdpCall + cdp.eval，验证 clearJlCookiesAndStorage 行为
function withMockedCdp(getCookiesResults, fn) {
  const origCdpCall = cdp.cdpCall;
  const origEval = cdp.eval;
  const calls = { cdpCall: [], eval: [], deleted: [] };
  const results = Array.isArray(getCookiesResults) ? getCookiesResults : [getCookiesResults, { cookies: [] }];
  let getCookiesIndex = 0;
  cdp.cdpCall = async (targetId, method, params) => {
    calls.cdpCall.push({ method, params });
    if (method === 'Network.getCookies') return results[getCookiesIndex++] || { cookies: [] };
    if (method === 'Network.deleteCookies') { calls.deleted.push(params); return {}; }
    return {};
  };
  cdp.eval = async (targetId, js) => { calls.eval.push(js); return 'ok'; };
  return Promise.resolve()
    .then(() => fn(calls))
    .finally(() => { cdp.cdpCall = origCdpCall; cdp.eval = origEval; });
}

const MIXED_COOKIES = {
  cookies: [
    { name: 'JSESSIONID', domain: 'seller-portal.jlsupp.com', path: '/merchant' },
    { name: '_us', domain: 'seller-portal.jlsupp.com', path: '/' },
    { name: 'ssxmod_itna', domain: '.jlsupp.com', path: '/' },
    // ERP cookie —— 绝不能被删
    { name: 'JSESSIONID', domain: 'viperp.superboss.cc', path: '/' },
    { name: 'erp_token', domain: '.superboss.cc', path: '/' },
  ],
};

test('clearJlCookiesAndStorage：只删 jlsupp 域，绝不碰 ERP(superboss.cc)', async () => {
  await withMockedCdp(MIXED_COOKIES, async (calls) => {
    await cdp.clearJlCookiesAndStorage('tab-x');
    // 删了 3 条 jlsupp
    assert.equal(calls.deleted.length, 3);
    // 每条 deleteCookies 的 domain 从不含 superboss.cc
    for (const d of calls.deleted) {
      assert.equal(/superboss\.cc/.test(d.domain), false, `误删 ERP: ${d.domain}`);
      assert.ok(d.name && d.domain && d.path, '删除参数必须带齐 name+domain+path');
    }
    // 确实删了 jlsupp 的认证凭证
    const deletedKeys = calls.deleted.map(d => `${d.name}@${d.domain}${d.path}`);
    assert.ok(deletedKeys.includes('JSESSIONID@seller-portal.jlsupp.com/merchant'));
    assert.ok(deletedKeys.includes('_us@seller-portal.jlsupp.com/'));
  });
});

test('clearJlCookiesAndStorage：getCookies 显式带全 jlsupp 子域 urls', async () => {
  await withMockedCdp(MIXED_COOKIES, async (calls) => {
    await cdp.clearJlCookiesAndStorage('tab-x');
    const getCalls = calls.cdpCall.filter(c => c.method === 'Network.getCookies');
    assert.equal(getCalls.length, 2, '删除后必须再次读取 cookie 验证认证态已清除');
    for (const getCall of getCalls) {
      assert.ok(getCall.params.urls, 'getCookies 必须带 urls（否则漏 seller-portal 的 JSESSIONID）');
      const urls = getCall.params.urls.join(' ');
      assert.ok(urls.includes('scrm.jlsupp.com'));
      assert.ok(urls.includes('seller-portal.jlsupp.com'));
    }
  });
});

test('clearJlCookiesAndStorage：清理后认证 Cookie 已消失则返回验证结果，WAF/设备 Cookie 可重生', async () => {
  const regeneratedCookies = {
    cookies: [
      { name: 'ssxmod_itna', value: 'waf-regenerated', domain: '.jlsupp.com', path: '/' },
      { name: 'device_id', value: 'device-regenerated', domain: 'scrm.jlsupp.com', path: '/' },
    ],
  };
  await withMockedCdp([MIXED_COOKIES, regeneratedCookies], async () => {
    const result = await cdp.clearJlCookiesAndStorage('tab-x');
    assert.equal(result.verified, true);
    assert.deepEqual(result.remainingAuthCookies, []);
  });
});

test('clearJlCookiesAndStorage：清理后 JSESSIONID 或 _us 仍在则抛错且不泄露 Cookie 值', async () => {
  const secretSession = 'secret-session-value';
  const secretUs = 'secret-us-value';
  const remaining = {
    cookies: [
      { name: 'JSESSIONID', value: secretSession, domain: 'seller-portal.jlsupp.com', path: '/merchant' },
      { name: '_us', value: secretUs, domain: 'seller-portal.jlsupp.com', path: '/' },
      { name: 'ssxmod_itna', value: 'allowed', domain: '.jlsupp.com', path: '/' },
    ],
  };
  await withMockedCdp([MIXED_COOKIES, remaining], async () => {
    let error;
    try {
      await cdp.clearJlCookiesAndStorage('tab-x');
    } catch (e) {
      error = e;
    }
    assert.ok(error, '认证 Cookie 仍在时必须阻止后续注入');
    assert.match(error.message, /认证 Cookie.*JSESSIONID.*_us/);
    assert.match(error.message, /seller-portal\.jlsupp\.com/);
    assert.match(error.message, /\/merchant/);
    assert.equal(error.message.includes(secretSession), false);
    assert.equal(error.message.includes(secretUs), false);
  });
});

test('clearJlCookiesAndStorage：清 localStorage + sessionStorage', async () => {
  await withMockedCdp(MIXED_COOKIES, async (calls) => {
    await cdp.clearJlCookiesAndStorage('tab-x');
    const js = calls.eval.join(';');
    assert.ok(js.includes('localStorage.clear()'));
    assert.ok(js.includes('sessionStorage.clear()'));
  });
});

test('clearJlCookiesAndStorage：绝不使用 Network.clearBrowserCookies（会清掉 ERP）', async () => {
  await withMockedCdp(MIXED_COOKIES, async (calls) => {
    await cdp.clearJlCookiesAndStorage('tab-x');
    const methods = calls.cdpCall.map(c => c.method);
    assert.equal(methods.includes('Network.clearBrowserCookies'), false);
  });
});

test('clearJlCookiesAndStorage：某次 deleteCookies 抛错则整体抛出（报错即停）', async () => {
  const origCdpCall = cdp.cdpCall;
  const origEval = cdp.eval;
  let deleteCount = 0;
  cdp.cdpCall = async (targetId, method) => {
    if (method === 'Network.getCookies') return MIXED_COOKIES;
    if (method === 'Network.deleteCookies') {
      deleteCount++;
      if (deleteCount === 2) throw new Error('CDP timeout');
      return {};
    }
    return {};
  };
  cdp.eval = async () => 'ok';
  try {
    await assert.rejects(() => cdp.clearJlCookiesAndStorage('tab-x'), /CDP timeout/);
    // 第2条就抛，不会删完3条
    assert.ok(deleteCount === 2, '抛错后不应继续删');
  } finally {
    cdp.cdpCall = origCdpCall;
    cdp.eval = origEval;
  }
});
