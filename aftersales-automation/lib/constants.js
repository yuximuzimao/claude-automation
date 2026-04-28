'use strict';

// 退回物流关键词（三处共用：infer.js / pipeline.js / op-queue.js）
const RETURN_KEYWORDS = ['退回商家', '安排退回', '拒收', '退件', '退回'];

// 买家签收关键词（非退回）
const SIGNED_KEYWORDS = ['已签收', '签收成功', '本人签收', '代签', '前台签收', '快递柜'];

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

module.exports = { RETURN_KEYWORDS, SIGNED_KEYWORDS, NON_MERCHANT_REASONS, MERCHANT_FAULT_REASONS, SCAN_HOURS, getHoursUntilNextScan };
