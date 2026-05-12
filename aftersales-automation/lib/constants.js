'use strict';

// 退回物流关键词（三处共用：infer.js / pipeline.js / op-queue.js）
const RETURN_KEYWORDS = ['退回商家', '安排退回', '拒收', '退件', '退回'];

// 买家签收关键词（非退回）
// 注意：物流动态首行格式为"签收 YYYY-MM-DD HH:MM:SS"，需覆盖无前缀的"签收"
// 快递柜/菜鸟驿站属于"待取件"（可拦截），不算签收，放在 YIZHAN_KEYWORDS
// "家门口"/"门口"等投递到门的场景等同签收，不可拦截
const SIGNED_KEYWORDS = ['已签收', '签收成功', '本人签收', '代签收', '前台签收', '签收', '放置门口', '投递门口', '放门口'];

// 平台标准非商责原因（无理由/个人原因类）
// 来源：鲸灵工单列表筛选项「售后原因」完整枚举（2026-04）
const NON_MERCHANT_REASONS = [
  '多拍/拍错/不想要',
  '七天无理由退货',
  '无理由退款',
  '无理由售后',
  '个人原因',
  '不喜欢',
  '不合适',
];

// 商责售后原因（涉及罚款风险，一律上报人工）
// 来源：fb-1776318426905 / fb-1776319121452 / fb-1776410431569 / fb-1777355227738 反馈
const MERCHANT_FAULT_REASONS = [
  '商品破损',
  '变形',
  '物流停滞',
  '签收异常',
  '商品漏发',
  '少件',
  '缺件',
  '发错商品',
  '商品与描述不符',
];

// 自动扫描时间点（server.js 和 pipeline.js 共用）
const SCAN_HOURS = [0, 8, 12, 16, 20];

// 到期提醒阈值（小时）：工单剩余时效 ≤ 此值时自动创建 Mac 提醒事项
const REMIND_HOURS = 12;

// waiting 重查最小间隔（小时）：距上次推理完成 ≥ 此值才允许重置为 pending
const RESCAN_INTERVAL_HOURS = 4;

// 安全边际（小时）：剩余时效 - 下次扫描间隔 > 此值才安全等待，否则拒绝
const SAFETY_MARGIN_HOURS = 8;

// 批量执行：允许入队的 queue item 状态白名单
const BATCH_EXECUTABLE_STATUSES = ['simulated'];

// 批量执行：允许自动批量执行的 reject reasonCode 白名单
const BATCH_SAFE_REJECT_CODES = [
  'SIGNED_NO_INTERCEPT',  // 已签收，无法拦截，请改退货退款
  'AT_STATION',           // 已到驿站待取件，可联系驿站拦截
  'INTERCEPT_TIMEOUT',    // 在途拦截件时效不足，立即处理
  'OVERDUE_RETURN',       // 超售后期无理由退货
];

// 判断某条 simulation decision 是否允许批量执行
function isBatchExecutable(decision, queueItemStatus) {
  if (!queueItemStatus || !BATCH_EXECUTABLE_STATUSES.includes(queueItemStatus)) return false;
  if (!decision) return false;
  if (decision.action === 'approve') return true;
  if (decision.action === 'reject') return BATCH_SAFE_REJECT_CODES.includes(decision.reasonCode);
  return false;
}

// 计算距下次自动扫描的小时数
function getHoursUntilNextScan() {
  const now = new Date();
  const h = now.getHours();
  let nextHour = SCAN_HOURS.find(hour => hour > h);
  let daysAhead = 0;
  if (nextHour === undefined) { nextHour = SCAN_HOURS[0]; daysAhead = 1; }
  const next = new Date(now);
  next.setDate(next.getDate() + daysAhead);
  next.setHours(nextHour, 0, 0, 0);
  return (next.getTime() - now.getTime()) / 3600000;
}

module.exports = { RETURN_KEYWORDS, SIGNED_KEYWORDS, NON_MERCHANT_REASONS, MERCHANT_FAULT_REASONS, SCAN_HOURS, REMIND_HOURS, RESCAN_INTERVAL_HOURS, SAFETY_MARGIN_HOURS, getHoursUntilNextScan, BATCH_EXECUTABLE_STATUSES, BATCH_SAFE_REJECT_CODES, isBatchExecutable };
