'use strict';
// 步骤定义 + 输出校验 schema
// 参考 aftersales-automation/test/schemas.js 的模式

const STEPS = {

  // ── L1 单元测试（不需要浏览器）────────────────────────────

  'L1-safe-write': {
    id: 'L1-safe-write',
    name: 'safe-write 原子写入',
    level: 'L1',
    resetTarget: null, // 无浏览器
  },

  'L1-annotate': {
    id: 'L1-annotate',
    name: 'annotate 类型标注',
    level: 'L1',
    resetTarget: null,
  },

  'L1-match-one-logic': {
    id: 'L1-match-one-logic',
    name: 'match-one 编排器逻辑',
    level: 'L1',
    resetTarget: null,
  },

  // ── L2 基础设施测试 ─────────────────────────────────────

  'L2-targets': {
    id: 'L2-targets',
    name: '浏览器标签检测',
    level: 'L2',
    resetTarget: null,
  },

  'L2-cdp': {
    id: 'L2-cdp',
    name: 'CDP 通信',
    level: 'L2',
    resetTarget: null,
  },

  'L2-navigate': {
    id: 'L2-navigate',
    name: 'ERP 页面导航',
    level: 'L2',
    resetTarget: 'erp',
  },

  // ── L2 页面操作测试 ─────────────────────────────────────

  'L2-ensure-corr-page': {
    id: 'L2-ensure-corr-page',
    name: '对应表页面守卫',
    level: 'L2',
    resetTarget: 'erp',
  },

  'L2-read-table-rows': {
    id: 'L2-read-table-rows',
    name: '表格 DOM 读取',
    level: 'L2',
    resetTarget: 'erp',
  },

  'L2-download-products': {
    id: 'L2-download-products',
    name: '下载平台商品',
    level: 'L2',
    resetTarget: 'erp',
    destructive: true, // 会触发下载弹窗
  },

  // ── L2 SKU 读写测试 ─────────────────────────────────────

  'L2-read-skus': {
    id: 'L2-read-skus',
    name: '读取货号 SKU 列表',
    level: 'L2',
    resetTarget: 'erp',
  },

  'L2-read-erp-codes': {
    id: 'L2-read-erp-codes',
    name: '重读验证 ERP 编码',
    level: 'L2',
    resetTarget: 'erp',
  },

  // ── L2 匹配操作测试 ─────────────────────────────────────

  'L2-remap-single': {
    id: 'L2-remap-single',
    name: '单品换绑',
    level: 'L2',
    resetTarget: 'erp',
    destructive: true, // 会修改对应表绑定
  },

  'L2-create-suite': {
    id: 'L2-create-suite',
    name: '创建套件',
    level: 'L2',
    resetTarget: 'erp',
    destructive: true, // 会创建套件
  },

  'L2-verify-archive': {
    id: 'L2-verify-archive',
    name: '档案核查',
    level: 'L2',
    resetTarget: 'erp',
  },

  // ── L2 编排器测试 ─────────────────────────────────────

  'L2-match-one': {
    id: 'L2-match-one',
    name: 'match-one 编排器',
    level: 'L2',
    resetTarget: 'erp',
  },
};

// 只读步骤（可安全重复执行）
const READONLY_STEPS = [
  'L2-targets', 'L2-cdp', 'L2-navigate',
  'L2-ensure-corr-page', 'L2-read-table-rows',
  'L2-read-skus', 'L2-read-erp-codes',
  'L2-verify-archive',
];

// 破坏性步骤（只做预检，不实际执行）
const DESTRUCTIVE_STEPS = [
  'L2-download-products', 'L2-remap-single', 'L2-create-suite',
];

module.exports = { STEPS, READONLY_STEPS, DESTRUCTIVE_STEPS };
