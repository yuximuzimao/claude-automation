const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const dungeonPath = path.join(__dirname, '..', 'data', 'dungeons.json');
const dungeons = fs.existsSync(dungeonPath)
  ? JSON.parse(fs.readFileSync(dungeonPath, 'utf8'))
  : null;
const dungeonIdsAreSequential = Array.isArray(dungeons) && dungeons.every((item, index) => item.id === `dungeon_${index + 1}`);
const dungeonNamesAreUnique = Array.isArray(dungeons) && new Set(dungeons.map(item => item.name)).size === dungeons.length;
const dungeonRowsAreComplete = Array.isArray(dungeons) && dungeons.every(item =>
  item &&
  typeof item.id === 'string' &&
  typeof item.name === 'string' &&
  item.name.trim() &&
  typeof item.location === 'string' &&
  Array.isArray(item.rewards) &&
  item.resources &&
  typeof item.resources.gameCoins === 'number' &&
  typeof item.resources.spiritEggs === 'number' &&
  item.resources.owlStars &&
  ['blue', 'yellow'].includes(item.resources.owlStars.color) &&
  typeof item.resources.owlStars.amount === 'number' &&
  typeof item.resources.chests === 'number' &&
  typeof item.resources.searchPoints === 'number' &&
  typeof item.resources.prismaticCrystals === 'number' &&
  item.resources.regionalCurrency &&
  typeof item.resources.regionalCurrency.name === 'string' &&
  typeof item.resources.regionalCurrency.amount === 'number'
);
const expectedEggHatchPets = [
  '小夜', '灵狐', '雪娃娃', '小狮鹫', '翡翠水母', '海枝枝', '果冻', '石肤蜥',
  '花怨鳗', '斑斑', '记忆石', '恶魔叮', '哭哭菇', '小箱怪', '矿晶虫',
  '菇菇丁', '绿草精灵', '多多', '螺旋帕帕', '号儿鱼', '呼呼猪',
];
const eggHatches = Array.isArray(dungeons) ? dungeons.flatMap(item => item.eggHatches || []) : [];
const eggHatchRowsAreComplete = eggHatches.every(item =>
  item &&
  typeof item.petName === 'string' &&
  item.petName.trim() &&
  typeof item.nature === 'string' &&
  item.nature.trim() &&
  Array.isArray(item.growths) &&
  item.growths.length > 0 &&
  item.growths.every(growth => typeof growth === 'string' && growth.trim()) &&
  (item.bloodline === undefined || typeof item.bloodline === 'string') &&
  (item.appearance === undefined || typeof item.appearance === 'string') &&
  (item.natureEffect === undefined || typeof item.natureEffect === 'string')
);
const eggHatchPetsAreCovered = expectedEggHatchPets.every(name => eggHatches.some(item => item.petName === name));
const rewardsDoNotDuplicateEggs = Array.isArray(dungeons) && dungeons.every(item =>
  (item.rewards || []).every(reward => !String(reward).includes('蛋'))
);
const sum = key => Array.isArray(dungeons) ? dungeons.reduce((total, item) => total + (key(item.resources || {}) || 0), 0) : 0;
const windDungeons = Array.isArray(dungeons) ? dungeons.filter(item => item.location === '风眠省') : [];
const rockianDungeons = Array.isArray(dungeons) ? dungeons.filter(item => item.location === '洛克里安') : [];
const windTotals = {
  gameCoins: windDungeons.reduce((total, item) => total + item.resources.gameCoins, 0),
  spiritEggs: windDungeons.reduce((total, item) => total + item.resources.spiritEggs, 0),
  chests: windDungeons.reduce((total, item) => total + item.resources.chests, 0),
  searchPoints: windDungeons.reduce((total, item) => total + item.resources.searchPoints, 0),
  prismaticCrystals: windDungeons.reduce((total, item) => total + item.resources.prismaticCrystals, 0),
  regionalCurrency: windDungeons.reduce((total, item) => total + item.resources.regionalCurrency.amount, 0),
};
const rockianTotals = {
  gameCoins: rockianDungeons.reduce((total, item) => total + item.resources.gameCoins, 0),
  spiritEggs: rockianDungeons.reduce((total, item) => total + item.resources.spiritEggs, 0),
  chests: rockianDungeons.reduce((total, item) => total + item.resources.chests, 0),
  searchPoints: rockianDungeons.reduce((total, item) => total + item.resources.searchPoints, 0),
  prismaticCrystals: rockianDungeons.reduce((total, item) => total + item.resources.prismaticCrystals, 0),
  regionalCurrency: rockianDungeons.reduce((total, item) => total + item.resources.regionalCurrency.amount, 0),
};

