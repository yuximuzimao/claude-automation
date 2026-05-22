#!/usr/bin/env node
/**
 * fix-shiny-and-chains.js
 * 1. 沿进化链传播 tags.shiny（核心 bug 修复）
 * 2. 根据 wiki 数据修正 limitedTime
 * 3. 补充 S2 精灵进化链
 */

const fs = require('fs');
const path = require('path');

const PETS_FILE = path.join(__dirname, '..', 'data', 'pets.json');
const CHAINS_FILE = path.join(__dirname, '..', 'data', 'evolution-chains.json');

const pets = JSON.parse(fs.readFileSync(PETS_FILE, 'utf8'));
const chains = JSON.parse(fs.readFileSync(CHAINS_FILE, 'utf8'));

// ====== Step 1: Propagate tags.shiny through evolution chains ======
let propagated = 0;

chains.forEach(chain => {
  // Check if any node in this chain has tags.shiny
  const hasShiny = Object.keys(chain.nodes).some(nodeKey => {
    return pets[nodeKey]?.tags?.shiny;
  });

  if (!hasShiny) return;

  // Propagate tags.shiny to ALL nodes in the chain
  Object.keys(chain.nodes).forEach(nodeKey => {
    if (!pets[nodeKey]) return;
    if (!pets[nodeKey].tags) pets[nodeKey].tags = {};
    if (!pets[nodeKey].tags.shiny) {
      pets[nodeKey].tags.shiny = { tagName: '异色' };
      propagated++;
    }
  });
});

console.log(`Step 1: Propagated tags.shiny to ${propagated} evolved forms`);

// ====== Step 2: Name → petKey mapping ======
const nameToKey = {};
Object.entries(pets).forEach(([k, v]) => { nameToKey[v.name] = k; });

// ====== Step 3: Fix S1 limitedTime based on wiki research ======
// S1 had ~19 shiny pets: 8 regular, 8 season-limited, 2 BP, 1 event
let s1Fixed = 0;

const s1SeasonLimited = [
  '柴渣虫', '清渣虫',         // 燃薪虫 chain (柴渣虫→清渣虫; wiki says 燃薪虫=清渣虫)
  '双灯鱼', '利灯鱼',         // 双灯鱼→利灯鱼
  '月牙雪熊',
  '粉粉星', '小皮球',         // 粉粉星→小皮球
  '空空颅', '夜宿颅', '夜枭', // 空空颅→夜宿颅→夜枭
  '晴光嗡嗡', '窃光蚊',       // 晴光嗡嗡→窃光蚊
  '贝瑟', '贝加尔', '贝古斯', // 贝瑟→贝加尔→贝古斯
  '粉星仔', '粉耳星兔', '落陨星兔', // 粉星仔→粉耳星兔|落陨星兔
];

const s1BattlePass = [
  '绒绒', '小绒茧',           // → 绒仙子 (wiki: 光纤兽→疾光千兽, 绒绒→小绒茧→绒仙子)
  '光纤兽',                    // → 疾光千兽
];

const s1Event = ['雅丹鬃'];

// S1 regular (always available): the rest of the S1 19
// 格兰种子 chain, 奇丽草 chain, 治愈兔 chain, etc.
const s1RegularChains = [
  // 格兰种子→格兰花→格兰球 (格兰球 is the final shiny form)
  'pet_274', // base of chain containing 格兰种子
  // 奇丽草→奇丽叶→奇丽花
  'pet_41',
  // 治愈兔→红丝绒 (wiki: 红绒十字)
  'pet_255',
  // 呼呼猪→獠牙猪
  'pet_137',
  // 大耳帽兜→帽兜娃娃→雪影娃娃
  'pet_142',
  // 拉特→酷拉
  'pet_205',
  // 恶魔狼 (standalone, already has 第一赛季 from old data)
  // Actually 恶魔狼 was classified as "常驻" in wiki
  // 机械方→多彩方方→立方人
  'pet_262', // base of chain containing 机械方 (wiki says 机械方方)
];

function setShinySeason(petKey, limitedTime) {
  if (!pets[petKey]?.tags?.shiny) return false;
  const old = pets[petKey].tags.shiny.limitedTime;
  pets[petKey].tags.shiny.limitedTime = limitedTime;
  if (old !== limitedTime) {
    return true;
  }
  return false;
}

// Apply S1 season-limited
s1SeasonLimited.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '第一赛季')) s1Fixed++;
});

