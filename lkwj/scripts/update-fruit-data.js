#!/usr/bin/env node
// update-fruit-data.js
// 从 _fruit_excel_dump.txt 读取果实进度数据，更新 pets.json 的 fruit 字段
// 执行: node scripts/update-fruit-data.js

const fs = require('fs');
const path = require('path');

const petsPath = path.join(__dirname, '../data/pets.json');
const dumpPath = path.join(__dirname, '../data/_fruit_excel_dump.txt');

const pets = JSON.parse(fs.readFileSync(petsPath, 'utf8'));

// 7 个无果实家族（Excel 标注无果实，不录入 fruit 字段）
const NO_FRUIT_TYPES = new Set(['传说精灵', '特殊奇遇', '开局必送', '呱呱上学记']);

// 果实获取方式映射（Excel C 列 → obtainType 6 分类）
function mapObtainType(excelC) {
  if (excelC === '捕捉20只精灵') return '课题任务';
  if (excelC.startsWith('智慧树苗')) return '智慧树苗';
  if (excelC === '一代御三家' || excelC === '二代御三家') return '剧情任务';
  if (excelC === '通行证契约礼券') return '通行证契约礼券';
  if (excelC.startsWith('赛季作业')) return '赛季作业';
  // 洛克筑梦师、官网下载、火红迎新
  return '限时活动';
}

// 互斥组配置
const EXCLUSIVE_GROUPS = {
  // 一代御三家三选一（最终形态 pet_4/7/10）
  pet_4: 'starter_gen1',
  pet_7: 'starter_gen1',
  pet_10: 'starter_gen1',
  // 二代御三家三选一（最终形态 pet_155/158/161）
  pet_155: 'starter_gen2',
  pet_158: 'starter_gen2',
  pet_161: 'starter_gen2',
  // 通行证 S1 二选一（最终形态 pet_309/312）
  pet_309: 'pass_s1',
  pet_312: 'pass_s1',
  // 通行证 S2 二选一（最终形态 pet_355/357）
  pet_355: 'pass_s2',
  pet_357: 'pass_s2',
};

// 建精灵名 → petId 映射
const nameToId = {};
for (const [k, v] of Object.entries(pets)) {
  nameToId[v.name] = k;
}

// 解析编号范围，返回 [firstNum, lastNum]
function parseRange(numStr) {
  // 处理 typo: N.239-N,241 → 239,241; N.367-368 → 367,368
  const cleaned = numStr.replace(/N[.,]/g, '').trim();
  const parts = cleaned.split('-').map(s => parseInt(s.replace(/[^0-9]/g, '')));
  const first = parts[0];
  const last = parts[parts.length - 1] || first;
  return [first, last];
}

// 读 dump 文件
// 注意：部分备注含换行符，需先把跨行内容合并
const rawLines = fs.readFileSync(dumpPath, 'utf8').split('\n');
// 合并逻辑：正常行以 "数字|" 开头，不符合则追加到上一行
const mergedLines = [];
for (const raw of rawLines) {
  if (/^\d+\|/.test(raw)) {
    mergedLines.push(raw);
  } else if (mergedLines.length > 0) {
    // 追加到上一行（备注中的换行符替换为空格）
    mergedLines[mergedLines.length - 1] += ' ' + raw;
  }
}
const dataLines = mergedLines.slice(1); // 跳过表头

let added = 0, updated = 0, skipped = 0, errors = [];

