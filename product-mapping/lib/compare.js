'use strict';

const { resolveItems } = require('./utils/resolve-items');

function formatItems(items) {
  return items.map(it => `${it.name}×${it.qty}`).sort().join(',');
}

function hasArchiveDetails(archiveType, archiveTitle, subItems) {
  if (archiveType === '0' && archiveTitle) return true;
  if (archiveType === '2' && Array.isArray(subItems) && subItems.length > 0) return true;
  return false;
}

function compareSkuArchive({ platformCode, recognition, archiveType, archiveTitle, subItems = [], brand = 'hee' }) {
  if (!recognition || !Array.isArray(recognition.items) || recognition.items.length === 0) {
    if (hasArchiveDetails(archiveType, archiveTitle, subItems)) {
      return {
        comparisonResult: 'mismatch',
        comparisonDetail: '✗ 识图为空，但 ERP 档案有明细',
      };
    }
    return {
      comparisonResult: null,
      comparisonDetail: '未对比：识图为空且无 ERP 档案明细',
    };
  }

  if (archiveType === '0' && archiveTitle) {
    const recItem = recognition.items[0];
    const expected = recItem?.name || '';
    const expectedQty = recItem?.qty ?? 0;
    const actual = archiveTitle || '';
    const nameOk = expected === actual;
    const qtyOk = expectedQty === 1;
    const comparisonResult = (nameOk && qtyOk) ? 'match' : 'mismatch';
    return {
      comparisonResult,
      comparisonDetail: comparisonResult === 'match'
        ? `✓ ${actual}`
        : !nameOk
          ? `✗ 识图:${expected} vs 档案:${actual}`
          : `✗ 识图数量×${expectedQty} vs 单品档案×1（ERP未建套件档案）`,
    };
  }

  if (archiveType === '2' && Array.isArray(subItems) && subItems.length > 0) {
    const resolvedItems = resolveItems(platformCode, recognition.items, brand);
    const expectedSet = formatItems(resolvedItems);
    const actualSet = formatItems(subItems);
    const comparisonResult = expectedSet === actualSet ? 'match' : 'mismatch';
    return {
      comparisonResult,
      comparisonDetail: comparisonResult === 'match'
        ? `✓ ${actualSet}`
        : `✗ 识图:[${expectedSet}] vs 档案:[${actualSet}]`,
    };
  }

  return {
    comparisonResult: 'mismatch',
    comparisonDetail: '✗ 有识图结果，但 ERP 档案无可比明细',
  };
}

module.exports = { compareSkuArchive };
