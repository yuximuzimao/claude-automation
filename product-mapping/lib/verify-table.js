'use strict';
/**
 * WHAT: 生成识图核对表 HTML — 图片+ERP明细一一对应，供人工兜底核对
 * WHERE: CLI verify-table 命令 → 此模块
 * WHY: 识图可能出错（如体验装误判为正装），流程末尾需人工逐项核对
 * ENTRY: cli.js: verify-table 命令
 *
 * 生命周期：每次生成新核对表时，自动清空旧 verify-*.html（与 check 清空 imgs/reports 一致，
 * 旧核对表对下次无用，只保留最新一份）。
 */
const path = require('path');
const fs = require('fs');
const { resolveItems } = require('./utils/resolve-items');
const { requireKnownBrand } = require('./brand-scope');
const { imageFileName, recordKey } = require('./sku-identity');

const REPORT_DIR = path.join(__dirname, '../data/reports');
const IMGS_DIR = path.join(__dirname, '../data/imgs');
const OUT_DIR = path.join(__dirname, '../data/reports');

/**
 * 读取最新的 check 报告
 */
function latestReport() {
  const files = fs.readdirSync(REPORT_DIR)
    .filter(f => f.startsWith('check-') && f.endsWith('.json'))
    .sort();
  if (!files.length) return null;
  const file = files[files.length - 1];
  return { path: path.join(REPORT_DIR, file), name: file, data: JSON.parse(fs.readFileSync(path.join(REPORT_DIR, file), 'utf8')) };
}

/**
 * 将图片文件编码为 base64 data URI
 */
function imgDataUri(productCode, platformCode) {
  const imgPath = path.join(IMGS_DIR, imageFileName(productCode, platformCode));
  if (!fs.existsSync(imgPath)) return null;
  const buf = fs.readFileSync(imgPath);
  const b64 = buf.toString('base64');
  return `data:image/jpeg;base64,${b64}`;
}

/**
 * 转义 HTML 特殊字符
 */
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

/**
 * 生成 HTML 核对表
 */
