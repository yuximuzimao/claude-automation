'use strict';
/**
 * WHAT: 从 ERP 商品对应表（全量读取）+ 档案V2 读取每个 SKU 的组合明细
 * HOW:  readCorrWithoutDownload（全量展开读取） → huohao 过滤 → erpCode 映射
 *       → initArchiveComp → queryArchive → querySubItems
 * OUT:  data/sku-components.json
 *
 * 与 product-mapping check.js 完全一致的路径，已验证可跑通。
 */
const fs   = require('fs');
const path = require('path');
const { readCorrWithoutDownload } = require('../../product-mapping/lib/correspondence');
const { initArchiveComp, queryArchive, querySubItems } = require('../../product-mapping/lib/archive');
const { clearCache } = require('./product-catalog');

const DATA_DIR             = path.join(__dirname, '../data');
const OUTPUT_FILE          = path.join(DATA_DIR, 'sku-components.json');
const PRODUCT_COLUMNS_FILE = path.join(DATA_DIR, 'product-columns.json');
const GIFT_CONFIG_FILE     = path.join(DATA_DIR, 'gift-sku-config.json');

/** 读取满赠SKU配置（不存在则返回空） */
function readGiftConfig() {
  if (!fs.existsSync(GIFT_CONFIG_FILE)) return { giftSkus: [] };
  return JSON.parse(fs.readFileSync(GIFT_CONFIG_FILE, 'utf-8'));
}

/**
 * 主入口：查询组合明细
 * @param {string} erpId  - CDP target ID
 * @param {string} [shopName='澜泽']
 * @returns {object} 与 sku-components.json 格式一致的对象
 */
