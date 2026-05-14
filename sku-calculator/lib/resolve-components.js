'use strict';
/**
 * WHAT: 从 ERP 商品对应表（逐货号精确搜索）+ 档案V2 读取每个 SKU 的组合明细
 * HOW:  per-product readTableRows → erpCode 映射 → queryArchive → querySubItems
 * OUT:  data/sku-components.json
 *
 * 关键：对应表使用虚拟滚动，全量读取（readCorrWithoutDownload）返回 0 行。
 * 改用逐货号精确搜索（同 product-mapping read-skus），每次只渲染1行，绕过虚拟滚动。
 */
const fs   = require('fs');
const path = require('path');
const cdp  = require('../../product-mapping/lib/cdp');
const { sleep, waitFor }    = require('../../product-mapping/lib/wait');
const { ensureCorrPage }    = require('../../product-mapping/lib/ops/ensure-corr-page');
const { readTableRows }     = require('../../product-mapping/lib/ops/read-table-rows');
const { initArchiveComp, queryArchive, querySubItems } = require('../../product-mapping/lib/archive');
const { getByErpName }      = require('./product-catalog');

const DATA_DIR    = path.join(__dirname, '../data');
const OUTPUT_FILE = path.join(DATA_DIR, 'sku-components.json');

/**
 * 在主页（非 dialog）的 el-select 中选值
 * （移植自 product-mapping/lib/ops/read-skus.js，未对外导出故在此复制）
 */
async function _setMainPageSelect(erpId, selectIdx, optionText) {
  const currentVal = await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(!sel) return "";' +
    '  var inp=sel.querySelector("input");' +
    '  return inp?inp.value:"";' +
    '})()'
  );
  if (currentVal === optionText) return;

  await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(sel) sel.click();' +
    '})()'
  );
  await sleep(400);

  await cdp.eval(erpId,
    '(function(){' +
    '  var items=document.querySelectorAll(".el-select-dropdown__item");' +
    '  for(var i=0;i<items.length;i++){' +
    '    if(items[i].innerText.trim()===' + JSON.stringify(optionText) + '&&items[i].getBoundingClientRect().height>0){' +
    '      items[i].click();return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(300);
}

/**
 * 查询单个货号在对应表中的 skuName → erpCode 映射
 * @returns {Map<string, string>} skuName → erpCode
 */
