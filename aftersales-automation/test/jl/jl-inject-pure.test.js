'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const JL_JS = path.join(__dirname, '../../../sessions/jl.js');

function injectSessionSource() {
  const source = fs.readFileSync(JL_JS, 'utf8');
  const start = source.indexOf('async function injectSession');
  const end = source.indexOf('// 主入口');
  assert.notEqual(start, -1, '找不到 injectSession 函数');
  assert.notEqual(end, -1, '找不到主入口边界');
  return source.slice(start, end);
}

test('jl inject 只注入认证态，不主动导航或依赖导航后页面自检', () => {
  const source = injectSessionSource();

  assert.equal(source.includes("'Page.navigate'"), false);
  assert.equal(source.includes('"Page.navigate"'), false);
  assert.equal(source.includes('document.readyState'), false);
  assert.equal(source.includes('__vue__'), false);
  assert.equal(source.includes('window.location.href'), false);
});
