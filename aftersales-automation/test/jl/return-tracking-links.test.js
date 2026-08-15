'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { readReturnTrackingLinksFromPage } = require('../../lib/jl/return-tracking-links');
const { READ_ORDER_INFO_JS } = require('../../lib/jl/read-ticket');

const CURRENT = '100001786536527848963';
const RELATED = '100001786536537201140';
const TRACKING = 'JT3173581151071';

function documentFixture({ bodyText = '', reference, tooltip } = {}) {
  return {
    body: { innerText: bodyText },
    querySelectorAll(selector) {
      assert.equal(selector, '[aria-describedby], [aria-controls]');
      return reference ? [reference] : [];
    },
    getElementById(id) {
      return tooltip && tooltip.id === id ? tooltip : null;
    },
  };
}

test('优先从 Vue 物流结构读取关联工单号，并按当前退货单号过滤', () => {
  const rootVm = {
    $children: [{
      $props: {
        logisticsInfoList: [
          {
            logisticsNum: TRACKING,
            logisticsUsedWorkOrderNumList: [RELATED, RELATED],
          },
          {
            logisticsNum: 'OTHER-TRACKING',
            logisticsUsedWorkOrderNumList: [CURRENT],
          },
          {
            logisticsUsedWorkOrderNumList: [CURRENT],
          },
        ],
      },
      $children: [],
    }],
  };

  assert.deepEqual(
    readReturnTrackingLinksFromPage(documentFixture(), rootVm, TRACKING),
    { multiUse: true, usedBy: [RELATED] }
  );
});

test('关联号只存在于隐藏 tooltip 的 textContent 时仍能读取', () => {
  const reference = {
    textContent: '多次使用',
    getAttribute(name) {
      return name === 'aria-describedby' ? 'el-popover-4316' : null;
    },
  };
  const tooltip = {
    id: 'el-popover-4316',
    style: { display: 'none' },
    textContent: '物流单号已被工单号： ' + RELATED + ' 使用',
    innerText: '',
  };
  const doc = documentFixture({
    bodyText: '退货物流单号：\n' + TRACKING + '\n多次使用',
    reference,
    tooltip,
  });

  assert.deepEqual(
    readReturnTrackingLinksFromPage(doc, null, TRACKING),
    { multiUse: true, usedBy: [RELATED] }
  );
});

test('页面有多个多次使用悬浮层时只接受当前退货单号所在物流行', () => {
  function reference(text, tooltipId, parentText) {
    return {
      textContent: text,
      parentElement: { textContent: parentText, parentElement: null },
      getAttribute(name) {
        return name === 'aria-describedby' ? tooltipId : null;
      },
    };
  }
  const references = [
    reference('多次使用', 'tooltip-current', `退货物流单号：${TRACKING}`),
    reference('多次使用', 'tooltip-other', '退货物流单号：OTHER-TRACKING'),
  ];
  const tooltips = {
    'tooltip-current': { textContent: `物流单号已被工单号：${RELATED} 使用` },
    'tooltip-other': { textContent: `物流单号已被工单号：${CURRENT} 使用` },
  };
  const doc = {
    body: { innerText: `退货物流单号：${TRACKING}\n多次使用` },
    querySelectorAll: () => references,
    getElementById: id => tooltips[id] || null,
  };

  assert.deepEqual(
    readReturnTrackingLinksFromPage(doc, null, TRACKING),
    { multiUse: true, usedBy: [RELATED] }
  );
});

test('多个悬浮层都无法与当前物流行唯一对应时不猜关联工单', () => {
  const references = ['tooltip-a', 'tooltip-b'].map(id => ({
    textContent: '多次使用',
    getAttribute: name => name === 'aria-describedby' ? id : null,
  }));
  const doc = {
    body: { innerText: `退货物流单号：${TRACKING}\n多次使用` },
    querySelectorAll: () => references,
    getElementById: id => ({ textContent: `物流单号已被工单号：${id === 'tooltip-a' ? RELATED : CURRENT} 使用` }),
  };

  assert.deepEqual(
    readReturnTrackingLinksFromPage(doc, null, TRACKING),
    { multiUse: true, usedBy: [] }
  );
});

test('正文只有多次使用但结构化字段和 tooltip 均缺失时保持 fail-closed', () => {
  const doc = documentFixture({ bodyText: '退货物流单号：\n' + TRACKING + '\n多次使用' });

  assert.deepEqual(
    readReturnTrackingLinksFromPage(doc, null, TRACKING),
    { multiUse: true, usedBy: [] }
  );
});

test('普通物流 DTO 默认空关联数组时不得误标多次使用', () => {
  const rootVm = {
    logisticsInfoList: [{
      logisticsNum: TRACKING,
      logisticsUsedWorkOrderNumList: [],
    }],
    $children: [],
  };

  assert.deepEqual(
    readReturnTrackingLinksFromPage(documentFixture(), rootVm, TRACKING),
    { multiUse: false, usedBy: [] }
  );
});

test('页面读取函数可序列化到浏览器上下文独立执行', () => {
  const browserFn = Function('return (' + readReturnTrackingLinksFromPage.toString() + ')')();
  const rootVm = {
    parcelList: [{
      logisticsNum: TRACKING,
      logisticsUsedWorkOrderNumList: [RELATED],
    }],
    $children: [],
  };

  assert.deepEqual(
    browserFn(documentFixture(), rootVm, TRACKING),
    { multiUse: true, usedBy: [RELATED] }
  );
});

test('Vue 子组件存在抛错 getter 时跳过该字段并继续读取其他组件', () => {
  const brokenVm = { $children: [] };
  Object.defineProperty(brokenVm, 'logisticsInfoList', {
    get() { throw new Error('组件已销毁'); },
  });
  const rootVm = {
    $children: [brokenVm, {
      parcelList: [{
        logisticsNum: TRACKING,
        logisticsUsedWorkOrderNumList: [RELATED],
      }],
      $children: [],
    }],
  };

  assert.deepEqual(
    readReturnTrackingLinksFromPage(documentFixture(), rootVm, TRACKING),
    { multiUse: true, usedBy: [RELATED] }
  );
});

test('完整详情页读取脚本包含可解析的关联号读取函数', () => {
  assert.doesNotThrow(() => Function('return ' + READ_ORDER_INFO_JS));
  assert.match(READ_ORDER_INFO_JS, /readReturnTrackingLinksFromPage/);
});
