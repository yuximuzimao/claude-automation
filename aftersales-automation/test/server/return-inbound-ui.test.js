'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const appSource = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
const htmlSource = fs.readFileSync(path.join(__dirname, '../../public/index.html'), 'utf8');
const queueSource = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');

test('退货入库页面提供独立停止按钮，并复用 op-queue 取消接口', () => {
  assert.match(htmlSource, /id="ri-stop-btn"[^>]*onclick="riStop\(\)"[^>]*disabled/);
  assert.match(appSource, /async function riStop\(\)[\s\S]*\/api\/op-queue\/[\s\S]*method: 'DELETE'/);
});

test('退货入库逐条完成事件立即更新结果表', () => {
  assert.match(appSource, /function riOnProgress\(data\)[\s\S]*phase === 'completed'[\s\S]*_riResults\[lastResult\.tracking\][\s\S]*riRenderResults\(\)/);
});

test('退货入库停止只在单条边界检查中断，不侵入 processOne 提交过程', () => {
  assert.match(queueSource, /for \(let i = 0; i < total; i\+\+\) \{\s*assertNotAborted\(op\);[\s\S]*await processOne\(targetId, tracking\)/);
});