for (const line of dataLines) {
  const parts = line.split('|');
  const [rowNum, numRange, family, obtainTypeRaw, remark] = parts;

  // 无果实类型跳过
  if (NO_FRUIT_TYPES.has(obtainTypeRaw)) {
    skipped++;
    continue;
  }

  const [firstNum, lastNum] = parseRange(numRange);
  const obtainType = mapObtainType(obtainTypeRaw);

  // obtainMethod：优先 D 列（备注），备注为空则用 C 列
  let obtainMethod = (remark && remark.trim()) ? remark.trim() : obtainTypeRaw;

  // 确定果实归属 petId
  let fruitPetId = null;

  if (obtainTypeRaw === '捕捉20只精灵' && remark) {
    // 从备注提取精灵名：捕捉20只{精灵名}
    const match = remark.match(/捕捉\d+只(.+)/);
    if (match) {
      const targetName = match[1].trim();
      fruitPetId = nameToId[targetName];
      if (!fruitPetId) {
        // 备注精灵名与 pets.json 不一致（Excel 笔误），fallback 到编号范围最后一个
        const candidateId = 'pet_' + lastNum;
        if (pets[candidateId]) {
          fruitPetId = candidateId;
          // 用正确精灵名修正 obtainMethod
          const correctName = pets[candidateId].name;
          obtainMethod = remark.replace(targetName, correctName);
          console.log(`  修正备注 [${numRange}]: "${targetName}" → "${correctName}"`);
        } else {
          errors.push(`[${numRange}] 未找到精灵名 "${targetName}"，fallback pet_${lastNum} 也不存在`);
        }
      }
    }
  }

  // 非捕捉类型：用编号范围最后一个
  if (!fruitPetId) {
    const candidateId = 'pet_' + lastNum;
    if (pets[candidateId]) {
      fruitPetId = candidateId;
    } else {
      // fallback 到第一个
      const firstId = 'pet_' + firstNum;
      if (pets[firstId]) {
        fruitPetId = firstId;
      } else {
        errors.push(`[${numRange}] 找不到对应精灵（pet_${lastNum} / pet_${firstNum}）`);
        continue;
      }
    }
  }

  const pet = pets[fruitPetId];
  if (!pet) {
    errors.push(`[${numRange}] pet ${fruitPetId} 不存在`);
    continue;
  }

  // 构建果实名
  const fruitName = pet.fruit?.name || (pet.name + '的果实');

  // 构建新 fruit 对象
  const newFruit = {
    name: fruitName,
    acquired: pet.fruit?.acquired || false,
    obtainMethod,
    obtainType,
  };

  // 加互斥组（如有）
  if (EXCLUSIVE_GROUPS[fruitPetId]) {
    newFruit.exclusiveGroup = EXCLUSIVE_GROUPS[fruitPetId];
  }

  const existed = !!pet.fruit;
  pet.fruit = newFruit;

  if (existed) updated++;
  else added++;
}

// 补全：分叉进化的"另一个终点"从已有数据中继承
// 场景：乖乖鹄家族(88-90/91), 毛头小蛛家族(296-297/298)
// Excel 只记录了一个分支，另一个分支在进化链中也是终点，应有相同的 obtainType
// 策略：找同一进化链中有 fruit 字段的终点，把信息拷贝给无 obtainType 的同链终点
const chains = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/evolution-chains.json'), 'utf8'));

for (const chain of chains) {
  const nodeIds = Object.keys(chain.nodes);
  // 找此链所有进化终点
  const endpoints = nodeIds.filter(id => !chain.nodes[id].evolvesTo || chain.nodes[id].evolvesTo.length === 0);
  if (endpoints.length < 2) continue;

  // 找有完整 fruit 信息的终点和缺信息的终点
  const withInfo = endpoints.filter(id => pets[id]?.fruit?.obtainType);
  const withoutInfo = endpoints.filter(id => pets[id]?.fruit && !pets[id]?.fruit?.obtainType);

  if (withInfo.length > 0 && withoutInfo.length > 0) {
    const donor = pets[withInfo[0]].fruit;
    for (const id of withoutInfo) {
      const pet = pets[id];
      pet.fruit = {
        name: pet.fruit.name,
        acquired: pet.fruit.acquired,
        obtainMethod: donor.obtainMethod,
        obtainType: donor.obtainType,
      };
      if (donor.exclusiveGroup) pet.fruit.exclusiveGroup = donor.exclusiveGroup;
      updated++;
      console.log(`  继承果实信息: ${id} ${pet.name} ← ${withInfo[0]}`);
    }
  }
}

// 保存
fs.writeFileSync(petsPath, JSON.stringify(pets, null, 2), 'utf8');

console.log(`\n✅ 完成`);
console.log(`  新增 fruit 字段: ${added}`);
console.log(`  更新 fruit 字段: ${updated}`);
console.log(`  跳过（无果实）: ${skipped}`);

if (errors.length > 0) {
  console.log(`\n⚠️  错误 (${errors.length}):`);
  errors.forEach(e => console.log('  ', e));
}

// 验证
const withFruit = Object.entries(pets).filter(([k, v]) => v.fruit);
const withMethod = withFruit.filter(([k, v]) => v.fruit.obtainMethod);
const byType = {};
withFruit.forEach(([k, v]) => {
  const t = v.fruit.obtainType || 'none';
  byType[t] = (byType[t] || 0) + 1;
});

console.log(`\n📊 验证`);
console.log(`  有 fruit 字段: ${withFruit.length}`);
console.log(`  有 obtainMethod: ${withMethod.length}`);
console.log(`  按 obtainType:`, JSON.stringify(byType));

const noFruitCheck = ['pet_1', 'pet_150', 'pet_293', 'pet_348', 'pet_313', 'pet_317', 'pet_375'];
const wrongNoFruit = noFruitCheck.filter(id => pets[id]?.fruit);
if (wrongNoFruit.length > 0) {
  console.log(`  ⚠️  以下应无果实但有 fruit 字段:`, wrongNoFruit);
} else {
  console.log(`  7 个无果实家族确认无 fruit 字段 ✓`);
}

const exclusiveCount = withFruit.filter(([k, v]) => v.fruit.exclusiveGroup).length;
console.log(`  有互斥组: ${exclusiveCount}`);
