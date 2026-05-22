/**
 * 核心库存分配算法
 *
 * 算法：赠品预扣 + 迭代"耗尽即锁定" + 最大余数法回填（LRM）+ 冷热分离
 *
 * Phase G: 赠品SKU固定分配（在 Phase 0 之前）
 *   - 读取 giftConfig，对每个赠品SKU按固定数量预扣库存
 *   - 库存不足直接报错中止（赠品是客户承诺，不能缺）
 *   - 赠品SKU从后续算法流程中移除
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
 * @param {object} opts - { reserve: 0.2, coldFixed: 5, giftConfig: [{ huohao, skuName, fixedAllocation }] }
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

  // Phase 0: 可用库存（初始全量，赠品预扣后再对剩余应用余量比例）
  const avail = { ...stock };

  // Phase G: 赠品SKU固定分配 — 在算法运行前预扣库存
  // 规则：赠品最多占单品库存的 (1-reserve)，即 80%。
  // 仅当赠品需求超过此上限时才等比例缩减，否则不做任何调整。
  const giftKeys = new Set();
  const giftSkus = []; // 用于最终输出
  const giftConfig = opts.giftConfig || [];

  if (giftConfig.length > 0) {
    const GIFT_CAP_RATIO = 1 - reserve;

    // G1: 构建赠品SKU列表（含初始分配量）
    const giftAllocs = [];
    for (const gift of giftConfig) {
      const key = `${gift.huohao}::${gift.skuName.replace(/\s+/g, ' ').trim()}`;
      const comp = (components[key] && components[key].components) || {};

      if (!Object.keys(comp).length) {
        throw new Error(
          `满赠SKU ${key} 无组合明细。请先运行 resolve-components 确保赠品SKU已从ERP解析`
        );
      }

      giftAllocs.push({ key, huohao: gift.huohao, skuName: gift.skuName, comp, allocation: gift.fixedAllocation });
    }

    // G2: 检测受限单品并等比例缩减（迭代至所有单品满足 赠品需求 ≤ stock×cap）
    let changed = true;
    let iter = 0;
    while (changed && iter < 20) {
      changed = false;
      iter++;

      const giftDemand = {};
      for (const g of giftAllocs) {
        for (const [p, qty] of Object.entries(g.comp)) {
          giftDemand[p] = (giftDemand[p] || 0) + g.allocation * qty;
        }
      }

      let maxRatio = 0;
      let maxProduct = null;
      for (const [p, demand] of Object.entries(giftDemand)) {
        const cap = (stock[p] || 0) * GIFT_CAP_RATIO;
        if (cap <= 0) continue;
        const ratio = demand / cap;
        if (ratio > maxRatio && ratio > 1.0001) {
          maxRatio = ratio;
          maxProduct = p;
        }
      }

      if (!maxProduct) break;

      const factor = 1 / maxRatio;
      const cap = (stock[maxProduct] || 0) * GIFT_CAP_RATIO;
      for (const g of giftAllocs) {
        if (g.comp[maxProduct]) {
          const oldAlloc = g.allocation;
          g.allocation = Math.floor(oldAlloc * factor);
          if (g.allocation !== oldAlloc) changed = true;
        }
      }

      if (changed) {
        warnings.push(
          `[赠品缩减] 单品「${maxProduct}」赠品需求超 stock×${(GIFT_CAP_RATIO * 100).toFixed(0)}%` +
          `（上限${Math.round(cap)}件），等比例缩减（因子=${factor.toFixed(4)}）`
        );
      }
    }

    // G3: 预扣库存
    for (const g of giftAllocs) {
      for (const [p, qty] of Object.entries(g.comp)) {
        const required = g.allocation * qty;
        const available = avail[p] ?? 0;
        if (available < required) {
          throw new Error(
            `满赠SKU ${g.key} 库存不足: 单品「${p}」需要 ${required} 件` +
            `（${g.allocation} 件 × ${qty}），可用仅 ${Math.round(available)} 件`
          );
        }
      }

      for (const [p, qty] of Object.entries(g.comp)) {
        avail[p] = (avail[p] ?? 0) - g.allocation * qty;
      }

      inv[g.key] = g.allocation;
      giftKeys.add(g.key);
      giftSkus.push(g);
    }
  }

  // 赠品预扣完毕后，对剩余库存应用余量比例（保证正常SKU有安全余量）
  for (const [p, qty] of Object.entries(avail)) {
    avail[p] = qty * (1 - reserve);
  }

  // 过滤掉赠品SKU，剩余进入正常算法流程
  const nonGiftSkus = skus.filter(s => !giftKeys.has(s.key));

  // Phase 0: 分离 active/cold，零库存预处理
  const activeSkus = [];
  const coldSkus   = [];

  for (const sku of nonGiftSkus) {
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

  // 缺少组合明细警告（仅针对非赠品SKU，赠品已在Phase G校验）
  for (const sku of nonGiftSkus) {
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

  // 计算各单品总需求（报告用，含赠品SKU）
  const totalDemand = {};
  for (const sku of nonGiftSkus) {
    const allocation = inv[sku.key] || 0;
    for (const [p, qty] of Object.entries(getComp(sku))) {
      totalDemand[p] = (totalDemand[p] || 0) + allocation * qty;
    }
  }
  for (const gift of giftSkus) {
    for (const [p, qty] of Object.entries(gift.comp)) {
      totalDemand[p] = (totalDemand[p] || 0) + gift.allocation * qty;
    }
  }

  // 构建 SKU 明细
  const skuDetails = nonGiftSkus.map(sku => {
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
      isGift: false,
      allocatedInventory: allocation,
      productBreakdown,
    };
  });

  // 追加赠品SKU明细
  for (const gift of giftSkus) {
    const productBreakdown = {};
    for (const [p, qty] of Object.entries(gift.comp)) {
      productBreakdown[p] = { qtyPerUnit: qty, totalDemand: gift.allocation * qty };
    }
    skuDetails.push({
      key: gift.key,
      huohao: gift.huohao,
      skuName: gift.skuName,
      cartAddCount: 0,
      isActive: false,
      isGift: true,
      allocatedInventory: gift.allocation,
      productBreakdown,
    });
  }

  return {
    _meta: {
      k: parseFloat(Math.min(globalMinK, 1.0).toFixed(6)), // 最紧约束系数（仅报告参考）
      reserve,
      coldFixed,
      bottleneck: bottleneckProduct.product,
      bottleneckRatio: bottleneckProduct.ratio === Infinity ? null : parseFloat(bottleneckProduct.ratio.toFixed(4)),
      activeCount: activeSkus.length,
      coldCount: coldSkus.length,
      giftCount: giftSkus.length,
      warnings,
    },
    skuDetails,
    totalDemand,
    available: avail,
    remaining: intRem,
  };
}

module.exports = { allocate };
