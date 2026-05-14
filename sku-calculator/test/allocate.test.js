/**
 * allocate.js 单元测试
 * 运行: node test/allocate.test.js
 */

const { allocate } = require('../lib/allocate');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  ✓ ${msg}`);
    passed++;
  } else {
    console.error(`  ✗ ${msg}`);
    failed++;
  }
}

function assertEq(a, b, msg) {
  if (a === b) {
    console.log(`  ✓ ${msg} (= ${b})`);
    passed++;
  } else {
    console.error(`  ✗ ${msg}: expected ${b}, got ${a}`);
    failed++;
  }
}

// ─────────────────────────────────────────
// 测试1: 库存充足 → 建议库存≥加购数，充分利用库存
// ─────────────────────────────────────────
console.log('\n[Test 1] 库存充足 → 建议库存≥加购数，充分利用库存');
{
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 500 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 300 },
  ];
  const components = {
    A: { components: { 黑茶: 9 } },
    B: { components: { 黑茶: 3, 益生菌: 6 } },
  };
  const stock = { 黑茶: 100000, 益生菌: 50000 };

  const result = allocate(skus, components, stock, { reserve: 0.2 });
  const aInv = result.skuDetails.find(s => s.key === 'A').allocatedInventory;
  const bInv = result.skuDetails.find(s => s.key === 'B').allocatedInventory;

  assert(aInv >= 500, `A 建议库存(${aInv}) ≥ 加购数(500)`);
  assert(bInv >= 300, `B 建议库存(${bInv}) ≥ 加购数(300)`);
  const ratio = aInv / bInv;
  assert(Math.abs(ratio - 500 / 300) < 0.2, `A:B 比例约5:3（实际 ${ratio.toFixed(2)}）`);
  const blackTeaDemand = result.totalDemand['黑茶'] || 0;
  assert(blackTeaDemand <= 80000, `黑茶总消耗(${blackTeaDemand}) ≤ 可用量(80000)`);
}

// ─────────────────────────────────────────
// 测试2: 库存不足时按比例缩减
// ─────────────────────────────────────────
console.log('\n[Test 2] 库存不足 → 等比缩减');
{
  // A: 加购500, 用黑茶9; B: 加购300, 用黑茶3
  // 黑茶可用 = 3600*0.8=2880
  // baseDemand_黑茶 = 500*9+300*3=5400
  // k = 2880/5400 = 0.5333
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 500 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 300 },
  ];
  const components = {
    A: { components: { 黑茶: 9 } },
    B: { components: { 黑茶: 3 } },
  };
  const stock = { 黑茶: 3600 };
  const result = allocate(skus, components, stock, { reserve: 0.2 });

  assert(result._meta.k < 1, 'k < 1（库存不足）');
  assert(result._meta.k > 0, 'k > 0（有库存）');

  const totalBlackTea = result.totalDemand['黑茶'] || 0;
  assert(totalBlackTea <= 2880, `总需求黑茶(${totalBlackTea}) ≤ 可用量(2880)`);

  // 比例验证：A和B的库存比应≈500/300=5/3
  const aInv = result.skuDetails.find(s => s.key === 'A').allocatedInventory;
  const bInv = result.skuDetails.find(s => s.key === 'B').allocatedInventory;
  assert(bInv > 0, 'B 库存 > 0');
  const ratio = aInv / bInv;
  assert(Math.abs(ratio - 500/300) < 0.2, `比例约为5:3（实际 ${ratio.toFixed(2)}）`);
}

// ─────────────────────────────────────────
// 测试3: 多瓶颈交叉（关键测试）
// ─────────────────────────────────────────
console.log('\n[Test 3] 多瓶颈交叉 —— A用黑茶, B用益生菌, C用黑茶+益生菌');
{
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 400 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 300 },
    { key: 'C', huohao: 'c', skuName: 'C', cartAddCount: 200 },
  ];
  const components = {
    A: { components: { 黑茶: 9 } },
    B: { components: { 益生菌: 6 } },
    C: { components: { 黑茶: 3, 益生菌: 4 } },
  };
  // 黑茶可用=4000, 益生菌可用=2400
  // 黑茶 baseDemand = 400*9+200*3=4200, ratio=4000/4200=0.952
  // 益生菌 baseDemand = 300*6+200*4=2600, ratio=2400/2600=0.923  ← 瓶颈
  // k = 0.923 (取 min，不超过1)
  const stock = { 黑茶: 5000, 益生菌: 3000 };
  const result = allocate(skus, components, stock, { reserve: 0.2 });

  // 验证约束：所有单品总需求 ≤ 可用量
  const blackTeaDemand = result.totalDemand['黑茶'] || 0;
  const probDemand = result.totalDemand['益生菌'] || 0;
  assert(blackTeaDemand <= 4000, `黑茶总需求(${blackTeaDemand}) ≤ 4000`);
  assert(probDemand <= 2400, `益生菌总需求(${probDemand}) ≤ 2400`);

  // 验证比例：A:B:C 应接近 400:300:200
  const aInv = result.skuDetails.find(s => s.key === 'A').allocatedInventory;
  const bInv = result.skuDetails.find(s => s.key === 'B').allocatedInventory;
  const cInv = result.skuDetails.find(s => s.key === 'C').allocatedInventory;
  assert(aInv > 0 && bInv > 0 && cInv > 0, 'A/B/C 均有库存');
  const ratioAB = aInv / bInv;
  const ratioBC = bInv / cInv;
  assert(Math.abs(ratioAB - 400/300) < 0.2, `A:B 比例约4:3（实际 ${ratioAB.toFixed(2)}）`);
  assert(Math.abs(ratioBC - 300/200) < 0.2, `B:C 比例约3:2（实际 ${ratioBC.toFixed(2)}）`);
}

// ─────────────────────────────────────────
// 测试4: 零库存单品
// ─────────────────────────────────────────
console.log('\n[Test 4] 某单品库存=0 → 相关 SKU 库存=0');
{
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 100 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 100 },
  ];
  const components = {
    A: { components: { 黑茶: 1 } },          // 只用黑茶
    B: { components: { 黑茶: 1, 益生菌: 1 } }, // 用黑茶+益生菌
  };
  const stock = { 黑茶: 10000, 益生菌: 0 }; // 益生菌=0

  const result = allocate(skus, components, stock, { reserve: 0 });
  const aInv = result.skuDetails.find(s => s.key === 'A').allocatedInventory;
  const bInv = result.skuDetails.find(s => s.key === 'B').allocatedInventory;

  assertEq(bInv, 0, 'B（使用益生菌）库存=0');
  assert(aInv > 0, 'A（只用黑茶）有库存');
}

// ─────────────────────────────────────────
// 测试5: 冷热分离——零加购 SKU 不稀释热门
// ─────────────────────────────────────────
console.log('\n[Test 5] 冷热分离——零加购不稀释热门');
{
  const skus = [
    { key: 'hot', huohao: 'h', skuName: 'hot', cartAddCount: 500 },
    { key: 'cold1', huohao: 'c', skuName: 'cold1', cartAddCount: 0 },
    { key: 'cold2', huohao: 'c', skuName: 'cold2', cartAddCount: 0 },
  ];
  const components = {
    hot:   { components: { 黑茶: 1 } },
    cold1: { components: { 黑茶: 1 } },
    cold2: { components: { 黑茶: 1 } },
  };
  const stock = { 黑茶: 625 }; // 可用=500，刚好满足热门SKU

  const result = allocate(skus, components, stock, { reserve: 0.2, coldFixed: 5 });
  const hotInv = result.skuDetails.find(s => s.key === 'hot').allocatedInventory;

  assertEq(hotInv, 500, '热门 SKU 获得全量 500 库存（不被冷门稀释）');
  assert(result.totalDemand['黑茶'] <= 500, `总需求黑茶 ≤ 500`);
}

// ─────────────────────────────────────────
// 测试6: LRM 回填不超卖
// ─────────────────────────────────────────
console.log('\n[Test 6] LRM 回填不造成超卖');
{
  // 制造场景：多个 SKU floor 后各有余数，回填时检查组合约束
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 3 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 3 },
    { key: 'C', huohao: 'c', skuName: 'C', cartAddCount: 3 },
  ];
  const components = {
    A: { components: { 稀缺品: 5 } },
    B: { components: { 稀缺品: 5 } },
    C: { components: { 稀缺品: 5 } },
  };
  // 稀缺品可用=11，k=11/45≈0.244，各floor=0，11只能让2个SKU+1
  const stock = { 稀缺品: 14 }; // 可用11
  const result = allocate(skus, components, stock, { reserve: 0.2, coldFixed: 0 });

  const totalDemand = result.totalDemand['稀缺品'] || 0;
  assert(totalDemand <= 11, `总需求稀缺品(${totalDemand}) ≤ 可用量(11)，LRM 不超卖`);
}

// ─────────────────────────────────────────
// 测试7: 全部无加购 → 走保底
// ─────────────────────────────────────────
console.log('\n[Test 7] 全部无加购 → 走保底分配');
{
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 0 },
    { key: 'B', huohao: 'b', skuName: 'B', cartAddCount: 0 },
  ];
  const components = {
    A: { components: { 黑茶: 1 } },
    B: { components: { 黑茶: 1 } },
  };
  const stock = { 黑茶: 10000 };
  const result = allocate(skus, components, stock, { reserve: 0.2, coldFixed: 5 });

  assertEq(result._meta.k, 1.0, 'k = 1.0（无 active SKU）');
  assertEq(result.skuDetails.find(s => s.key === 'A').allocatedInventory, 5, 'A 保底 = 5');
  assertEq(result.skuDetails.find(s => s.key === 'B').allocatedInventory, 5, 'B 保底 = 5');
}

// ─────────────────────────────────────────
// 测试8: 回归 — 稀缺单品不连坐无关SKU
// 验证：旧算法（全局 k）此测试必然失败；新算法必须通过
// ─────────────────────────────────────────
console.log('\n[Test 8] 回归：稀缺单品不连坐无关 SKU，充分利用库存');
{
  // 场景：完全还原实际数据特征
  //   SKU_普通黑茶：cart=100，只用 黑茶×1（黑茶库存充足）
  //   SKU_含保温杯：cart=50，  用 黑茶×9 + 保温杯×1（保温杯极少）
  // 黑茶: stock=20000, 可用=16000
  // 保温杯: stock=14,  可用=11.2
  //
  // 旧算法（全局 k）：
  //   baseDemand[保温杯] = 50×1 = 50，k_保温杯 = 11.2/50 = 0.224
  //   全局 k = 0.224 → 普通黑茶 inv = floor(100×0.224) = 22 ← 错！
  //
  // 新算法（迭代锁定）：
  //   第1轮 D[黑茶]=100×1+50×9=550, D[保温杯]=50×1=50
  //   ratio[黑茶]=16000/550=29.1, ratio[保温杯]=11.2/50=0.224 ← 先耗尽
  //   t=0.224，锁定 SKU_含保温杯：invFloat=50×0.224=11.2
  //   R[黑茶] = 16000 - 11.2×9 = 15899.2
  //   第2轮 S={SKU_普通黑茶}, D[黑茶]=100, ratio=15899.2/100=158.99
  //   t=158.99，invFloat[普通黑茶]=100×158.99=15899 → inv≈15899 ← 远超加购数

  const skus = [
    { key: '普通黑茶', huohao: 'h1', skuName: '黑茶1盒', cartAddCount: 100 },
    { key: '含保温杯', huohao: 'h2', skuName: '黑茶9+保温杯', cartAddCount: 50  },
  ];
  const components = {
    普通黑茶: { components: { 黑茶: 1 } },
    含保温杯: { components: { 黑茶: 9, 保温杯: 1 } },
  };
  const stock = { 黑茶: 20000, 保温杯: 14 };

  const result = allocate(skus, components, stock, { reserve: 0.2 });
  const normalInv  = result.skuDetails.find(s => s.key === '普通黑茶').allocatedInventory;
  const thermoInv  = result.skuDetails.find(s => s.key === '含保温杯').allocatedInventory;
  const blackTotal = result.totalDemand['黑茶'] || 0;
  const thermoTotal = result.totalDemand['保温杯'] || 0;

  // 核心断言：普通黑茶应远超加购数（充分利用黑茶库存）
  assert(normalInv > 100,  `普通黑茶建议库存(${normalInv}) 应远大于加购数100（旧算法=22，此断言会失败）`);
  assert(normalInv > 1000, `普通黑茶建议库存(${normalInv}) 应 >1000（黑茶库存16000远超需求）`);
  // 含保温杯 SKU 受限
  assert(thermoInv < 50,   `含保温杯建议库存(${thermoInv}) 应低于加购数50（受保温杯约束）`);
  // 约束满足
  assert(blackTotal  <= 16000, `黑茶总消耗(${blackTotal}) ≤ 可用量(16000)`);
  assert(thermoTotal <= 12,    `保温杯总消耗(${thermoTotal}) ≤ 可用量(11.2，floor=11)`);
}

// ─────────────────────────────────────────
// 测试9: 回归 — k无上限，库存充足时可远超加购数
// ─────────────────────────────────────────
console.log('\n[Test 9] 回归：库存充足时建议库存应充分利用，不被 k≤1 封顶');
{
  // 场景：单一产品，加购100，库存大量充裕
  // 旧算法（k封顶1）：inv = min(k,1) × cart = 100
  // 新算法（k无上限）：inv ≈ avail / comp = 8000 / 1 = 8000
  const skus = [
    { key: 'A', huohao: 'a', skuName: 'A', cartAddCount: 100 },
  ];
  const components = {
    A: { components: { 黑茶: 1 } },
  };
  const stock = { 黑茶: 10000 }; // 可用 8000，加购仅 100

  const result = allocate(skus, components, stock, { reserve: 0.2 });
  const inv = result.skuDetails.find(s => s.key === 'A').allocatedInventory;
  const blackTotal = result.totalDemand['黑茶'] || 0;

  assert(inv > 100,   `建议库存(${inv}) > 加购数100（不被 k≤1 封顶）`);
  assert(inv >= 7900, `建议库存(${inv}) ≥ 7900（充分利用8000可用库存）`);
  assert(blackTotal <= 8000, `黑茶消耗(${blackTotal}) ≤ 可用量(8000)`);
}

// ─────────────────────────────────────────
// 结果汇总
// ─────────────────────────────────────────
console.log(`\n────────────────────────────`);
console.log(`✓ ${passed} 通过 | ✗ ${failed} 失败`);
if (failed > 0) process.exit(1);