async function resolveComponents(erpId, shopName = '澜泽') {
  // 清空旧数据，避免不同店铺间相互干扰
  fs.writeFileSync(OUTPUT_FILE, '{}', 'utf-8');
  fs.writeFileSync(PRODUCT_COLUMNS_FILE, '[]', 'utf-8');

  const warnings = [];

  // 动态发现的单品目录：erpName → {colIndex, displayName, erpNames}
  const discoveredProducts = new Map();

  // 1. 读加购数据
  const cartData = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'cart-adds.json'), 'utf-8'));
  const cartSkus = cartData.skus;
  console.log(`  加购 SKU 总数: ${cartSkus.length}`);

  // 1b. 读满赠SKU配置，构建伪SKU条目（用于参与ERP解析流程）
  const giftConfig = readGiftConfig();
  const giftSkuEntries = giftConfig.giftSkus.map(g => ({
    key: `${g.huohao}::${g.skuName.replace(/\s+/g, ' ').trim()}`,
    huohao: g.huohao,
    skuName: g.skuName,
    cartAddCount: 0,
    _isGift: true,
  }));
  const allSkus = [...cartSkus, ...giftSkuEntries];
  if (giftSkuEntries.length) {
    console.log(`  满赠 SKU 数: ${giftSkuEntries.length}（不在加购Excel中，从 gift-sku-config.json 读取）`);
  }

  // 2. 收集所有唯一货号（加购 + 赠品）
  const uniqueHuohao = [...new Set(allSkus.map(s => s.huohao))];
  console.log(`  唯一货号数: ${uniqueHuohao.length}`);

  // 2. 从对应表全量读取（与 check.js 完全相同路径）
  console.log('  读取商品对应表（全量）...');
  const corrAll = await readCorrWithoutDownload(erpId, shopName);
  console.log(`  对应表共 ${corrAll.length} 条产品记录`);

  // 3. 按货号过滤，建立 huohao::normalizedSkuName → erpCode 索引
  const corrIndex = new Map(); // `huohao::normalizedSkuName` → erpCode
  for (const prod of corrAll) {
    if (!uniqueHuohao.has(prod.productCode)) continue;
    for (const sku of prod.skus) {
      if (!sku.erpCode) {
        warnings.push(`货号 ${prod.productCode} SKU「${sku.skuName}」无 erpCode`);
        continue;
      }
      const normalized = sku.skuName.replace(/;.*$/, '').replace(/\s+/g, ' ').trim();
      corrIndex.set(`${prod.productCode}::${normalized}`, sku.erpCode);
    }
  }
  console.log(`  共 ${corrIndex.size} 条 SKU → erpCode 映射`);

  // 4. 匹配每个 SKU 的 erpCode（加购 + 赠品 SKU 的 skuName 也做空格归一再查）
  const matched = [];
  for (const sku of allSkus) {
    const normalizedSkuName = sku.skuName.replace(/\s+/g, ' ').trim();
    const key = `${sku.huohao}::${normalizedSkuName}`;
    const erpCode = corrIndex.get(key);
    if (!erpCode) {
      warnings.push(`对应表中找不到: ${key}`);
      continue;
    }
    matched.push({ ...sku, erpCode });
  }
  console.log(`  匹配成功: ${matched.length}/${allSkus.length}，警告: ${warnings.length}`);

  // 5. 初始化档案V2（与 check.js 完全相同路径）
  console.log('  初始化档案V2...');
  await initArchiveComp(erpId);

  // 6. 逐个查询档案（erpCode 去重）
  const erpCodeCache = new Map(); // erpCode → components | null
  const result = {};

  for (let i = 0; i < matched.length; i++) {
    const sku = matched[i];
    process.stdout.write(`  [${i + 1}/${matched.length}] 档案查询: ${sku.key}\r`);

    let components;

    if (erpCodeCache.has(sku.erpCode)) {
      components = erpCodeCache.get(sku.erpCode);
    } else {
      let archiveItem;
      try {
        archiveItem = await queryArchive(erpId, sku.erpCode);
      } catch (err) {
        warnings.push(`档案V2 查询异常 ${sku.erpCode}: ${err.message}`);
        erpCodeCache.set(sku.erpCode, null);
        continue;
      }

      if (!archiveItem) {
        warnings.push(`档案V2 中找不到 erpCode: ${sku.erpCode}（SKU: ${sku.key}）`);
        erpCodeCache.set(sku.erpCode, null);
        components = null;
      } else if (archiveItem.subItemNum > 0) {
        // 组合装：读子品明细
        const subItems = await querySubItems(erpId, archiveItem.subItemNum);
        components = {};
        for (const sub of subItems) {
          if (!discoveredProducts.has(sub.name)) {
            discoveredProducts.set(sub.name, {
              colIndex:    discoveredProducts.size,
              displayName: sub.name,
              erpNames:    [sub.name],
            });
          }
          components[sub.name] = (components[sub.name] || 0) + sub.qty;
        }
        if (!Object.keys(components).length) {
          components = null;
        }
      } else {
        // 单品：组件就是档案标题对应的单品 × 1
        const erpName = archiveItem.title;
        if (!discoveredProducts.has(erpName)) {
          discoveredProducts.set(erpName, {
            colIndex:    discoveredProducts.size,
            displayName: erpName,
            erpNames:    [erpName],
          });
        }
        components = { [erpName]: 1 };
      }

      erpCodeCache.set(sku.erpCode, components);
    }

    if (components) {
      result[sku.key] = {
        huohao:     sku.huohao,
        skuName:    sku.skuName,
        erpCode:    sku.erpCode,
        components,
      };
    }
  }

  console.log(`\n  完成: ${Object.keys(result).length} 个 SKU 有组合明细`);

  if (warnings.length) {
    console.log(`  警告共 ${warnings.length} 条:`);
    warnings.forEach(w => console.warn(`  ⚠️  ${w}`));
  }

  // 7. 写动态产品目录
  const productCols = [...discoveredProducts.values()];
  fs.writeFileSync(PRODUCT_COLUMNS_FILE, JSON.stringify(productCols, null, 2), 'utf-8');
  clearCache();
  console.log(`  产品目录已更新: ${productCols.length} 个单品 → ${PRODUCT_COLUMNS_FILE}`);

  // 8. 写文件
  const output = {
    _meta: {
      source:       `ERP 商品对应表（全量）+ 档案V2（${shopName}）`,
      resolvedAt:   new Date().toISOString(),
      totalSkus:    allSkus.length,
      cartSkuCount: cartSkus.length,
      giftSkuCount: giftSkuEntries.length,
      matchedSkus:  matched.length,
      resolvedSkus: Object.keys(result).length,
      warnings,
    },
    ...result,
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2), 'utf-8');
  console.log(`  已保存 → ${OUTPUT_FILE}`);

  return output;
}

module.exports = { resolveComponents };
