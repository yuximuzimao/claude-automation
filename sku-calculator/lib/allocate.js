/**
 * 核心库存分配算法
 *
 * 算法：全局统一缩放 + 最大余数法回填（LRM）+ 冷热分离
 *
 * 步骤：
 * Phase A: 有加购 SKU
 *   1. 分离 active(有加购) / cold(无加购) SKU
 *   2. available[j] = stock[j] * (1 - reserve)
 *   3. k = min(1, min(available[j] / baseDemand[j]))
 *   4. inv[i] = floor(base[i] * k)
 *   5. LRM 回填：按余数排序，逐条 +1 并立即扣减 remaining
 * Phase B: 无加购 SKU
 *   6. 从 Phase A 剩余库存中分配保底
 *
 * @param {object[]} skus - 每个 SKU: { key, huohao, skuName, cartAddCount }
 * @param {object} components - { [key]: { components: { displayName: qty } } }
 * @param {object} stock - { [displayName]: qty } 云仓库存
 * @param {object} opts - { reserve: 0.2, coldFixed: 5 }
 * @returns {object} 分配结果
 */
function allocate(skus, components, stock, opts = {}) {
  const reserve    = opts.reserve   ?? 0.2;
  const coldFixed  = opts.coldFixed ?? 5;

  // 1. 分离 active / cold
  const activeSkus = skus.filter(s => s.cartAddCount > 0);
  const coldSkus   = skus.filter(s => s.cartAddCount <= 0);

  // 2. 可用库存
  const available = {};
  for (const [product, qty] of Object.entries(stock)) {
    available[product] = qty * (1 - reserve);
  }

  // 辅助：获取 SKU 的组合明细（不存在则返回空对象）
  function getComp(sku) {
    return (components[sku.key] && components[sku.key].components) || {};
  }

  const warnings = [];
  const inv   = {}; // key -> 最终库存整数

  // 3. 预过滤：移除"必须使用某个零库存单品"的 SKU（这些 SKU 必然是0）
  const feasibleActive = [];
  for (const sku of activeSkus) {
    const comp = getComp(sku);
    const infeasible = Object.entries(comp).some(
      ([product, qty]) => qty > 0 && (available[product] ?? 0) === 0
    );
    if (infeasible) {
      inv[sku.key] = 0;
      warnings.push(`SKU ${sku.key} 因必用零库存单品而归零`);
    } else {
      feasibleActive.push(sku);
    }
  }

  // 用 feasibleActive 参与 k 计算
  const baseDemand = {}; // product -> 总需求（k=1 时）
  for (const sku of feasibleActive) {
    const comp = getComp(sku);
    for (const [product, qty] of Object.entries(comp)) {
      baseDemand[product] = (baseDemand[product] || 0) + sku.cartAddCount * qty;
    }
  }

  const bottlenecks = [];
  let k = 1.0;

  for (const [product, demand] of Object.entries(baseDemand)) {
    if (demand === 0) continue;
    const avail = available[product] ?? 0;
    const ratio = avail / demand;
    bottlenecks.push({ product, demand, available: avail, ratio });
    if (ratio < k) {
      k = ratio;
    }
  }

  // k 封顶为 1（不超额备货）
  k = Math.min(k, 1.0);

  const bottleneckProduct = bottlenecks.reduce(
    (min, b) => b.ratio < min.ratio ? b : min,
    { ratio: Infinity, product: null }
  );

  // 4. 应用缩放，计算精确值和 floor 值（仅可行 SKU）
  const exact = {}; // key -> 浮点值

  for (const sku of feasibleActive) {
    exact[sku.key] = sku.cartAddCount * k;
    inv[sku.key]   = Math.floor(exact[sku.key]);
  }

  // 5. LRM 回填——实时扣减模式
  // 先计算 Phase A floor 后的剩余
  const remaining = { ...available };
  for (const sku of feasibleActive) {
    const comp = getComp(sku);
    for (const [product, qty] of Object.entries(comp)) {
      remaining[product] = (remaining[product] ?? 0) - inv[sku.key] * qty;
    }
  }

  // 按余数从大到小排序（仅可行 SKU）
  const sortedActive = [...feasibleActive].sort((a, b) => {
    const remA = exact[a.key] - inv[a.key];
    const remB = exact[b.key] - inv[b.key];
    return remB - remA;
  });

  for (const sku of sortedActive) {
    // 只回填有 floor 损失的 SKU（余数 > 0）
    if (exact[sku.key] - inv[sku.key] === 0) continue;

    const comp = getComp(sku);
    // 检查 +1 是否满足所有单品约束
    let canAdd = true;
    for (const [product, qty] of Object.entries(comp)) {
      if ((remaining[product] ?? 0) < qty) {
        canAdd = false;
        break;
      }
    }
    if (canAdd) {
      inv[sku.key] += 1;
      // 立即扣减 remaining
      for (const [product, qty] of Object.entries(comp)) {
        remaining[product] = (remaining[product] ?? 0) - qty;
      }
    }
  }

  // 6. Phase B: 无加购 SKU 保底分配
  for (const sku of coldSkus) {
    const comp = getComp(sku);
    let canAllocate = true;
    const need = {};
    for (const [product, qty] of Object.entries(comp)) {
      need[product] = coldFixed * qty;
      if ((remaining[product] ?? 0) < need[product]) {
        canAllocate = false;
        break;
      }
    }
    if (canAllocate) {
      inv[sku.key] = coldFixed;
      for (const [product, qty] of Object.entries(need)) {
        remaining[product] = (remaining[product] ?? 0) - qty;
      }
    } else {
      inv[sku.key] = 0;
      warnings.push(`冷门 SKU 保底不足，跳过: ${sku.key}`);
    }
  }

  // 检查是否有 SKU 没有组合明细
  for (const sku of skus) {
    if (!components[sku.key]) {
      warnings.push(`⚠️  缺少组合明细: ${sku.key}，无法计算单品占用`);
    }
  }

  // 计算各单品总需求（用于报告）
  const totalDemand = {};
  for (const sku of skus) {
    const comp = getComp(sku);
    const allocation = inv[sku.key] || 0;
    for (const [product, qty] of Object.entries(comp)) {
      totalDemand[product] = (totalDemand[product] || 0) + allocation * qty;
    }
  }

  // 构建每个 SKU 的明细（单品用量 + 总占用）
  const skuDetails = skus.map(sku => {
    const comp = getComp(sku);
    const allocation = inv[sku.key] || 0;
    const productBreakdown = {};
    for (const [product, qty] of Object.entries(comp)) {
      productBreakdown[product] = {
        qtyPerUnit: qty,
        totalDemand: allocation * qty,
      };
    }
    return {
      key: sku.key,
      huohao: sku.huohao,
      skuName: sku.skuName,
      cartAddCount: sku.cartAddCount,
      isActive: sku.cartAddCount > 0,
      allocatedInventory: allocation,
      productBreakdown,
    };
  });

  return {
    _meta: {
      k: parseFloat(k.toFixed(6)),
      reserve,
      coldFixed,
      bottleneck: bottleneckProduct.product,
      bottleneckRatio: bottleneckProduct.ratio === Infinity ? null : parseFloat(bottleneckProduct.ratio.toFixed(4)),
      activeCount: activeSkus.length,
      coldCount: coldSkus.length,
      warnings,
    },
    skuDetails,
    totalDemand,
    available,
    remaining,
  };
}

module.exports = { allocate };
