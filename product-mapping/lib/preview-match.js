'use strict';
/**
 * WHAT: 匹配前预览核对表 HTML — 识图填写完成后、执行 match 前的人工确认
 * WHERE: CLI preview-match 命令 → 此模块
 * WHY: match 是写操作，执行前需确认识图结论无误；已匹配项同时复核
 *
 * 输出两部分（卡片格式与 verify-table 一致）：
 *   Part 1 已匹配 — 图片 + 人工识图结论（来自 sku-records recognition）
 *   Part 2 待匹配 — 图片 + 人工识图结论（来自 sku-records recognition）
 * ERP 档案数据只用于区分绑定状态，不得替代人工识图明细。
 *
 * 生命周期：每次生成时清空旧 preview-match-*.html
 */

const path = require('path');
const fs = require('fs');
const { resolveItems } = require('./utils/resolve-items');

const REPORT_DIR = path.join(__dirname, '../data/reports');
const IMGS_DIR = path.join(__dirname, '../data/imgs');
const SKU_RECORDS = path.join(__dirname, '../data/sku-records.json');
const { requireRecordBrand } = require('./brand-scope');

/** 将图片文件编码为 base64 data URI */
function imgDataUri(platformCode) {
  const imgPath = path.join(IMGS_DIR, `${platformCode}.jpg`);
  if (!fs.existsSync(imgPath)) return null;
  return `data:image/jpeg;base64,${fs.readFileSync(imgPath).toString('base64')}`;
}

/** 转义 HTML 特殊字符 */
function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** 识图明细统一渲染：已匹配和待匹配都必须以 recognition 为准 */
function renderRecognitionRows(sku, brand) {
  if (!sku.recognition || !Array.isArray(sku.recognition.items) || sku.recognition.items.length === 0) {
    return `<tr><td class="c-name" style="color:#aaa">识图未填写</td><td class="c-qty"></td></tr>`;
  }
  const resolved = resolveItems(sku.platformCode, sku.recognition.items, brand);
  return resolved.map(it =>
    `<tr><td class="c-name">${esc(it.name)}</td><td class="c-qty">×${it.qty}</td></tr>`
  ).join('');
}

/** 渲染单张卡片（与 verify-table 同款布局） */
function renderCard(sku, detailRows, badgeClass, badgeText) {
  const imgSrc = imgDataUri(sku.platformCode);
  return `
  <div class="card">
    <div class="card-header">
      <div class="header-left">
        <span class="chip">${esc(sku.productCode)}</span>
        <span class="sku-code">${esc(sku.platformCode)}</span>
      </div>
      <div class="header-title">${esc(sku.skuName)}</div>
      <span class="badge ${badgeClass}">${badgeText}</span>
    </div>
    <div class="card-body">
      <div class="img-col">
        ${imgSrc
          ? `<img src="${imgSrc}" alt="${esc(sku.platformCode)}" />`
          : '<div class="no-img">无图片</div>'}
      </div>
      <div class="info-col">
        <div class="detail-label">人工识图结果</div>
        <table class="detail-table">${detailRows}</table>
      </div>
    </div>
  </div>`;
}

