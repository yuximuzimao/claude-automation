'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const navigateSource = fs.readFileSync(path.join(__dirname, '../lib/navigate.js'), 'utf8');
const workflowSource = fs.readFileSync(path.join(__dirname, '../lib/workflow.js'), 'utf8');
const cdpSource = fs.readFileSync(path.join(__dirname, '../lib/cdp.js'), 'utf8');

test('ERP 导航先激活标签页，并且已在目标页时仍等待页面内容就绪', () => {
  assert.match(navigateSource, /async function navigateErp[\s\S]*await cdp\.activateTarget\(targetId\)[\s\S]*if \(currentHash === hash\) \{[\s\S]*await waitForPageContent\(targetId\)/);
});

test('每条处理前激活 ERP，单号写入确认成功后才允许按 Enter', () => {
  assert.match(workflowSource, /async function processOne[\s\S]*await cdp\.activateTarget\(targetId\)/);
  assert.match(workflowSource, /await cdp\.typeText\(targetId, tracking\)[\s\S]*确认快递单号输入成功[\s\S]*await cdp\.key\(targetId, 'Enter'\)/);
});

test('文本输入和 Enter 在真正发送 CDP Input 事件前都会重新激活目标标签页', () => {
  assert.match(cdpSource, /async function key\(targetId, keyName\) \{\s*await activateTarget\(targetId\);[\s\S]*Input\.dispatchKeyEvent/);
  assert.match(cdpSource, /async function typeText\(targetId, text\) \{\s*await activateTarget\(targetId\);[\s\S]*Input\.insertText/);
});