function generate(report) {
  const brand = requireKnownBrand(report.brand, 'check 报告');
  const allSkus = [];
  for (const prod of report.products) {
    for (const sku of prod.skus) {
      allSkus.push({ ...sku, _productCode: prod.productCode, _productName: prod.productName });
    }
  }

  // 预加载所有图片（避免 map 内逐个 I/O）
  const imgCache = {};
  for (const sku of allSkus) {
    const key = recordKey(sku._productCode, sku.platformCode);
    imgCache[key] = imgDataUri(sku._productCode, sku.platformCode);
  }

  const rows = allSkus.map(sku => {
    const imgSrc = imgCache[recordKey(sku._productCode, sku.platformCode)];
    const hasImg = !!imgSrc;
    const isMatch = sku.comparisonResult === 'match';
    const isMismatch = sku.comparisonResult === 'mismatch';

    // ERP 明细行
    let erpRows = '';
    if (sku.archiveType === '2' && sku.subItems && sku.subItems.length > 0) {
      erpRows = sku.subItems.map(si =>
        `<tr><td class="c-name">${esc(si.name)}</td><td class="c-qty">×${si.qty}</td></tr>`
      ).join('');
    } else if (sku.archiveType === '0' && sku.archiveTitle) {
      erpRows = `<tr><td class="c-name">${esc(sku.archiveTitle)}</td><td class="c-qty">×1</td></tr>`;
    } else {
      erpRows = `<tr><td class="c-name" style="color:#aaa">无档案数据</td><td class="c-qty"></td></tr>`;
    }

    // 识图明细行（含配件注入）
    let recRows = '';
    if (sku.recognition && sku.recognition.items && sku.recognition.items.length > 0) {
      const resolvedItems = resolveItems(sku.platformCode, sku.recognition.items, brand);
      recRows = resolvedItems.map(it =>
        `<tr><td class="c-name">${esc(it.name)}</td><td class="c-qty">×${it.qty}</td></tr>`
      ).join('');
    } else {
      recRows = `<tr><td class="c-name" style="color:#aaa">无识图数据</td><td class="c-qty"></td></tr>`;
    }

    // 状态标签
    let cmpClass = 'cmp-na';
    let cmpText = '未对比';
    if (isMatch) { cmpClass = 'cmp-ok'; cmpText = '✓ 一致'; }
    else if (isMismatch) { cmpClass = 'cmp-bad'; cmpText = '✗ 不一致'; }

    return `
    <div class="card ${isMismatch ? 'card-mismatch' : ''}">
      <div class="card-header">
        <div class="header-left">
          <span class="chip">${esc(sku._productCode)}</span>
          <span class="sku-code">${esc(sku.platformCode)}</span>
        </div>
        <div class="header-title">${esc(sku.skuName || '')}</div>
        <span class="badge ${cmpClass}">${cmpText}</span>
      </div>
      <div class="card-body">
        <div class="img-col">
          ${hasImg
            ? `<img src="${imgSrc}" alt="${esc(sku.platformCode)}" />`
            : `<div class="no-img">无图片</div>`}
        </div>
        <div class="info-col">
          <div class="view-erp"><table class="detail-table">${erpRows}</table></div>
          <div class="view-rec"><table class="detail-table">${recRows}</table></div>
        </div>
      </div>
    </div>`;
  }).join('\n');

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>识图核对表 — ${esc(report.shop)} ${report.checkTime.slice(0,10)}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif; background: #f0f0f0; color: #333; padding: 28px; }
h1 { font-size: 20px; margin-bottom: 4px; }
.sub { color: #888; font-size: 13px; margin-bottom: 24px; }
.summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px; }
.summary .stat { background: #fff; border-radius: 6px; padding: 10px 16px; font-size: 13px; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.stat b { font-size: 18px; margin-right: 4px; }
.stat.good b { color: #22c55e; }
.stat.warn b { color: #f97316; }
.stat.bad b { color: #ef4444; }

.card { background: #fff; border-radius: 6px; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(0,0,0,.10); overflow: hidden; }
.card-mismatch { border-left: 4px solid #ef4444; }
.card-header { display: flex; align-items: center; gap: 12px; padding: 12px 20px; background: #fafafa; border-bottom: 1px solid #d9d9d9; }
.header-left { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.chip { background: #e0e7ff; color: #4338ca; padding: 2px 10px; border-radius: 4px; font-weight: 600; font-size: 13px; }
.sku-code { color: #888; font-family: "SF Mono", "Menlo", "Monaco", monospace; font-size: 12px; }
.header-title { flex: 1; font-size: 14px; font-weight: 400; color: #555; min-width: 0; word-break: break-all; border: 1px solid #d9d9d9; border-radius: 4px; padding: 3px 10px; background: #fff; }
.badge { padding: 2px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; flex-shrink: 0; }
.cmp-ok { background: #dcfce7; color: #16a34a; }
.cmp-bad { background: #fef2f2; color: #ef4444; }
.cmp-na { background: #f3f4f6; color: #9ca3af; }

.card-body { display: flex; gap: 0; }
.img-col { width: 520px; min-height: 300px; display: flex; align-items: center; justify-content: center; background: #fafafa; border-right: 1px solid #d9d9d9; padding: 16px; }
.img-col img { max-width: 500px; max-height: 500px; object-fit: contain; border-radius: 4px; }
.no-img { color: #bbb; font-size: 16px; }
.info-col { flex: 1; padding: 24px 28px; min-width: 0; }

.detail-table { width: 100%; border-collapse: collapse; }
.detail-table td { padding: 8px 0; border-bottom: 1px solid #ccc; }
.detail-table .c-name { font-size: 18px; font-weight: 700; word-break: break-all; }
.detail-table .c-qty { width: 64px; text-align: right; font-weight: 700; font-size: 22px; white-space: nowrap; padding-left: 16px; }

.toggle-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 24px; }
.toggle-bar span { font-size: 13px; color: #888; margin-right: 4px; }
.toggle-btn { padding: 6px 20px; border: 1.5px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; color: #555; transition: all .15s; }
.toggle-btn.active { background: #4338ca; border-color: #4338ca; color: #fff; font-weight: 600; }
body.mode-erp .view-rec { display: none; }
body.mode-rec .view-erp { display: none; }

@media (max-width: 900px) {
  .card-body { flex-direction: column; }
  .img-col { width: 100%; border-right: none; border-bottom: 1px solid #d9d9d9; }
  .card-header { flex-wrap: wrap; }
}
</style>
</head>
<body>

<h1>识图核对表</h1>
<div class="sub">${esc(report.shop)} · ${report.checkTime.slice(0,10)} · 共 ${allSkus.length} 个 SKU</div>

<div class="summary">
  <div class="stat good"><b>${report.summary.comparisonMatch || 0}</b> 一致</div>
  <div class="stat bad"><b>${report.summary.comparisonMismatch || 0}</b> 不一致</div>
  <div class="stat"><b>${report.summary.recognitionDone || 0}</b> 已识图</div>
</div>

<div class="toggle-bar">
  <span>查看：</span>
  <button class="toggle-btn active" id="btn-erp" onclick="setMode('erp')">ERP 档案</button>
  <button class="toggle-btn" id="btn-rec" onclick="setMode('rec')">识图结果</button>
</div>

${rows}

<script>
function setMode(mode) {
  document.body.className = 'mode-' + mode;
  document.getElementById('btn-erp').className = 'toggle-btn' + (mode === 'erp' ? ' active' : '');
  document.getElementById('btn-rec').className = 'toggle-btn' + (mode === 'rec' ? ' active' : '');
}
document.body.className = 'mode-erp';
</script>
</body>
</html>`;
}

/**
 * 主入口：读取最新报告 → 清空旧核对表 → 生成 HTML → 保存 → 返回路径
 */
function main() {
  const report = latestReport();
  if (!report) throw new Error('未找到 check 报告，请先运行 node cli.js check --shop <店铺> --brand <品牌>');

  // 清空旧核对表（与 check 清空 imgs/reports 一致，旧表对下次无用）
  if (fs.existsSync(OUT_DIR)) {
    fs.readdirSync(OUT_DIR).forEach(f => {
      if (f.startsWith('verify-') && f.endsWith('.html')) {
        fs.unlinkSync(path.join(OUT_DIR, f));
      }
    });
  }

  const html = generate(report.data);

  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const outName = `verify-${report.data.shop}-${dateStr}.html`;
  const outPath = path.join(OUT_DIR, outName);

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(outPath, html);

  return { path: outPath, name: outName, skuCount: report.data.products.flatMap(p => p.skus).length };
}

module.exports = { main, generate };