async function _queryProductErpCodes(erpId, shopName, huohao, warnings) {
  await ensureCorrPage(erpId);

  // 等搜索输入框就绪
  await waitFor(async () => {
    const ready = await cdp.eval(erpId,
      '(function(){' +
      '  var items=Array.from(document.querySelectorAll(".el-form-item")).filter(function(f){return !f.closest(".el-dialog__wrapper")});' +
      '  return items.length>=5&&items[4].querySelector("input")?"ready":"not-ready";' +
      '})()'
    );
    return ready === 'ready';
  }, { timeoutMs: 10000, intervalMs: 500, label: '等搜索输入框就绪' });

  // 点击左侧店铺
  const shopClicked = await cdp.eval(erpId,
    '(function(){' +
    '  var spans=document.querySelectorAll("span");' +
    '  for(var i=0;i<spans.length;i++){' +
    '    if(spans[i].innerText.trim().includes(' + JSON.stringify(shopName) + ')&&spans[i].className.includes("el-tooltip")){' +
    '      spans[i].click();return "clicked";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (shopClicked !== 'clicked') throw new Error(`左侧店铺「${shopName}」未找到`);
  await sleep(1500);

  // 设搜索下拉：精确搜索 + 平台商家编码
  await _setMainPageSelect(erpId, 4, '精确搜索');
  await _setMainPageSelect(erpId, 5, '平台商家编码');

  // 输入货号 + 回车
  const inputResult = await cdp.eval(erpId,
    '(function(){' +
    '  var editor=document.querySelector(".el-input-popup-editor");' +
    '  if(!editor) return "editor-not-found";' +
    '  var inp=editor.querySelector("input");' +
    '  if(!inp) return "input-not-found";' +
    '  inp.value=' + JSON.stringify(huohao) + ';' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  return "triggered";' +
    '})()'
  );
  if (inputResult !== 'triggered') throw new Error('搜索输入框未找到: ' + inputResult);
  await sleep(3500);

  // 验证有结果，并读取 ERP 表中实际显示的 productCode（可能大小写与 huohao 不同）
  const firstRowCode = await cdp.eval(erpId,
    '(function(){' +
    '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
    '  if(!rows.length) return "";' +
    '  var tds=rows[0].querySelectorAll("td");' +
    '  return tds[6]?tds[6].innerText.trim():"";' +
    '})()'
  );
  if (!firstRowCode) {
    warnings.push(`货号「${huohao}」在对应表中无搜索结果，跳过`);
    return new Map();
  }
  // 用 ERP 实际显示的编码（防止大小写不一致导致 readTableRows 超时）
  const actualProductCode = firstRowCode;

  // 读取子行（platformCode → erpCode）
  const subRows = await readTableRows(erpId, {
    fields: ['skuName', 'platformCode', 'erpCode'],
    expectedProductCode: actualProductCode,
  });

  // ERP skuName 格式：「名称;KGOS」，去掉 ; 后缀 + 空格归一 → 与加购 skuName 匹配
  const skuMap = new Map(); // normalizedSkuName → erpCode
  for (const row of subRows) {
    if (row.erpCode) {
      const normalized = row.skuName.replace(/;.*$/, '').replace(/\s+/g, ' ').trim();
      skuMap.set(normalized, row.erpCode);
    } else {
      warnings.push(`货号 ${huohao} SKU「${row.skuName}」无 erpCode`);
    }
  }
  return skuMap;
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

  // 1. 读加购数据
  const cartData = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'cart-adds.json'), 'utf-8'));
  const skus = cartData.skus;
  console.log(`  加购 SKU 总数: ${skus.length}`);

  // 2. 收集所有唯一货号
  const uniqueHuohao = [...new Set(skus.map(s => s.huohao))];
  console.log(`  唯一货号数: ${uniqueHuohao.length}`);

  const warnings = [];

  // 3. 逐货号从对应表精确搜索（绕过虚拟滚动）
  console.log('  逐货号读取对应表...');
  // corrIndex key: `huohao::normalizedSkuName`（空格归一）→ erpCode
  const corrIndex = new Map();

  for (let i = 0; i < uniqueHuohao.length; i++) {
    const huohao = uniqueHuohao[i];
    process.stdout.write(`  [${i + 1}/${uniqueHuohao.length}] 对应表查询: ${huohao}\r`);
    try {
      const skuMap = await _queryProductErpCodes(erpId, shopName, huohao, warnings);
      for (const [normalizedName, erpCode] of skuMap) {
        corrIndex.set(`${huohao}::${normalizedName}`, erpCode);
      }
    } catch (err) {
      warnings.push(`货号 ${huohao} 查询对应表失败: ${err.message}`);
    }
  }
  console.log(`\n  对应表查询完成，共 ${corrIndex.size} 条 SKU → erpCode 映射`);

  // 4. 匹配每个 SKU 的 erpCode（加购 skuName 也做空格归一再查）
  const matched = [];
  for (const sku of skus) {
    const normalizedSkuName = sku.skuName.replace(/\s+/g, ' ').trim();
    const key = `${sku.huohao}::${normalizedSkuName}`;
    const erpCode = corrIndex.get(key);
    if (!erpCode) {
      warnings.push(`对应表中找不到: ${key}`);
      continue;
    }
    matched.push({ ...sku, erpCode });
  }
  console.log(`  匹配成功: ${matched.length}/${skus.length}，警告: ${warnings.length}`);

  // 5. 初始化档案V2（导航到档案页 + 清空条件，只做一次）
  console.log('  初始化档案V2...');
  await initArchiveComp(erpId);

  // 6. 逐个查询档案（erpCode 去重，避免重复 ERP 请求）
  const erpCodeCache = new Map(); // erpCode → components | null
  const result = {};

  for (let i = 0; i < matched.length; i++) {
    const sku = matched[i];
    process.stdout.write(`  [${i + 1}/${matched.length}] 档案查询: ${sku.key}\r`);

    let components;

    if (erpCodeCache.has(sku.erpCode)) {
      components = erpCodeCache.get(sku.erpCode);
    } else {
      const archiveItem = await queryArchive(erpId, sku.erpCode);

      if (!archiveItem) {
        warnings.push(`档案V2 中找不到 erpCode: ${sku.erpCode}（SKU: ${sku.key}）`);
        erpCodeCache.set(sku.erpCode, null);
        components = null;
      } else if (archiveItem.subItemNum > 0) {
        // 组合装：读子品明细
        const subItems = await querySubItems(erpId, archiveItem.subItemNum);
        components = {};
        for (const sub of subItems) {
          const col = getByErpName(sub.name);
          if (!col) {
            warnings.push(`子品名称映射失败: "${sub.name}"（SKU: ${sku.key}）`);
            continue;
          }
          components[col.displayName] = (components[col.displayName] || 0) + sub.qty;
        }
        if (!Object.keys(components).length) {
          warnings.push(`组合装子品全部映射失败: ${sku.erpCode}（SKU: ${sku.key}）`);
          components = null;
        }
      } else {
        // 单品：组件就是档案标题对应的单品 × 1
        const col = getByErpName(archiveItem.title);
        if (!col) {
          warnings.push(`单品档案名称映射失败: "${archiveItem.title}"（SKU: ${sku.key}）`);
          components = null;
        } else {
          components = { [col.displayName]: 1 };
        }
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

  // 7. 写文件（格式与 mock 兼容：顶层 _meta + 各 key 平铺）
  const output = {
    _meta: {
      source:       `ERP 商品对应表（逐货号）+ 档案V2（${shopName}）`,
      resolvedAt:   new Date().toISOString(),
      totalSkus:    skus.length,
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
