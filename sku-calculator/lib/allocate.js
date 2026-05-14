/**
 * 核心库存分配算法
 *
 * 算法：迭代"耗尽即锁定" + 最大余数法回填（LRM）+ 冷热分离
 *
 * Phase 0: 预处理
 *   - 计算可用量 avail[j] = stock[j] * (1 - reserve)
 *   - 零库存单品：依赖该单品的 SKU 直接 inv=0 移出
 *   - 分离 active（cart>0）/ cold（cart=0）
 *
 * Phase A: active SKU 迭代分配（浮点）
 *   每轮：
 *     1. 计算当前活跃集合 S 对各单品的需求速率 D[j]
 *     2. 找最紧约束：b = argmin(R[j]/D[j])，t = R[b]/D[b]
 *     3. 锁定所有使用 b 的 SKU：invFloat[i] = cart[i] * t
 *     4. 扣减这批 SKU 的库存消耗，移出 S
 *   直到 S 为空
 *   → 不使用稀缺单品的 SKU 不受影响，库存充足时 invFloat > cart
 *
 * Phase B: 整数化 + LRM 回填
 *   - floor 取整
 *   - 按余数降序逐条 +1，立即扣减（防止超卖）
 *
 * Phase C: cold SKU 保底分配
 *   - 从 Phase B 剩余库存中按保底件数尝试分配
 *
 * @param {object[]} skus - 每个 SKU: { key, huohao, skuName, cartAddCount }
 * @param {object} components - { [key]: { components: { displayName: qty } } }
 * @param {object} stock - { [displayName]: qty } 云仓库存
 * @param {object} opts - { reserve: 0.2, coldFixed: 5 }
 * @returns {object} 分配结果
 */
