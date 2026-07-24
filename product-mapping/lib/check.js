'use strict';
/**
 * WHAT: 完整核查流程编排（扫描+标记+下载图片+生成报告）
 * WHERE: CLI check 命令 → 此模块
 * WHY: 4 步核查流程的自动化编排入口，输出结构化 comparison 事实供 AI 按阶段判断
 * ENTRY: cli.js: check 命令
 */
const path = require('path');
const fs = require('fs');
const { listActiveProducts } = require('./jl-products');
const { readAllCorrespondence, readCorrWithoutDownload } = require('./correspondence');
const { initArchiveComp, queryArchive, querySubItems } = require('./archive');
const { imgPath, downloadImg, mergeVerdicts } = require('./visual');
const { sleep } = require('./wait');
const { releaseErpLock } = require('./erp-lock');
const { compareSkuArchive } = require('./compare');
const { requireKnownBrand, requireRecordBrand, assertSameBrand } = require('./brand-scope');

const REPORT_DIR = path.join(__dirname, '../data/reports');
const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');

function loadSkuRecords() {
  try {
    const raw = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
    return raw.skus || raw;
  } catch (_) {
    return {};
  }
}

function summarizeSkuComparisons(allSkus) {
  const compMatch = allSkus.filter(s => s.comparisonResult === 'match').length;
  const compMismatch = allSkus.filter(s => s.comparisonResult === 'mismatch').length;
  const recognitionDone = allSkus.filter(s => s.recognition).length;
  const pendingVisualReview = allSkus.filter(s => !s.recognition).length;
  const matchedSkus = allSkus.filter(s => s.erpCode);
  const unmatchedSkus = allSkus.filter(s => !s.erpCode);

  return {
    pendingVisualReview,
    recognitionDone,
    comparisonMatch: compMatch,
    comparisonMismatch: compMismatch,
    comparisonPending: recognitionDone - compMatch - compMismatch,
    matchedSkuCount: matchedSkus.length,
    matchedComparisonMatch: matchedSkus.filter(s => s.comparisonResult === 'match').length,
    matchedComparisonMismatch: matchedSkus.filter(s => s.comparisonResult === 'mismatch').length,
    unmatchedAwaitingMatch: unmatchedSkus.length,
  };
}

function loadReusableActiveProducts(shopName, skuRecords) {
  const files = fs.existsSync(REPORT_DIR)
    ? fs.readdirSync(REPORT_DIR)
      .filter(f => f.startsWith(`check-${shopName}-`) && f.endsWith('.json'))
      .sort()
    : [];
  if (!files.length) throw new Error(`后置 check 缺少 ${shopName} 的历史 check 报告`);

  const previous = JSON.parse(fs.readFileSync(path.join(REPORT_DIR, files[files.length - 1]), 'utf8'));
  const products = Array.isArray(previous.products) ? previous.products : [];
  const recordCodes = new Set(Object.values(skuRecords)
    .filter(r => r && r.shopName === shopName && String(r.scope || '').startsWith('active-'))
    .map(r => r.platformCode)
    .filter(Boolean));
  const reportCodes = new Set(products
    .flatMap(p => Array.isArray(p.skus) ? p.skus : [])
    .map(s => s.platformCode)
    .filter(Boolean));

  const missingInReport = [...recordCodes].filter(code => !reportCodes.has(code));
  const missingInRecords = [...reportCodes].filter(code => !recordCodes.has(code));
  if (!recordCodes.size || missingInReport.length || missingInRecords.length) {
    throw new Error(
      `后置 check 活动范围不一致：records=${recordCodes.size} report=${reportCodes.size}`
      + ` missingInReport=${missingInReport.join(',') || '-'}`
      + ` missingInRecords=${missingInRecords.join(',') || '-'}`
    );
  }

  return {
    previous,
    products: products.map(p => ({
      code: p.productCode,
      name: p.productName,
      productId: p.productId,
    })),
  };
}

/**
 * 主核查流程
 * @param {string} jlId - 鲸灵标签页 targetId
 * @param {string} erpId - ERP 标签页 targetId
 * @param {string} shopName - 店铺名，如「澜泽」
 * @returns {Promise<object>} 核查报告
 */
