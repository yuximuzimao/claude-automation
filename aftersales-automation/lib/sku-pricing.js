'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_CONFIG_PATH = path.join(__dirname, '../data/sku-pricing.json');
let configPathOverride = null;
const NUMBER_PATTERN = '[0-9零〇一二两三四五六七八九十百千]+';
const UNIT_PATTERN = '(?:盒|瓶|袋|件|支|包|罐|套)?';
const GIFT_HINT_RE = /(?:买\s*[0-9零〇一二两三四五六七八九十百千]+)|(?:[0-9零〇一二两三四五六七八九十百千]+\s*(?:盒|瓶|袋|件|支|包|罐|套)?\s*(?:赠送|加赠|赠|送))/;

function getConfigPath() {
  return configPathOverride || DEFAULT_CONFIG_PATH;
}

function setConfigPathForTests(filePath) {
  configPathOverride = filePath || null;
}

function chineseNumberToInt(input) {
  const text = String(input || '').trim();
  if (!text) return null;
  if (/^\d+$/.test(text)) return Number(text);

  const digits = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  const units = { 十: 10, 百: 100, 千: 1000 };
  let section = 0;
  let current = 0;
  let saw = false;

  for (const ch of text) {
    if (Object.prototype.hasOwnProperty.call(digits, ch)) {
      current = digits[ch];
      saw = true;
      continue;
    }
    const unit = units[ch];
    if (!unit) return null;
    saw = true;
    if (current === 0) current = 1;
    section += current * unit;
    current = 0;
  }

  if (!saw) return null;
  const total = section + current;
  return Number.isFinite(total) ? total : null;
}

function normalizeSpecName(name) {
  return String(name || '')
    .replace(/[０-９]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xFEE0))
    .replace(/[＋]/g, '+')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseGiftPricing(specName, physicalQty) {
  const name = normalizeSpecName(specName);
  const total = Number(physicalQty);
  if (!name || !Number.isInteger(total) || total <= 0) {
    return { suspected: false, parsed: false, pricedQty: null, bundledGiftQty: null };
  }

  const patterns = [
    new RegExp(`(?:买\\s*)?(${NUMBER_PATTERN})\\s*${UNIT_PATTERN}\\s*(?:赠送|加赠|赠|送)\\s*(${NUMBER_PATTERN})\\s*${UNIT_PATTERN}`),
    new RegExp(`(${NUMBER_PATTERN})\\s*${UNIT_PATTERN}\\s*\\+\\s*(${NUMBER_PATTERN})\\s*${UNIT_PATTERN}`),
  ];

  for (const pattern of patterns) {
    const match = name.match(pattern);
    if (!match) continue;
    const pricedQty = chineseNumberToInt(match[1]);
    const bundledGiftQty = chineseNumberToInt(match[2]);
    if (!Number.isInteger(pricedQty) || pricedQty <= 0 || !Number.isInteger(bundledGiftQty) || bundledGiftQty <= 0) continue;
    return {
      suspected: true,
      parsed: pricedQty + bundledGiftQty === total,
      pricedQty,
      bundledGiftQty,
    };
  }

  return {
    suspected: GIFT_HINT_RE.test(name),
    parsed: false,
    pricedQty: total,
    bundledGiftQty: 0,
  };
}

function readSkuPricingConfig() {
  const file = getConfigPath();
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch (error) {
    if (error.code === 'ENOENT') return {};
    throw error;
  }
}

function writeSkuPricingConfig(config) {
  const file = getConfigPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(config, null, 2) + '\n');
  fs.renameSync(tmp, file);
}

function getSavedSkuPricing(specCode) {
  if (!specCode) return null;
  return readSkuPricingConfig()[String(specCode)] || null;
}

function resolveSkuPricing({ specCode, specName, physicalQty }) {
  const code = String(specCode || '').trim();
  const total = Number(physicalQty);
  if (!code || !Number.isInteger(total) || total <= 0) {
    return { status: 'unavailable', reason: '缺少可复用的规格商家编码或ERP实际组成数量' };
  }

  const saved = getSavedSkuPricing(code);
  if (saved) {
    if (Number(saved.physicalQty) !== total) {
      const parsed = parseGiftPricing(specName, total);
      return {
        status: 'confirmation_required',
        compositionMismatch: true,
        specCode: code,
        specName: String(specName || ''),
        physicalQty: total,
        suggestedPricedQty: parsed.parsed ? parsed.pricedQty : Number(saved.pricedQty) || total,
        suggestedBundledGiftQty: parsed.parsed ? parsed.bundledGiftQty : Number(saved.bundledGiftQty) || 0,
        savedPhysicalQty: Number(saved.physicalQty),
      };
    }
    return {
      status: 'resolved',
      source: 'saved',
      specCode: code,
      specName: String(specName || saved.specName || ''),
      physicalQty: total,
      pricedQty: Number(saved.pricedQty),
      bundledGiftQty: Number(saved.bundledGiftQty),
    };
  }

  const parsed = parseGiftPricing(specName, total);
  if (parsed.suspected) {
    return {
      status: 'confirmation_required',
      compositionMismatch: false,
      specCode: code,
      specName: String(specName || ''),
      physicalQty: total,
      suggestedPricedQty: parsed.pricedQty,
      suggestedBundledGiftQty: parsed.bundledGiftQty,
      parseMatchedPhysicalQty: parsed.parsed,
    };
  }

  return {
    status: 'resolved',
    source: 'implicit_no_bundle_gift',
    specCode: code,
    specName: String(specName || ''),
    physicalQty: total,
    pricedQty: total,
    bundledGiftQty: 0,
  };
}

function validateConfirmedPricing(entry) {
  const specCode = String(entry && entry.specCode || '').trim();
  const specName = String(entry && entry.specName || '').trim();
  const physicalQty = Number(entry && entry.physicalQty);
  const pricedQty = Number(entry && entry.pricedQty);
  const bundledGiftQty = Number(entry && entry.bundledGiftQty);

  if (!specCode) throw new Error('缺少规格商家编码');
  if (!Number.isInteger(physicalQty) || physicalQty <= 0) throw new Error(`${specCode} ERP实际组成数量无效`);
  if (!Number.isInteger(pricedQty) || pricedQty <= 0) throw new Error(`${specCode} 主品数量必须为正整数`);
  if (!Number.isInteger(bundledGiftQty) || bundledGiftQty < 0) throw new Error(`${specCode} 赠品数量必须为非负整数`);
  if (pricedQty + bundledGiftQty !== physicalQty) {
    throw new Error(`${specCode} 主品${pricedQty}+赠品${bundledGiftQty}必须等于ERP实际组成${physicalQty}`);
  }
  return { specCode, specName, physicalQty, pricedQty, bundledGiftQty };
}

function saveConfirmedSkuPricing(entries, now = () => new Date().toISOString()) {
  const config = readSkuPricingConfig();
  const saved = [];
  for (const raw of entries || []) {
    const entry = validateConfirmedPricing(raw);
    const record = {
      specCode: entry.specCode,
      specName: entry.specName,
      physicalQty: entry.physicalQty,
      pricedQty: entry.pricedQty,
      bundledGiftQty: entry.bundledGiftQty,
      confirmedAt: now(),
    };
    config[entry.specCode] = record;
    saved.push(record);
  }
  if (saved.length) writeSkuPricingConfig(config);
  return saved;
}

module.exports = {
  chineseNumberToInt,
  parseGiftPricing,
  readSkuPricingConfig,
  getSavedSkuPricing,
  resolveSkuPricing,
  validateConfirmedPricing,
  saveConfirmedSkuPricing,
  setConfigPathForTests,
};
