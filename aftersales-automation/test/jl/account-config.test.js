const test = require('node:test');
const assert = require('node:assert/strict');
const {
  buildSavedAccountConfig,
  extractInitialPhoneFromStorageState,
} = require('../../lib/jl-account-config');

function makeStorageState(supplierInfoValue) {
  return {
    cookies: [],
    origins: [{
      origin: 'https://scrm.jlsupp.com',
      localStorage: [{ name: 'supplierInfo', value: supplierInfoValue }],
    }],
  };
}

test('extractInitialPhoneFromStorageState reads the first saved supplier mobile as a string', () => {
  const storageState = makeStorageState(JSON.stringify({
    supplierMobileList: [13800138000],
    supplierMobile: 13900139000,
  }));

  assert.equal(extractInitialPhoneFromStorageState(storageState), '13800138000');
});

test('extractInitialPhoneFromStorageState ignores missing or malformed supplier info', () => {
  assert.equal(extractInitialPhoneFromStorageState({ origins: [] }), null);
  assert.equal(extractInitialPhoneFromStorageState(makeStorageState('{bad-json')), null);
  assert.equal(extractInitialPhoneFromStorageState(
    makeStorageState(JSON.stringify({ supplierMobileList: [] }))
  ), null);
});

test('buildSavedAccountConfig preserves phone and existing account fields', () => {
  const existing = {
    file: 'account5.json',
    name: '账号5',
    note: '共途-KGOS',
    phone: '19357607791',
    url: 'https://scrm.jlsupp.com/custom',
  };

  const saved = buildSavedAccountConfig(existing, 'account5.json', '5', {
    initialPhone: '13800138000',
  });

  assert.deepEqual(saved, existing);
});

test('buildSavedAccountConfig initializes phone only when the account has none', () => {
  const existing = {
    file: 'account15.json',
    name: '账号15',
    note: '鑫润泽-钥黑',
    scanEnabled: true,
  };

  const saved = buildSavedAccountConfig(existing, 'account15.json', '15', {
    initialPhone: '13800138000',
  });

  assert.equal(saved.phone, '13800138000');
  assert.equal(saved.note, '鑫润泽-钥黑');
  assert.equal(saved.scanEnabled, true);
});

test('buildSavedAccountConfig fills defaults for new account', () => {
  const saved = buildSavedAccountConfig(null, 'account14.json', '14');

  assert.deepEqual(saved, {
    file: 'account14.json',
    name: '账号14',
    note: '',
  });
});