// Apply S1 BP
s1BattlePass.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '通行证')) s1Fixed++;
});

// Apply S1 event
s1Event.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '活动')) s1Fixed++;
});

// Apply S1 regular (these were incorrectly marked as 第一赛季 by old data migration)
s1RegularChains.forEach(baseKey => {
  const chain = chains.find(c => c.baseSpeciesId === baseKey);
  if (chain) {
    Object.keys(chain.nodes).forEach(nodeKey => {
      if (setShinySeason(nodeKey, '可获取')) s1Fixed++;
    });
  } else {
    if (setShinySeason(baseKey, '可获取')) s1Fixed++;
  }
});

// 恶魔狼 should be 可获取 per wiki (not 第一赛季 as old data said)
if (setShinySeason('pet_131', '可获取')) s1Fixed++;

console.log(`Step 3: Fixed S1 season data for ${s1Fixed} pet entries`);

// ====== Step 4: S2 limitedTime ======
let s2Fixed = 0;

const s2SeasonLimited = [
  '小鼓象', '巨鼓象',
  '猴麦仔', '音碟吼',
  '炫光迪迪', '霹雳迪迪',
  '烟花团', '烟花伯爵',
  '咕咕帽', '咕德帽帽',
  '牵线木偶', '帅帅魔偶',
  '小丑豆豆', '小丑公爵',
  '狐脸擦擦',
  '加油海葵', '花海葵',
];

const s2Regular = [
  '音速犬', '护主犬',
  '伊贝儿',
  '恶魔叮', '叮叮恶魔',
  '菊花梨',
  '公平鸽',
  '灵狐', '权杖-II', '权杖-V',
  '小夜',
  '小独角兽',
];

const s2BattlePass = ['爆焰喷喷', '雪怪'];

s2SeasonLimited.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '第二赛季')) s2Fixed++;
});

s2Regular.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '可获取')) s2Fixed++;
});

s2BattlePass.forEach(name => {
  const key = nameToKey[name];
  if (key && setShinySeason(key, '通行证')) s2Fixed++;
});

console.log(`Step 4: Fixed S2 season data for ${s2Fixed} pet entries`);

// ====== Step 5: Add S2 evolution chains ======
// S2 new sprites (347-355) have empty acquires. Add their evolution chains.

const s2Chains = [
  {
    chainId: 163,
    baseSpeciesId: 'pet_348', // 小丑豆豆
    nodes: {
      'pet_348': { evolvesTo: [{ toSpeciesId: 'pet_xiaochougongjue', condition: { type: 'level', level: 32, note: '需夜晚时段(19:00-5:00)' } }] },
      'pet_xiaochougongjue': { evolvesTo: [] },
    },
    _s2_note: '进化目标 小丑公爵 尚未录入 pets.json',
  },
  {
    chainId: 164,
    baseSpeciesId: 'pet_349', // 加油海葵
    nodes: {
      'pet_349': { evolvesTo: [{ toSpeciesId: 'pet_huahaikui', condition: { type: 'level', level: 28 } }] },
      'pet_huahaikui': { evolvesTo: [] },
    },
    _s2_note: '进化目标 花海葵 尚未录入 pets.json',
  },
  {
    chainId: 165,
    baseSpeciesId: 'pet_350', // 烟花团
    nodes: {
      'pet_350': { evolvesTo: [{ toSpeciesId: 'pet_yanhuabojue', condition: { type: 'level', level: 30 } }] },
      'pet_yanhuabojue': { evolvesTo: [] },
    },
    _s2_note: '进化目标 烟花伯爵 尚未录入 pets.json',
  },
  {
    chainId: 166,
    baseSpeciesId: 'pet_351', // 猴麦仔
    nodes: {
      'pet_351': { evolvesTo: [{ toSpeciesId: 'pet_yindiehou', condition: { type: 'level', level: 30 } }] },
      'pet_yindiehou': { evolvesTo: [] },
    },
    _s2_note: '进化目标 音碟吼 尚未录入 pets.json',
  },
  {
    chainId: 167,
    baseSpeciesId: 'pet_352', // 咕咕帽
    nodes: {
      'pet_352': { evolvesTo: [{ toSpeciesId: 'pet_gudemaomao', condition: { type: 'level', level: 28 } }] },
      'pet_gudemaomao': { evolvesTo: [] },
    },
    _s2_note: '进化目标 咕德帽帽 尚未录入 pets.json',
  },
  {
    chainId: 168,
    baseSpeciesId: 'pet_353', // 牵线木偶
    nodes: {
      'pet_353': { evolvesTo: [{ toSpeciesId: 'pet_shuaishuaimoou', condition: { type: 'level', level: 30 } }] },
      'pet_shuaishuaimoou': { evolvesTo: [] },
    },
    _s2_note: '进化目标 帅帅魔偶 尚未录入 pets.json',
  },
  {
    chainId: 169,
    baseSpeciesId: 'pet_354', // 炫光迪迪
    nodes: {
      'pet_354': { evolvesTo: [{ toSpeciesId: 'pet_pilididi', condition: { type: 'level', level: 30 } }] },
      'pet_pilididi': { evolvesTo: [] },
    },
    _s2_note: '进化目标 霹雳迪迪 尚未录入 pets.json',
  },
  {
    chainId: 170,
    baseSpeciesId: 'pet_355', // 小鼓象
    nodes: {
      'pet_355': { evolvesTo: [{ toSpeciesId: 'pet_juguxiang', condition: { type: 'level', level: 32 } }] },
      'pet_juguxiang': { evolvesTo: [] },
    },
    _s2_note: '进化目标 巨鼓象 尚未录入 pets.json',
  },
  {
    chainId: 171,
    baseSpeciesId: 'pet_347', // 暮星辰
    nodes: {
      'pet_347': { evolvesTo: [] },
    },
    _s2_note: '进化链 幽星光→曜星光→暮星辰，前两形态尚未录入 pets.json',
  },
];

