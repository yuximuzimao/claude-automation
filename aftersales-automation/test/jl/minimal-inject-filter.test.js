'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  filterAuthCookies,
  filterIdentityLocalStorage,
} = require('../../lib/jl/session-filter');

test('filterAuthCookies keeps only portable auth cookies', () => {
  const cookies = filterAuthCookies([
    { name: 'JSESSIONID', value: 'redacted' },
    { name: 'ssxmod_itna', value: 'redacted' },
    { name: 'ssxmod_itna2', value: 'redacted' },
    { name: '_us', value: 'redacted' },
    { name: '_dx_app_74b6f0355db61adda5271d1fc08a9db3', value: 'device' },
    { name: 'acw_tc', value: 'network' },
    { name: 'cdn_sec_tc', value: 'network' },
  ]);

  assert.deepEqual(cookies.map(c => c.name), [
    'JSESSIONID',
    'ssxmod_itna',
    'ssxmod_itna2',
    '_us',
  ]);
});

test('filterIdentityLocalStorage keeps only account identity keys', () => {
  const items = filterIdentityLocalStorage([
    { name: '__supplierId__', value: 'redacted' },
    { name: '__subBizType__', value: 'redacted' },
    { name: 'currentSubBizType', value: 'redacted' },
    { name: 'supplierInfo', value: 'redacted' },
    { name: 'aifocus-cookie', value: 'redacted' },
    { name: '_&MONITOR_DEVICE_ID&_', value: 'device' },
    { name: '_dx_captcha_cid', value: 'device' },
    { name: 'track_info_list', value: 'tracking' },
  ]);

  assert.deepEqual(items.map(i => i.name), [
    '__supplierId__',
    '__subBizType__',
    'currentSubBizType',
    'supplierInfo',
    'aifocus-cookie',
  ]);
});
