'use strict';

/**
 * 操作步骤定义 + 输出 Schema
 *
 * 每个步骤包含：
 *   id         - 步骤唯一标识
 *   name       - 步骤名称
 *   resetTarget- 复原时刷新哪个页面（'jl' | 'erp'）
 *   destructive- 是否破坏性操作（只做预检，不实际提交）
 *   prerequisite- 执行前需要先运行的命令（用于 ERP-2 依赖 ERP-1 的页面状态）
 *   cliCmd     - (args) => string[]，生成 CLI 命令参数数组
 *   argKeys    - 该步骤需要哪些 args（用于提示用法）
 *   schema     - 输出 data 的字段校验规则
 *   customValidate - (data) => string[]，额外校验逻辑（可选）
 *   downstream - (data) => object，提取下游步骤所需的参数
 */

const STEPS = {

  // ── 鲸灵平台 ─────────────────────────────────────────────────

  'JL-1': {
    id: 'JL-1',
    name: '读取工单列表',
    resetTarget: 'jl',
    cliCmd: () => ['list'],
    argKeys: [],
    schema: {
      urgent: { type: 'array', required: true },
    },
    downstream: (data) => ({
      workOrderNum: data.urgent && data.urgent[0] && data.urgent[0].workOrderNum,
    }),
  },

  'JL-2': {
    id: 'JL-2',
    name: '读取工单详情',
    resetTarget: 'jl',
    cliCmd: (args) => ['read-ticket', args.workOrderNum],
    argKeys: ['workOrderNum'],
    schema: {
      // read-ticket 实际输出字段（无 workOrderNum/type，那些在 list 里）
      mainOrderId: { type: 'string', required: true, nonEmpty: true },
      subOrders: { type: 'array', required: true, minLen: 1 },
    },
    customValidate: (data) => {
      const errors = [];
      const sub = data.subOrders && data.subOrders[0];
      if (!sub) { errors.push('subOrders[0] 不存在'); return errors; }
      if (!sub.id) errors.push('subOrders[0].id 为空（→ ERP-1 无法执行）');
      if (!sub.sku) errors.push('subOrders[0].sku 为空（→ PM-1 无法执行）');
      return errors;
    },
    downstream: (data) => {
      const sub = data.subOrders && data.subOrders[0];
      const gift = data.gifts && data.gifts[0];
      return {
        subOrderId: sub && sub.id,
        sku: sub && sub.sku,
        attr1: sub && sub.attr1,
        returnTracking: data.returnTracking,
        giftSubOrderId: gift && gift.id,
      };
    },
  },

  // ── 商品查询 ─────────────────────────────────────────────────

  'PM-1': {
    id: 'PM-1',
    name: '商品对应表查specCode',
    resetTarget: 'erp',
    cliCmd: (args) => {
      const cmd = ['product-match', args.sku];
      if (args.attr1 || args.shopName) cmd.push(args.attr1 || '');
      if (args.shopName) cmd.push(args.shopName);
      return cmd;
    },
    argKeys: ['sku'],  // attr1 可选，shopName 推荐传入
    schema: {},
    customValidate: (data) => {
      const errors = [];
      if (!data.specCode && (!data.specCodes || data.specCodes.length === 0)) {
        errors.push('specCode / specCodes 均为空（→ PA-1 无法执行）');
      }
      return errors;
    },
    downstream: (data) => ({
      specCode: data.specCode || (data.specCodes && data.specCodes[0] && data.specCodes[0].code),
    }),
  },

  'PA-1': {
    id: 'PA-1',
    name: '商品档案V2查套件明细',
    resetTarget: 'erp',
    cliCmd: (args) => ['product-archive', args.specCode],
    argKeys: ['specCode'],
    schema: {
      outerId: { type: 'string', required: true, nonEmpty: true },
      title: { type: 'string', required: true },
      subItemNum: { type: 'number', required: true },
    },
    downstream: (data) => ({
      subItemNum: data.subItemNum,
      subItems: data.subItems,
    }),
  },

  // ── ERP操作 ─────────────────────────────────────────────────

  'ERP-1': {
    id: 'ERP-1',
    name: 'ERP搜索子订单',
    resetTarget: 'erp',
    cliCmd: (args) => ['erp-search', args.subOrderId],
    argKeys: ['subOrderId'],
    schema: {
      rows: { required: true },
    },
    customValidate: (data, args) => {
      const errors = [];
      if (!data.rows) { errors.push('rows 为空'); return errors; }
      const rows = data.rows.rows || data.rows;
      if (!Array.isArray(rows)) { errors.push('rows 格式不正确'); return errors; }
      if (rows.length === 0) { errors.push('搜索结果为空（0行）'); return errors; }
      // 核验：搜索结果里有没有包含目标子订单号的行
      // （textSnippet 里应包含 subOrderId，或 internalId 匹配）
      const subOrderId = data.subOrderId;
      if (subOrderId) {
        const found = rows.some(r =>
          (r.textSnippet && r.textSnippet.includes(subOrderId)) ||
          (r.internalId && String(r.internalId) === String(subOrderId))
        );
        if (!found) {
          errors.push(`搜索结果 ${rows.length} 行均不含目标子订单号 ${subOrderId}（搜索可能填错字段）`);
        }
      }
      return errors;
    },
    downstream: () => ({ rowIndex: 0 }),
  },

  'ERP-2': {
    id: 'ERP-2',
    name: 'ERP查看物流详情',
    resetTarget: 'erp',
    // ERP-2 依赖 ERP-1 的页面搜索结果状态
    // 每次测试会先执行 prerequisite（不算入 ERP-2 的测试时间）
    prerequisite: {
      cliCmd: (args) => ['erp-search', args.subOrderId],
      argKeys: ['subOrderId'],
    },
    cliCmd: (args) => ['erp-logistics', String(args.rowIndex !== undefined ? args.rowIndex : 0)],
    argKeys: ['subOrderId'],  // subOrderId 用于 prerequisite
    schema: {
      // logisticsText 可以为空（订单未发货或搜索结果不含目标订单时正常为空）
      logisticsText: { type: 'string', required: true },
      tracking: { type: 'string', required: true },
    },
    downstream: (data) => ({ logistics: data.logisticsText }),
  },

  'ERP-3': {
    id: 'ERP-3',
    name: 'ERP售后入库查询',
    resetTarget: 'erp',
    cliCmd: (args) => ['erp-aftersale', args.returnTracking],
    argKeys: ['returnTracking'],
    schema: {
      rows: { type: 'array', required: true },
    },
    downstream: (data) => ({ aftersaleRows: data.rows }),
  },

  // ── 鲸灵物流 ─────────────────────────────────────────────────

  'JL-5': {
    id: 'JL-5',
    name: '鲸灵物流查询',
    resetTarget: 'jl',
    cliCmd: (args) => ['logistics', args.workOrderNum],
    argKeys: ['workOrderNum'],
    schema: {
      packages: { type: 'array', required: true, minLen: 1 },
    },
    customValidate: (data) => {
      const errors = [];
      if (!data.packages) return errors;
      data.packages.forEach((pkg, i) => {
        if (!pkg.tab) errors.push(`packages[${i}].tab 为空`);
        if (!pkg.text) errors.push(`packages[${i}].text 为空（无物流文字）`);
      });
      return errors;
    },
    downstream: (data) => ({ packages: data.packages }),
  },

  // ── 破坏性操作（预检模式）────────────────────────────────────

  'JL-3': {
    id: 'JL-3',
    name: '拒绝退款',
    resetTarget: 'jl',
    destructive: true,
    cliCmd: (args) => ['reject', args.workOrderNum, args.reason, args.detail],
    argKeys: ['workOrderNum', 'reason', 'detail'],
    schema: { rejected: { required: true } },
  },

  'JL-4': {
    id: 'JL-4',
    name: '同意退款',
    resetTarget: 'jl',
    destructive: true,
    cliCmd: (args) => ['approve', args.workOrderNum],
    argKeys: ['workOrderNum'],
    schema: { approved: { required: true } },
  },

  'NOTE-1': {
    id: 'NOTE-1',
    name: '添加内部备注',
    resetTarget: 'jl',
    destructive: true,
    cliCmd: (args) => ['add-note', args.workOrderNum, args.note],
    argKeys: ['workOrderNum', 'note'],
    schema: {},
  },
};