// Remove existing standalone chains for these sprites (they should have chainIds 155-163)
const existingIds = new Set(s2Chains.map(c => c.chainId));
const filteredChains = chains.filter(c => {
  return !c.baseSpeciesId || !s2Chains.some(sc => sc.baseSpeciesId === c.baseSpeciesId && c.nodes[c.baseSpeciesId]?.evolvesTo?.length === 0);
});

// Actually, let's just replace the chains for the S2 sprites
const s2BaseKeys = s2Chains.map(c => c.baseSpeciesId);
const keepChains = chains.filter(c => !s2BaseKeys.includes(c.baseSpeciesId));

const allChains = [...keepChains, ...s2Chains].sort((a, b) => a.chainId - b.chainId);

fs.writeFileSync(CHAINS_FILE, JSON.stringify(allChains, null, 2), 'utf8');
console.log(`Step 5: Added ${s2Chains.length} S2 evolution chains (${keepChains.length} existing + ${s2Chains.length} new = ${allChains.length} total)`);

// ====== Step 6: Fix 燃薪虫 name in pets.json ======
// 燃薪虫 is the wiki name for 清渣虫 (柴渣虫's evolution)
// Actually, 燃薪虫 is listed as the evolution of 柴渣虫, same as 清渣虫
// The old items[] had "燃薪虫" - this is likely an alternate name for 清渣虫
// Let's add a note but keep the current name
const qingzhachong = nameToKey['清渣虫'];
if (qingzhachong) {
  if (!pets[qingzhachong].notes) pets[qingzhachong].notes = '';
  if (!pets[qingzhachong].notes.includes('燃薪虫')) {
    pets[qingzhachong].notes = (pets[qingzhachong].notes + ' 别名：燃薪虫').trim();
    console.log(`Step 6: Added 燃薪虫 alias to ${qingzhachong} (清渣虫)`);
  }
}

// ====== Write outputs ======
fs.writeFileSync(PETS_FILE, JSON.stringify(pets, null, 2), 'utf8');

// ====== Final stats ======
console.log('\n=== fix-shiny-and-chains.js ===');
const totalShiny = Object.values(pets).filter(p => p.tags?.shiny).length;
const withSeason = Object.values(pets).filter(p => p.tags?.shiny?.limitedTime).length;
const withoutSeason = totalShiny - withSeason;

// Season distribution
const seasonDist = {};
Object.values(pets).forEach(p => {
  if (p.tags?.shiny?.limitedTime) {
    const lt = p.tags.shiny.limitedTime;
    seasonDist[lt] = (seasonDist[lt] || 0) + 1;
  }
});

console.log(`Total shiny: ${totalShiny} (${withSeason} with season, ${withoutSeason} without)`);
Object.entries(seasonDist).sort((a,b) => b[1]-a[1]).forEach(([s,c]) => {
  console.log(`  ${s}: ${c}`);
});
console.log(`Done.`);
