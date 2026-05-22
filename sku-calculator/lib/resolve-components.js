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

  // 1b. 读满赠SKU配置
  const giftConfig = readGiftConfig();

  // 2. 收集所有唯一货号（加购 + 赠品货号）
  const giftHuohaoSet = new Set(giftConfig.giftSkus.map(g => g.huohao));
  const uniqueHuohao = [...new Set([...cartSkus.map(s => s.huohao), ...giftHuohaoSet])];
  console.log(`  唯一货号数: ${uniqueHuohao.length}（加购 + 满赠）`);

  // 3. 从对应表全量读取（与 check.js 完全相同路径）
  console.log('  读取商品对应表（全量）...');
  const corrAll = await readCorrWithoutDownload(erpId, shopName);
  console.log(`  对应表共 ${corrAll.length} 条产品记录`);

  // 4. 按货号过滤，建立 huohao::normalizedSkuName → erpCode 索引
  const corrIndex = new Map(); // `huohao::normalizedSkuName` → erpCode
  for (const prod of corrAll) {
    if (!uniqueHuohao.includes(prod.productCode)) continue;
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

  // 5. 满赠货号展开：从对应表查找每个赠品货号下的所有SKU
  //    自动检测：如果配置已有 skuName（上次已展开），跳过展开
  const needsExpansion = giftConfig.giftSkus.some(g => !g.skuName);
  const giftSkuEntries = [];
  let expandedGiftConfig;

  if (needsExpansion) {
    expandedGiftConfig = [];
    for (const gift of giftConfig.giftSkus) {
      const prod = corrAll.find(p => p.productCode === gift.huohao);
      if (!prod) {
        warnings.push(`满赠货号 ${gift.huohao} 在对应表中不存在`);
        continue;
      }
      if (!prod.skus || prod.skus.length === 0) {
        warnings.push(`满赠货号 ${gift.huohao} 在对应表中无SKU`);
        continue;
      }
      for (const sku of prod.skus) {
        if (!sku.erpCode) {
          warnings.push(`满赠货号 ${gift.huohao} SKU「${sku.skuName}」无 erpCode`);
          continue;
        }
        const normalized = sku.skuName.replace(/;.*$/, '').replace(/\s+/g, ' ').trim();
        giftSkuEntries.push({
          key: `${gift.huohao}::${normalized}`,
          huohao: gift.huohao,
          skuName: normalized,
          cartAddCount: 0,
          _isGift: true,
        });
        expandedGiftConfig.push({
          huohao: gift.huohao,
          skuName: normalized,
          fixedAllocation: gift.fixedAllocation,
        });
      }
    }
    if (giftSkuEntries.length) {
      console.log(`  满赠货号展开: ${giftConfig.giftSkus.length} 个货号 → ${giftSkuEntries.length} 个SKU`);
    }
    // 写回展开后的赠品配置，供 calculate 使用
    if (expandedGiftConfig.length > 0) {
      fs.writeFileSync(GIFT_CONFIG_FILE, JSON.stringify({ giftSkus: expandedGiftConfig }, null, 2), 'utf-8');
    }
  } else {
    // 已展开：直接使用现有配置构建伪SKU条目
    expandedGiftConfig = giftConfig.giftSkus;
    for (const g of giftConfig.giftSkus) {
      const normalized = g.skuName.replace(/\s+/g, ' ').trim();
      giftSkuEntries.push({
        key: `${g.huohao}::${normalized}`,
        huohao: g.huohao,
        skuName: g.skuName,
        cartAddCount: 0,
        _isGift: true,
      });
    }
    console.log(`  满赠 SKU: ${giftSkuEntries.length} 个（已展开，来自 gift-sku-config.json）`);
  }

  const allSkus = [...cartSkus, ...giftSkuEntries];

  // 6. 匹配每个 SKU 的 erpCode
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

  // 7. 初始化档案V2（与 check.js 完全相同路径）
  console.log('  初始化档案V2...');
  await initArchiveComp(erpId);

  // 8. 逐个查询档案（erpCode 去重）
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

  // 9. 写动态产品目录
  const productCols = [...discoveredProducts.values()];
  fs.writeFileSync(PRODUCT_COLUMNS_FILE, JSON.stringify(productCols, null, 2), 'utf-8');
  clearCache();
  console.log(`  产品目录已更新: ${productCols.length} 个单品 → ${PRODUCT_COLUMNS_FILE}`);

  // 10. 写文件
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
