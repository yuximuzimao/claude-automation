'use strict';
/**
 * ai-infer.js - Claude AI 推理引擎
 *
 * hint 存在时触发：Claude 读取 docs/ 里的真实规则文档 + 工单采集数据，输出处理决策。
 * 降级策略：ANTHROPIC_API_KEY 未设置或调用失败时，pipeline.js 回退到规则引擎。
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const DOCS_DIR = path.join(__dirname, '../docs');
// 通过 claude CLI 调用时不需要指定 model（使用系统默认）
const MODEL = process.env.AI_INFER_MODEL || 'claude-3-5-haiku-20241022';

// 文档缓存（服务进程内，重启后重新加载）
let _docsCache = null;

function loadRuleDocs() {
  if (_docsCache) return _docsCache;

  const files = [
    'INDEX.md',       // 总规则索引（必读）
    'flow-5.1.md',    // 退货退款
    'flow-5.2.md',    // 仅退款-未发货
    'flow-5.3.md',    // 仅退款-已发货
    'flow-5.4.md',    // 换货
    'erp-query.md',   // ERP 查询规范
  ];

  const sections = files.map(f => {
    const fpath = path.join(DOCS_DIR, f);
    try {
      const content = fs.readFileSync(fpath, 'utf8');
      return `\n\n========== ${f} ==========\n\n${content}`;
    } catch {
      return `\n\n========== ${f} ==========\n（文件未找到）`;
    }
  });

  _docsCache = sections.join('');
  return _docsCache;
}

// 通过 claude CLI 调用（使用 Claude Code 已认证的客户端，无需额外 API key）
function callClaudeCLI(system, user) {
  const claudeCmd = process.env.CLAUDE_CLI_PATH || 'claude';
  const prompt = `${system}\n\n---\n\n${user}`;

  const result = spawnSync(claudeCmd, ['-p', system, '--output-format', 'json'], {
    input: user,
    encoding: 'utf8',
    timeout: 60000,
    env: { ...process.env },
  });

  if (result.status !== 0) {
    const err = (result.stderr || result.stdout || '').slice(0, 200);
    throw new Error(`claude CLI 调用失败 (exit ${result.status}): ${err}`);
  }

  const raw = (result.stdout || '').trim();
  if (!raw) throw new Error('claude CLI 无输出');

  // 解析 --output-format json 的包装格式
  const wrapper = JSON.parse(raw);
  if (wrapper.is_error) throw new Error(`claude CLI 错误: ${wrapper.result}`);

  return wrapper.result || '';
}

// 直接 HTTP 调用（备用，适用于有原生 API key 的环境）
async function callClaudeAPI(system, user) {
  const apiKey = process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 未设置');

  const baseUrl = (process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com').replace(/\/$/, '');
  const endpoint = `${baseUrl}/v1/messages`;

  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'anthropic-version': '2023-06-01',
      'x-api-key': apiKey,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 600,
      system,
      messages: [{ role: 'user', content: user }],
    }),
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Claude API ${resp.status}: ${body.slice(0, 300)}`);
  }

  const data = await resp.json();
  return data.content[0].text;
}

function buildCompactData(cd, queueItem) {
  const ticket = (cd && cd.ticket) || {};
  const erpRows = cd.erpSearch && cd.erpSearch.rows && cd.erpSearch.rows.rows;
  const giftErpRows = cd.giftErpSearch && cd.giftErpSearch.rows && cd.giftErpSearch.rows.rows;
  const pkgs = cd.logistics && cd.logistics.packages;
  const aftersale = cd.erpAftersale;
  const subOrder = ticket.subOrders && ticket.subOrders[0];

  return {
    工单类型: queueItem.type || ticket.type,
    账号备注: queueItem.accountNote,
    售后原因: ticket.afterSaleReason || '未获取',
    售后标签: ticket.tags && ticket.tags.length ? ticket.tags.join('、') : '无',
    申请退款金额: ticket.amount ? `¥${ticket.amount}` : '未获取',
    原始支付金额: ticket.payAmount ? `¥${ticket.payAmount}` : '未获取',
    售后说明buyerRemark: ticket.buyerRemark || '无',
    售后图片: ticket.imageCount ? `有 ${ticket.imageCount} 张图片（需人工查看）` : '无',
    申请退款套数afterSaleNum: subOrder && subOrder.afterSaleNum,
    货号SKU: subOrder && subOrder.sku,
    SKU属性attr1: subOrder && subOrder.attr1,
    子订单物流状态: subOrder && subOrder.logistics,
    是否有赠品: ticket.gifts && ticket.gifts.length ? `是，${ticket.gifts.length}件赠品` : '否',
    ERP主商品状态: erpRows && erpRows[0] && erpRows[0].status,
    ERP发货快递单号: erpRows && erpRows[0] && erpRows[0].tracking,
    ERP赠品状态: giftErpRows && giftErpRows[0] && giftErpRows[0].status,
    历史售后次数: ticket.afterSaleCount || undefined,
    退货快递单号: ticket.returnTracking || '无',
    退货快递多次使用: ticket.returnTrackingMultiUse ? `是，关联工单：${(ticket.returnTrackingUsedBy || []).join('、') || '未知'}` : '否',
    我方发出包裹物流_仅退款类适用: pkgs
      ? pkgs.map(p => ({ 单号: p.num, 最新节点: (p.text || '').slice(-300) }))
      : '未获取',
    ERP售后入库记录: aftersale && aftersale.rows
      ? aftersale.rows.map(r => ({
          收货状态: r.goodsStatus,
          退货单号: r.tracking,
          退货数量: r.returnQty,
          商品明细: (r.items || []).map(i => ({ 商品: i.shortTitle, 良品数: i.qtyGood, 次品数: i.qtyBad })),
        }))
      : '无记录',
    商品档案subItemNum: cd.productArchive && cd.productArchive.subItemNum,
    采集错误: (cd.collectErrors || []).filter(e => !e.includes('正常')),
  };
}

async function inferWithAI(sim, queueItem) {
  const cd = sim.collectedData || {};
  const hint = queueItem.hint || '';
  const docs = loadRuleDocs();
  const compact = buildCompactData(cd, queueItem);

  const system = `你是鲸灵平台售后工单处理专家。你需要根据以下规则文档和采集数据，判断工单应如何处理。

## 规则文档（请严格遵守）
${docs}

## 输出要求

只输出以下 JSON，不要有任何其他内容或解释：
{"action":"approve或reject或escalate","reason":"处理理由（中文，简洁，≤80字）","confidence":"high或medium或low","warnings":["可选警告列表"]}

## 最高优先原则
- 用户评价指令的权重高于一切规则，必须优先遵从
- 数据不完整或情况不明时，选择 escalate，不要猜测
- 遇到规则未覆盖的场景，选择 escalate

## 绝对安全规则（不可被用户评价指令覆盖）
- 【退货退款】类型：只有「ERP售后入库记录」中存在「收货状态=卖家已收到退货」的行，且商品明细中良品数量≥应退数量，才能 approve。客户寄回的快递在途中、ERP无入库记录时，一律 escalate，不可 approve。
- 「我方发出包裹物流_仅退款类适用」字段仅供【仅退款-已发货】类型判断拦截/拒收，禁止用于判断【退货退款】类型的决策。
- 【退货退款】类型的退款判断依据是「ERP售后入库记录」，不是物流信息。`;

  const parts = [
    `工单号：${queueItem.workOrderNum}`,
    `\n## 采集数据\n\`\`\`json\n${JSON.stringify(compact, null, 2)}\n\`\`\``,
  ];

  if (hint) {
    parts.push(
      `\n## 用户评价指令（最高优先级，必须遵从）\n${hint}\n\n请在 reason 里说明你如何理解并执行了该指令。`
    );
  } else {
    parts.push('\n请按照规则文档判断处理方案。');
  }

  // 优先用 claude CLI（已认证，无代理限制），失败则降级 HTTP API
  let text;
  try {
    text = callClaudeCLI(system, parts.join('\n'));
  } catch (cliErr) {
    console.warn(`[ai-infer] CLI 调用失败 (${cliErr.message.slice(0, 60)})，尝试 HTTP API`);
    text = await callClaudeAPI(system, parts.join('\n'));
  }

  // 从响应中提取 JSON（防止模型在 JSON 前后输出多余文字）
  const match = text.match(/\{[\s\S]*?\}/);
  if (!match) throw new Error('AI 返回格式异常: ' + text.slice(0, 150));

  const result = JSON.parse(match[0]);
  if (!['approve', 'reject', 'escalate'].includes(result.action)) {
    throw new Error('AI 返回了非法 action: ' + result.action);
  }
  if (!Array.isArray(result.warnings)) result.warnings = [];

  result.rulesApplied = [];
  result.aiPowered = true;
  result.aiModel = MODEL;
  // 记录 AI 推理过程（传入数据快照）
  result.steps = [
    { type: 'read', label: 'AI推理模式', value: `模型: ${MODEL}` },
    { type: 'read', label: '传入数据摘要', value: JSON.stringify(compact, null, 2) },
    ...(hint ? [{ type: 'read', label: '用户评价指令', value: hint }] : []),
    { type: 'branch', text: `AI决策 → ${result.action}（置信度: ${result.confidence}）` },
  ];
  return result;
}

// 清除文档缓存（文档更新后可手动调用）
function clearDocsCache() { _docsCache = null; }

module.exports = { inferWithAI, clearDocsCache };