/** 主入口 */
function main() {
  if (!fs.existsSync(SKU_RECORDS)) {
    throw new Error('sku-records.json 不存在，请先运行 node cli.js check --shop <店铺> --brand <品牌>');
  }

  const skuRecords = JSON.parse(fs.readFileSync(SKU_RECORDS, 'utf8'));
  const shopName = Object.values(skuRecords)[0]?.shopName || '未知店铺';
  const brand = requireRecordBrand(skuRecords, shopName);
  const missingRecognition = Object.values(skuRecords)
    .filter(sku => !sku.recognition || !Array.isArray(sku.recognition.items) || sku.recognition.items.length === 0)
    .map(sku => sku.platformCode);
  if (missingRecognition.length) {
    throw new Error(`识图未完成：${missingRecognition.length} 个 SKU 缺少 recognition`);
  }

  // 分成已匹配 / 待匹配两组
  const matched = [];
  const unmatched = [];
  for (const rec of Object.values(skuRecords)) {
    (rec.erpCode ? matched : unmatched).push(rec);
  }

  // ── Part 1：已匹配项，主明细仍然只展示人工识图结果 ──
  const matchedCards = matched.map(sku =>
    renderCard(sku, renderRecognitionRows(sku, brand), 'cmp-ok', '✓ 已匹配')
  ).join('\n');

  // ── Part 2：待匹配项，同样展示人工识图结果 ──
  const unmatchedCards = unmatched.map(sku =>
    renderCard(sku, renderRecognitionRows(sku, brand), 'cmp-pending', '⏳ 待匹配')
  ).join('\n');

  // ── 拼 HTML（样式与 verify-table 保持一致） ──
  const dateLabel = new Date().toISOString().slice(0, 10);
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>匹配前核对 — ${esc(shopName)} ${dateLabel}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif; background: #f0f0f0; color: #333; padding: 28px; }
h1 { font-size: 20px; margin-bottom: 4px; }
.sub { color: #888; font-size: 13px; margin-bottom: 24px; }
.summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.summary .stat { background: #fff; border-radius: 6px; padding: 10px 16px; font-size: 13px; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.stat b { font-size: 18px; margin-right: 4px; }
.stat.good b { color: #22c55e; }
.stat.warn b { color: #f97316; }

.section-title { font-size: 16px; font-weight: 700; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #d9d9d9; }
.section-title.s-matched { border-color: #22c55e; color: #15803d; }
.section-title.s-unmatched { border-color: #f97316; color: #c2410c; }

.card { background: #fff; border-radius: 6px; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(0,0,0,.10); overflow: hidden; }
.card-header { display: flex; align-items: center; gap: 12px; padding: 12px 20px; background: #fafafa; border-bottom: 1px solid #d9d9d9; }
.header-left { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.chip { background: #e0e7ff; color: #4338ca; padding: 2px 10px; border-radius: 4px; font-weight: 600; font-size: 13px; }
.sku-code { color: #888; font-family: "SF Mono", "Menlo", "Monaco", monospace; font-size: 12px; }
.header-title { flex: 1; font-size: 14px; font-weight: 400; color: #555; min-width: 0; word-break: break-all; border: 1px solid #d9d9d9; border-radius: 4px; padding: 3px 10px; background: #fff; }
.badge { padding: 2px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; flex-shrink: 0; }
.cmp-ok { background: #dcfce7; color: #16a34a; }
.cmp-pending { background: #fff7ed; color: #c2410c; }

.card-body { display: flex; gap: 0; }
.img-col { width: 520px; min-height: 300px; display: flex; align-items: center; justify-content: center; background: #fafafa; border-right: 1px solid #d9d9d9; padding: 16px; }
.img-col img { max-width: 500px; max-height: 500px; object-fit: contain; border-radius: 4px; }
.no-img { color: #bbb; font-size: 16px; }
.info-col { flex: 1; padding: 24px 28px; min-width: 0; }
.detail-label { color: #64748b; font-size: 13px; font-weight: 600; margin-bottom: 8px; }

.detail-table { width: 100%; border-collapse: collapse; }
.detail-table td { padding: 8px 0; border-bottom: 1px solid #ccc; }
.detail-table .c-name { font-size: 18px; font-weight: 700; word-break: break-all; }
.detail-table .c-qty { width: 64px; text-align: right; font-weight: 700; font-size: 22px; white-space: nowrap; padding-left: 16px; }

@media (max-width: 900px) {
  .card-body { flex-direction: column; }
  .img-col { width: 100%; border-right: none; border-bottom: 1px solid #d9d9d9; }
  .card-header { flex-wrap: wrap; }
}
</style>
</head>
<body>

<h1>匹配前核对</h1>
<div class="sub">${esc(shopName)} · ${esc(brand)} · ${dateLabel} · 共 ${Object.keys(skuRecords).length} 个 SKU</div>

<div class="summary">
  <div class="stat good"><b>${matched.length}</b> 已匹配</div>
  <div class="stat warn"><b>${unmatched.length}</b> 待匹配</div>
</div>

<div class="section-title s-matched">已匹配（${matched.length}）</div>
${matchedCards}

<div class="section-title s-unmatched">待匹配（${unmatched.length}）</div>
${unmatchedCards}

</body>
</html>`;

  // 清空旧核对表
  if (fs.existsSync(REPORT_DIR)) {
    fs.readdirSync(REPORT_DIR).forEach(f => {
      if (f.startsWith('preview-match-') && f.endsWith('.html')) {
        fs.unlinkSync(path.join(REPORT_DIR, f));
      }
    });
  }

  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const outName = `preview-match-${shopName}-${dateStr}.html`;
  const outPath = path.join(REPORT_DIR, outName);

  if (!fs.existsSync(REPORT_DIR)) fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.writeFileSync(outPath, html);

  return { path: outPath, name: outName, brand, matched: matched.length, unmatched: unmatched.length };
}

module.exports = { main };
