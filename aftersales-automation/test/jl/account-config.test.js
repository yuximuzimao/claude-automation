const test = require('node:test');
const assert = require('node:assert/strict');
const { buildSavedAccountConfig } = require('../../lib/jl-account-config');

test('buildSavedAccountConfig preserves phone and existing account fields', () => {
  const existing = {
    file: 'account5.json',
    name: '账号5',
    note: '共途-KGOS',
    phone: '19357607791',
    url: 'https://scrm.jlsupp.com/custom',
  };

  const saved = buildSavedAccountConfig(existing, 'account5.json', '5');

  assert.deepEqual(saved, existing);
});

test('buildSavedAccountConfig fills defaults for new account', () => {
  const saved = buildSavedAccountConfig(null, 'account14.json', '14');

  assert.deepEqual(saved, {
    file: 'account14.json',
    name: '账号14',
    note: '',
  });
});