// 只读步骤（可跑10次）
const READONLY_STEPS = ['JL-1', 'JL-2', 'JL-5', 'PM-1', 'PA-1', 'ERP-1', 'ERP-2', 'ERP-3'];

// 数据链路定义（L2 测试）
const CHAINS = [
  {
    id: 'chain-1',
    name: 'JL-1 → JL-2',
    description: '工单列表提供工单号给详情查询',
    steps: [
      { stepId: 'JL-1', getArgs: () => ({}) },
      { stepId: 'JL-2', getArgs: (ctx) => ({ workOrderNum: ctx['JL-1'].urgent && ctx['JL-1'].urgent[0] && ctx['JL-1'].urgent[0].workOrderNum }) },
    ],
  },
  {
    id: 'chain-2',
    name: 'JL-2 → ERP-1',
    description: '工单详情提供子订单号给ERP搜索',
    steps: [
      { stepId: 'JL-2', getArgs: (ctx, initArgs) => ({ workOrderNum: initArgs.workOrderNum }) },
      { stepId: 'ERP-1', getArgs: (ctx) => ({ subOrderId: ctx['JL-2'].subOrders && ctx['JL-2'].subOrders[0] && ctx['JL-2'].subOrders[0].id }) },
    ],
  },
  {
    id: 'chain-3',
    name: 'JL-2 → PM-1 → PA-1',
    description: '工单详情 → 商品对应表 → 商品档案',
    steps: [
      { stepId: 'JL-2', getArgs: (ctx, initArgs) => ({ workOrderNum: initArgs.workOrderNum }) },
      { stepId: 'PM-1', getArgs: (ctx, initArgs) => {
        const sub = ctx['JL-2'].subOrders && ctx['JL-2'].subOrders[0];
        return { sku: sub && sub.sku, attr1: sub && sub.attr1, shopName: initArgs.shopName };
      }},
      { stepId: 'PA-1', getArgs: (ctx) => ({ specCode: ctx['PM-1'].specCode || (ctx['PM-1'].specCodes && ctx['PM-1'].specCodes[0] && ctx['PM-1'].specCodes[0].code) }) },
    ],
  },
  {
    id: 'chain-4',
    name: 'JL-2 → ERP-3',
    description: '工单详情提供退货快递单号给售后入库查询',
    steps: [
      { stepId: 'JL-2', getArgs: (ctx, initArgs) => ({ workOrderNum: initArgs.workOrderNum }) },
      { stepId: 'ERP-3', getArgs: (ctx) => ({ returnTracking: ctx['JL-2'].returnTracking }) },
    ],
  },
  {
    id: 'chain-5',
    name: 'ERP-1 → ERP-2',
    description: 'ERP搜索后读物流（页面状态耦合）',
    steps: [
      { stepId: 'ERP-1', getArgs: (ctx, initArgs) => ({ subOrderId: initArgs.subOrderId }) },
      { stepId: 'ERP-2', getArgs: (ctx, initArgs) => ({ subOrderId: initArgs.subOrderId, rowIndex: 0 }) },
    ],
  },
  {
    id: 'chain-6',
    name: 'JL-2 → JL-5',
    description: '工单详情 → 鲸灵物流查询（仅退款-已发货核心链路）',
    steps: [
      { stepId: 'JL-2', getArgs: (ctx, initArgs) => ({ workOrderNum: initArgs.workOrderNum }) },
      { stepId: 'JL-5', getArgs: (ctx, initArgs) => ({ workOrderNum: initArgs.workOrderNum }) },
    ],
  },
];

module.exports = { STEPS, READONLY_STEPS, CHAINS };