const checks = [
  ['server defines dungeon data file', server.includes('DUNGEONS_FILE')],
  ['server exposes api dungeons endpoint', server.includes("url.pathname === '/api/dungeons'")],
  ['game-data includes dungeons and progress', server.includes('dungeons') && server.includes('dungeon_progress')],
  ['dungeons tab routes to dedicated renderer', /if \(name === 'dungeons'\) \{ renderDungeonsTab\(\); return; \}/.test(html)],
  ['renderDungeonsTab exists', /function\s+renderDungeonsTab\s*\(/.test(html)],
  ['renderDungeonRow exists', /function\s+renderDungeonRow\s*\(/.test(html)],
  ['toggleDungeon exists', /async\s+function\s+toggleDungeon\s*\(/.test(html)],
  ['dungeon renderer uses gameData.dungeons', html.includes('gameData?.dungeons')],
  ['dungeon progress is persisted separately', html.includes('dungeon_progress')],
  ['dungeon row shows rewards and location', html.includes('rewards') && html.includes('特殊掉落') && html.includes('位置')],
  ['dungeon data file exists and is an array', Array.isArray(dungeons)],
  ['dungeon data rows have required fields', dungeonRowsAreComplete],
  ['dungeon rewards do not duplicate egg resources', rewardsDoNotDuplicateEggs],
  ['dungeon ids are sequential', dungeonIdsAreSequential],
  ['dungeon names are unique', dungeonNamesAreUnique],
  ['wind province resource totals match source image', windDungeons.length === 10 && windTotals.gameCoins === 170 && windTotals.spiritEggs === 9 && windTotals.chests === 24 && windTotals.searchPoints === 25 && windTotals.prismaticCrystals === 935 && windTotals.regionalCurrency === 3200],
  ['rockian resource totals match source image', rockianDungeons.length === 16 && rockianTotals.gameCoins === 254 && rockianTotals.spiritEggs === 17 && rockianTotals.chests === 20 && rockianTotals.searchPoints === 11 && rockianTotals.prismaticCrystals === 1665 && rockianTotals.regionalCurrency === 3800],
  ['combined integrable totals match corrected sums', sum(r => r.gameCoins) === 424 && sum(r => r.spiritEggs) === 26 && sum(r => r.chests) === 44 && sum(r => r.searchPoints) === 36 && sum(r => r.prismaticCrystals) === 2600],
  ['dungeon row uses collapsible detail layout', html.includes('expandedDungeon') && html.includes('toggleDungeonExpand') && html.includes('dungeon-detail')],
  ['dungeon row renders aligned fixed resource grid', html.includes('dungeon-resource-grid') && html.includes('dungeon-resource-cell') && html.includes('repeat(7') && html.includes('副本资源')],
  ['collapsed dungeon summary includes all resource and reward types', html.includes('getDungeonResourceCells(item).map') && html.includes('rewards.map') && html.includes('资源：') && html.includes('收获：')],
  ['dungeon egg hatch data is present', eggHatches.length > 0],
  ['dungeon egg hatch rows have required fields', eggHatchRowsAreComplete],
  ['dungeon egg hatch pet names are covered', eggHatchPetsAreCovered],
  ['dungeon row groups egg hatch data by pet', html.includes('groupEggHatchesByPet') && html.includes('dungeon-egg-name') && html.includes('精灵蛋属性')],
  ['dungeon egg hatch rows use aligned fixed cells', html.includes('dungeon-egg-row') && html.includes('dungeon-egg-cell') && html.includes('has-form')],
  ['dungeon egg hatch wording uses bloodline and form, not variant', html.includes('血脉 / 形态') && !html.includes('变体')],
  ['collections has dungeon_progress object', collections.dungeon_progress && typeof collections.dungeon_progress === 'object' && !Array.isArray(collections.dungeon_progress)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
