'use strict';

function requireCode(value, name) {
  const code = String(value || '').trim();
  if (!code) throw new Error(`${name} 不能为空`);
  return code;
}

function recordKey(productCode, platformCode) {
  return `${requireCode(productCode, 'productCode')}::${requireCode(platformCode, 'platformCode')}`;
}

function safeFilePart(value, name) {
  return requireCode(value, name).replace(/[\/\\:\0]/g, '_');
}

function imageFileName(productCode, platformCode) {
  return `${safeFilePart(productCode, 'productCode')}__${safeFilePart(platformCode, 'platformCode')}.jpg`;
}

function findRecord(records, productCode, platformCode) {
  if (!records || typeof records !== 'object') return null;

  const key = recordKey(productCode, platformCode);
  if (records[key]) return records[key];

  const legacy = records[platformCode];
  if (legacy && (!legacy.productCode || legacy.productCode === productCode)) return legacy;

  return Object.values(records).find(record =>
    record &&
    record.productCode === productCode &&
    record.platformCode === platformCode
  ) || null;
}

module.exports = {
  recordKey,
  imageFileName,
  findRecord,
};