function allocate(skus, components, stock, opts = {}) {
  const reserve   = opts.reserve   ?? 0.2;
  const coldFixed = opts.coldFixed ?? 5;

  // 辅助：获取 SKU 的组合明细（不存在则返回空对象）
  function getComp(sku) {
    return (components[sku.key] && components[sku.key].components) || {};
  }

  const warnings = [];
  const inv = {}; // key -> 最终库存整数

  // Phase 0: 可用库存
  const avail = {};
  for (const [product, qty] of Object.entries(stock)) {
    avail[product] = qty * (1 - reserve);
  }

  // Phase 0: 分离 active/cold，零库存预处理
  const activeSkus = [];
  const coldSkus   = [];

  for (const sku of skus) {
    if (sku.cartAddCount <= 0) {
      coldSkus.push(sku);
      continue;
    }
    const comp = getComp(sku);
    const infeasible = Object.entries(comp).some(
      ([p, qty]) => qty > 0 && (avail[p] ?? 0) === 0
    );
    if (infeasible) {
      inv[sku.key] = 0;
      warnings.push(`SKU ${sku.key} 因必用零库存单品而归零`);
    } else {
      activeSkus.push(sku);
    }
  }

  // Phase A: 迭代"耗尽即锁定"分配
  const R = { ...avail };         // 各单品剩余可用量（浮点）
  const invFloat = {};             // key -> 浮点分配量
  let active = [...activeSkus];    // 当前未锁定的 SKU
  let firstBottleneck = null;      // 报告用：第一个被耗尽的单品

  while (active.length > 0) {
    // 计算当前活跃集合的各单品需求速率
    const D = {};
    for (const sku of active) {
      for (const [p, qty] of Object.entries(getComp(sku))) {
        if (qty > 0) D[p] = (D[p] || 0) + sku.cartAddCount * qty;
      }
    }

    // 找最紧约束单品
    let minRatio = Infinity;
    let minProduct = null;
    for (const [p, demand] of Object.entries(D)) {
      if (demand <= 0) continue;
      const ratio = (R[p] ?? 0) / demand;
      if (ratio < minRatio) {
        minRatio = ratio;
        minProduct = p;
      }
    }

    if (minProduct === null) {
      // 剩余 SKU 不消耗任何有库存单品（comp 全空），给 cart 数量
      for (const sku of active) {
        invFloat[sku.key] = sku.cartAddCount;
      }
      break;
    }

    if (firstBottleneck === null) firstBottleneck = minProduct;

    const t = minRatio;
    const locked   = [];
    const remaining = [];

    for (const sku of active) {
      const comp = getComp(sku);
      if ((comp[minProduct] ?? 0) > 0) {
        invFloat[sku.key] = sku.cartAddCount * t;
        locked.push(sku);
      } else {
        remaining.push(sku);
      }
    }

    // 扣减被锁定 SKU 消耗的库存
    for (const sku of locked) {
      for (const [p, qty] of Object.entries(getComp(sku))) {
        R[p] = Math.max(0, (R[p] ?? 0) - invFloat[sku.key] * qty);
      }
    }

    active = remaining;
  }

  // Phase B: 整数化
  for (const sku of activeSkus) {
    inv[sku.key] = Math.floor(invFloat[sku.key] ?? 0);
  }

  // 计算 floor 后的整数剩余
  const intRem = { ...avail };
  for (const sku of activeSkus) {
    for (const [p, qty] of Object.entries(getComp(sku))) {
      intRem[p] = (intRem[p] ?? 0) - inv[sku.key] * qty;
    }
  }

  // LRM 回填：按余数降序，逐条 +1，立即扣减
  const sortedActive = [...activeSkus].sort((a, b) => {
    const remA = (invFloat[a.key] ?? 0) - inv[a.key];
    const remB = (invFloat[b.key] ?? 0) - inv[b.key];
    return remB - remA;
  });

  for (const sku of sortedActive) {
    const frac = (invFloat[sku.key] ?? 0) - inv[sku.key];
    if (frac <= 0) continue;
    const comp = getComp(sku);
    let canAdd = true;
    for (const [p, qty] of Object.entries(comp)) {
      if ((intRem[p] ?? 0) < qty) { canAdd = false; break; }
    }
    if (canAdd) {
      inv[sku.key] += 1;
      for (const [p, qty] of Object.entries(comp)) {
        intRem[p] = (intRem[p] ?? 0) - qty;
      }
    }
  }

  // Phase C: cold SKU 保底分配
  for (const sku of coldSkus) {
    const comp = getComp(sku);
    let canAllocate = true;
    for (const [p, qty] of Object.entries(comp)) {
      if ((intRem[p] ?? 0) < coldFixed * qty) { canAllocate = false; break; }
    }
    if (canAllocate) {
      inv[sku.key] = coldFixed;
      for (const [p, qty] of Object.entries(comp)) {
        intRem[p] = (intRem[p] ?? 0) - coldFixed * qty;
      }
    } else {
      inv[sku.key] = 0;
      warnings.push(`冷门 SKU 保底不足，跳过: ${sku.key}`);
    }
  }

  // 缺少组合明细警告
  for (const sku of skus) {
    if (!components[sku.key]) {
      warnings.push(`⚠️  缺少组合明细: ${sku.key}，无法计算单品占用`);
    }
  }

  // 报告用：计算瓶颈（baseDemand 最紧约束，用于输出参考）
  const baseDemand = {};
  for (const sku of activeSkus) {
    for (const [p, qty] of Object.entries(getComp(sku))) {
      baseDemand[p] = (baseDemand[p] || 0) + sku.cartAddCount * qty;
    }
  }
  const bottlenecks = [];
  for (const [p, demand] of Object.entries(baseDemand)) {
    if (demand > 0) {
      const ratio = (avail[p] ?? 0) / demand;
      bottlenecks.push({ product: p, demand, available: avail[p] ?? 0, ratio });
    }
  }
  const bottleneckProduct = bottlenecks.reduce(
    (min, b) => b.ratio < min.ratio ? b : min,
    { ratio: Infinity, product: null }
  );
  const globalMinK = bottlenecks.length > 0 ? Math.min(...bottlenecks.map(b => b.ratio)) : 1.0;

  // 人工复核警告：需求超过可用量的单品（ratio < 1）
  for (const b of bottlenecks) {
    if (b.ratio < 1) {
      warnings.push(
        `⚠️ [人工复核] ${b.product}: 云仓库存${stock[b.product]}件，可用量${Math.round(b.available)}件，全量需求${Math.round(b.demand)}件，库存不足（${(b.ratio * 100).toFixed(1)}%），请人工确认分配方案`
      );
    }
  }

  // 计算各单品总需求（报告用）
  const totalDemand = {};
  for (const sku of skus) {
    const allocation = inv[sku.key] || 0;
    for (const [p, qty] of Object.entries(getComp(sku))) {
      totalDemand[p] = (totalDemand[p] || 0) + allocation * qty;
    }
  }

  // 构建 SKU 明细
  const skuDetails = skus.map(sku => {
    const comp = getComp(sku);
    const allocation = inv[sku.key] || 0;
    const productBreakdown = {};
    for (const [p, qty] of Object.entries(comp)) {
      productBreakdown[p] = { qtyPerUnit: qty, totalDemand: allocation * qty };
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
      k: parseFloat(Math.min(globalMinK, 1.0).toFixed(6)), // 最紧约束系数（仅报告参考）
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
    available: avail,
    remaining: intRem,
  };
}

module.exports = { allocate };
