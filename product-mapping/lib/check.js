'use strict';
/**
 * WHAT: 完整核查流程编排（扫描+标记+下载图片+生成报告）
 * WHERE: CLI check 命令 → 此模块
 * WHY: 4 步核查流程的自动化编排入口，输出 comparison 报告用于人工核查
 * ENTRY: cli.js: check 命令
 */
const path = require('path');
const fs = require('fs');
const { listActiveProducts } = require('./jl-products');
const { readAllCorrespondence } = require('./correspondence');
const { initArchiveComp, queryArchive, querySubItems } = require('./archive');
const { imgPath, downloadImg, mergeVerdicts } = require('./visual');
const { sleep } = require('./wait');
const { releaseErpLock } = require('./erp-lock');

const REPORT_DIR = path.join(__dirname, '../data/reports');
const SKU_RECORDS_PATH = path.join(__dirname, '../data/sku-records.json');

/**
 * 主核查流程
 * @param {string} jlId - 鲸灵标签页 targetId
 * @param {string} erpId - ERP 标签页 targetId
 * @param {string} shopName - 店铺名，如「澜泽」
 * @returns {Promise<object>} 核查报告
 */
async function runCheck(jlId, erpId, shopName) {
  try {
    const report = {
      shop: shopName,
      checkTime: new Date().toISOString(),
      summary: {},
      products: []
    };

    // 1. 获取鲸灵活动商品列表
    console.error('[check] 1/4 获取鲸灵活动商品列表...');
    const jlProducts = await listActiveProducts(jlId);
    console.error(`[check] 共 ${jlProducts.length} 个活动商品`);

    // 2. 读取对应表全量数据
    console.error('[check] 2/4 读取商品对应表...');
    const corrAll = await readAllCorrespondence(erpId, shopName);
    const corrMap = {};
    corrAll.forEach(r => { corrMap[r.productCode] = r.skus; });
    console.error(`[check] 对应表共 ${corrAll.length} 条产品记录`);

    // 3. 初始化档案V2
    console.error('[check] 3/4 初始化商品档案V2...');
    await initArchiveComp(erpId);

    // 4. 清空并重建图片目录、清空旧报告（对下次匹配无用，保留只会积累干扰）
    const imgsDir = path.join(__dirname, '../data/imgs');
    if (fs.existsSync(imgsDir)) {
      fs.readdirSync(imgsDir).forEach(f => fs.unlinkSync(path.join(imgsDir, f)));
    }
    fs.mkdirSync(imgsDir, { recursive: true });
    if (fs.existsSync(REPORT_DIR)) {
      fs.readdirSync(REPORT_DIR).forEach(f => {
        if (f.endsWith('.json')) fs.unlinkSync(path.join(REPORT_DIR, f));
      });
    }
    console.error('[check] 清空 imgs/ 和 reports/（全新开始）');

    // 读取识图记录（sku-records.json），用于报告对比
    // 兼容两种格式：match-one 格式 {stage,skus:{platformCode→rec}} 和旧平铺格式 {platformCode→rec}
    let skuRecords = {};
    try {
      const raw = JSON.parse(fs.readFileSync(SKU_RECORDS_PATH, 'utf8'));
      skuRecords = raw.skus || raw;
    } catch (_) {}

    // 5. 逐产品核查
    console.error('[check] 4/4 逐产品核查...');
    let matchedCount = 0, unmatchedCount = 0, partialCount = 0, notInCorrCount = 0;
    let pendingVisualCount = 0;
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
          skuResults.push({
            skuName: sku.skuName,
            platformCode: sku.platformCode,
            erpCode: '',
            erpName: '',
            archiveType: null,
            archiveTitle: null,
            recognition: rec0?.recognition || null,
            status: '未匹配'
          });
          continue;
        }

        hasMatched = true;
        const archiveItem = await queryArchive(erpId, sku.erpCode);

        let status, archiveType = null, archiveTitle = null, subItemNum = 0;
        if (!archiveItem) {
          status = '已匹配-档案未录入';
        } else {
          archiveType = archiveItem.type; // '0'=单品, '2'=组合装
          archiveTitle = archiveItem.title;
          subItemNum = archiveItem.subItemNum || 0;

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
          pendingVisualCount++;
        }

        const rec = skuRecords[sku.platformCode];
        const recognition = rec?.recognition || null;
        const subItems = (archiveItem && archiveItem.subItems) || [];

        // 识图 vs 档案对比（仅在有识图结果且有档案时计算）
        let comparisonResult = null, comparisonDetail = null;
        if (recognition && archiveItem) {
          if (archiveType === '0') {
            const expected = recognition.items[0]?.name || '';
            const actual = archiveTitle || '';
            comparisonResult = expected === actual ? 'match' : 'mismatch';
            comparisonDetail = comparisonResult === 'match'
              ? `✓ ${actual}`
              : `✗ 识图:${expected} vs 档案:${actual}`;
          } else if (archiveType === '2' && subItems.length > 0) {
            const expectedSet = recognition.items.map(it => `${it.name}×${it.qty}`).sort().join(',');
            const actualSet = subItems.map(s => `${s.name}×${s.qty}`).sort().join(',');
            comparisonResult = expectedSet === actualSet ? 'match' : 'mismatch';
            comparisonDetail = comparisonResult === 'match'
              ? `✓ ${actualSet}`
              : `✗ 识图:[${expectedSet}] vs 档案:[${actualSet}]`;
          }
        }

        skuResults.push({
          skuName: sku.skuName,
          platformCode: sku.platformCode,
          erpCode: sku.erpCode,
          erpName: sku.erpName,
          archiveType,
          archiveTitle,
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
    const compMatch = allSkus.filter(s => s.comparisonResult === 'match').length;
    const compMismatch = allSkus.filter(s => s.comparisonResult === 'mismatch').length;
    const recognitionDone = allSkus.filter(s => s.recognition).length;

    report.summary = {
      total: jlProducts.length,
      notInCorr: notInCorrCount,
      fullyMatched: matchedCount,
      partiallyMatched: partialCount,
      fullyUnmatched: unmatchedCount,
      pendingVisualReview: pendingVisualCount,
      recognitionDone,
      comparisonMatch: compMatch,
      comparisonMismatch: compMismatch,
      comparisonPending: recognitionDone - compMatch - compMismatch
    };

    // 保存报告
    if (!fs.existsSync(REPORT_DIR)) fs.mkdirSync(REPORT_DIR, { recursive: true });
    const dateStr = new Date().toISOString().slice(0, 10);
    const reportPath = path.join(REPORT_DIR, `check-${shopName}-${dateStr}.json`);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.error(`[check] 报告已保存: ${reportPath}`);
    if (compMismatch > 0) {
      console.error(`[check] ⚠️ ${compMismatch} 个 SKU 识图与档案不一致，请人工核查`);
    }
    if (pendingVisualCount > 0) {
      console.error(`[check] ⚠️ ${pendingVisualCount} 个组合装待视觉核查，运行 visual-pending 查看`);
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
              imgUrl: null,
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

module.exports = { runCheck };