async function runCheck(jlId, erpId, shopName, options = {}) {
  try {
    const reuseActiveScope = options.reuseActiveScope === true;
    const skipDownload = options.skipDownload === true;

    // 读取识图记录（sku-records.json），用于活动范围复用和报告对比
    const skuRecords = loadSkuRecords();
    let reusable = null;
    let brand;
    if (reuseActiveScope) {
      const recordBrand = requireRecordBrand(skuRecords, shopName);
      brand = options.brand
        ? assertSameBrand(options.brand, recordBrand, 'sku-records')
        : recordBrand;
      reusable = loadReusableActiveProducts(shopName, skuRecords);
      if (!reusable.previous.brand) {
        throw new Error('历史 check 报告缺少品牌，请重新运行首次 check --shop <店铺> --brand <品牌>');
      }
      assertSameBrand(brand, reusable.previous.brand, '历史 check 报告');
    } else {
      brand = requireKnownBrand(options.brand, '首次 check ');
    }

    const report = {
      shop: shopName,
      brand,
      checkTime: new Date().toISOString(),
      summary: {},
      products: []
    };

    // 1. 获取活动商品列表；后置 check 可复用已经人工确认的活动范围
    console.error(`[check] 1/4 ${reuseActiveScope ? '复用已确认活动范围' : '获取鲸灵活动商品列表'}...`);
    const jlProducts = reuseActiveScope
      ? reusable.products
      : await listActiveProducts(jlId);
    console.error(`[check] 品牌=${brand}，共 ${jlProducts.length} 个活动商品`);

    // 2. 读取对应表全量数据；后置 check 不重复下载平台商品
    console.error(`[check] 2/4 读取商品对应表${skipDownload ? '（跳过平台商品下载）' : ''}...`);
    const corrAll = skipDownload
      ? await readCorrWithoutDownload(erpId, shopName)
      : await readAllCorrespondence(erpId, shopName);
    const corrMap = {};
    corrAll.forEach(r => { corrMap[r.productCode] = r.skus; });
    const corrImgMap = {};
    corrAll.forEach(r => r.skus.forEach(s => { if (s.imgUrl) corrImgMap[s.platformCode] = s.imgUrl; }));
    console.error(`[check] 对应表共 ${corrAll.length} 条产品记录`);

    // 3. 初始化档案V2
    console.error('[check] 3/4 初始化商品档案V2...');
    await initArchiveComp(erpId);

    // 4. 正常新活动清空运行态；后置 check 保留已确认图片和旧报告，成功后再覆盖报告
    const imgsDir = path.join(__dirname, '../data/imgs');
    fs.mkdirSync(imgsDir, { recursive: true });
    if (!reuseActiveScope && fs.existsSync(imgsDir)) {
      fs.readdirSync(imgsDir).forEach(f => fs.unlinkSync(path.join(imgsDir, f)));
    }
    if (!reuseActiveScope && fs.existsSync(REPORT_DIR)) {
      fs.readdirSync(REPORT_DIR).forEach(f => {
        if (f.endsWith('.json')) fs.unlinkSync(path.join(REPORT_DIR, f));
      });
    }
    console.error(reuseActiveScope
      ? '[check] 保留已确认 imgs/ 和旧报告（后置核查）'
      : '[check] 清空 imgs/ 和 reports/（全新开始）');

    // 5. 逐产品核查
    console.error('[check] 4/4 逐产品核查...');
    let matchedCount = 0, unmatchedCount = 0, partialCount = 0, notInCorrCount = 0;
    const activePlatformCodes = new Set();

    for (const p of jlProducts) {
      const skus = corrMap[p.code];

      if (!skus) {
        notInCorrCount++;
        report.products.push({
          productCode: p.code,
          productName: p.name,
          productId: p.productId,
          status: '不在对应表',
          skus: []
        });
        continue;
      }

      const skuResults = [];
      let hasUnmatched = false;
      let hasMatched = false;

      for (const sku of skus) {
        if (sku.platformCode) activePlatformCodes.add(sku.platformCode);
        // 所有 SKU 都下载图片（文件名 = platformCode，不存在才下载）
        if (sku.imgUrl) {
          const dest = imgPath(sku.platformCode);
          if (!fs.existsSync(dest)) {
            try { downloadImg(sku.imgUrl, dest); } catch (e) {
              console.error(`[check] ⚠️ 图片下载失败: ${sku.platformCode} ${e.message}`);
            }
          }
        }

        if (!sku.erpCode) {
          hasUnmatched = true;
          const rec0 = skuRecords[sku.platformCode];
          const recognition = rec0?.brand === brand ? rec0.recognition || null : null;
          skuResults.push({
            skuName: sku.skuName,
            platformCode: sku.platformCode,
            erpCode: '',
            erpName: '',
            archiveType: null,
            archiveTitle: null,
            recognition,
            status: '未匹配'
          });
          continue;
        }

        hasMatched = true;
        const archiveItem = await queryArchive(erpId, sku.erpCode);

        let status, archiveType = null, archiveTitle = null, subItemNum = 0, archiveLookupMode = null;
        if (!archiveItem) {
          status = '已匹配-档案未录入';
        } else {
          archiveType = archiveItem.type; // '0'=单品, '2'=组合装
          archiveTitle = archiveItem.title;
          subItemNum = archiveItem.subItemNum || 0;
          archiveLookupMode = archiveItem.lookupMode || null;

          // 组合装额外获取子品明细（视觉核查比对基准）
          if (archiveType === '2' && subItemNum > 0) {
            try {
              archiveItem.subItems = await querySubItems(erpId, subItemNum);
            } catch (e) {
              console.error(`[check] ⚠️ 子品明细获取失败: ${sku.erpCode} ${e.message}`);
              archiveItem.subItems = [];
            }
          }

          status = '已匹配-待视觉核查';
        }

        const rec = skuRecords[sku.platformCode];
        const recognition = rec?.brand === brand ? rec.recognition || null : null;
        const subItems = (archiveItem && archiveItem.subItems) || [];

        // 识图 vs 档案对比由纯函数统一处理：
        // - recognition 为空但 ERP 有明细 => mismatch
        // - 有 recognition 但 ERP 无可比明细 => mismatch
        // - 组合装对比时临时注入配件（不写回 recognition）
        const { comparisonResult, comparisonDetail } = compareSkuArchive({
          platformCode: sku.platformCode,
          recognition,
          archiveType,
          archiveTitle,
          subItems,
          brand,
        });

        skuResults.push({
          skuName: sku.skuName,
          platformCode: sku.platformCode,
          erpCode: sku.erpCode,
          erpName: sku.erpName,
          archiveType,
          archiveTitle,
          archiveLookupMode,
          subItemNum,
          subItems,
          recognition,
          comparisonResult,
          comparisonDetail,
          status
        });
      }

      if (!hasUnmatched && hasMatched) matchedCount++;
      else if (hasUnmatched && !hasMatched) unmatchedCount++;
      else partialCount++;

      const productStatus = !hasUnmatched && hasMatched ? '已完全匹配'
        : !hasMatched ? '全部未匹配'
        : '部分未匹配';

      report.products.push({
        productCode: p.code,
        productName: p.name,
        productId: p.productId,
        status: productStatus,
        skus: skuResults
      });

      process.stderr.write('.');
    }
    console.error('');

    // 合并识图结论（visual-verdicts.json → 更新各 SKU status）
    mergeVerdicts(report);

    // 统计识图 vs 档案对比结果
    const allSkus = report.products.flatMap(p => p.skus);
    const comparisonSummary = summarizeSkuComparisons(allSkus);

    report.summary = {
      total: jlProducts.length,
      notInCorr: notInCorrCount,
      fullyMatched: matchedCount,
      partiallyMatched: partialCount,
      fullyUnmatched: unmatchedCount,
      ...comparisonSummary,
    };

    // 保存报告
    if (!fs.existsSync(REPORT_DIR)) fs.mkdirSync(REPORT_DIR, { recursive: true });
    const dateStr = new Date().toISOString().slice(0, 10);
    const reportPath = path.join(REPORT_DIR, `check-${shopName}-${dateStr}.json`);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.error(`[check] 报告已保存: ${reportPath}`);
    if (comparisonSummary.comparisonMismatch > 0) {
      console.error(`[check] ⚠️ ${comparisonSummary.comparisonMismatch} 个 SKU 识图与档案不一致，需先定位并报告差异`);
    }
    if (comparisonSummary.pendingVisualReview > 0) {
      console.error(`[check] ⚠️ ${comparisonSummary.pendingVisualReview} 个 SKU 待完成识图`);
    }

    if (activePlatformCodes.size > 0) {
      try {
        const activeScope = `active-${dateStr}`;
        // 全量重写 sku-records.json：以本次 check 的活跃 SKU 为唯一数据源
        // 不读旧文件做 patch，避免历史残留导致 getTodo() 误判
        const newRecords = {};
        for (const prod of report.products) {
          for (const sku of prod.skus) {
            if (!sku.platformCode) continue;
            newRecords[sku.platformCode] = {
              platformCode: sku.platformCode,
              skuName: sku.skuName || null,
              productCode: prod.productCode,
              shopName,
              brand,
              imgUrl: corrImgMap[sku.platformCode] || null,
              erpCode: sku.erpCode || null,
              erpName: sku.erpName || null,
              recognition: sku.recognition || null,
              scope: activeScope,
            };
          }
        }
        fs.writeFileSync(SKU_RECORDS_PATH, JSON.stringify(newRecords, null, 2));
        console.error(`[check] sku-records 全量重写：${Object.keys(newRecords).length} 条，scope=${activeScope}`);
      } catch (e) {
        console.error(`[check] ⚠️ sku-records 更新失败: ${e.message}`);
      }
    }

    return report;
  } finally {
    await releaseErpLock();
  }
}

module.exports = { runCheck, summarizeSkuComparisons };
