const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const dungeonPath = path.join(__dirname, '..', 'data', 'dungeons.json');
const dungeons = fs.existsSync(dungeonPath)
  ? JSON.parse(fs.readFileSync(dungeonPath, 'utf8'))
  : null;

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
  ['dungeon row shows rewards and location', html.includes('rewards') && html.includes('副本奖励') && html.includes('位置')],
  ['dungeon data file exists and is an array', Array.isArray(dungeons)],
  ['dungeon data has sample with required fields', Array.isArray(dungeons) && dungeons.some(i => i.id === 'dungeon_1' && i.name && i.location && Array.isArray(i.rewards) && i.rewards.includes('精灵蛋'))],
  ['collections has dungeon_progress object', collections.dungeon_progress && typeof collections.dungeon_progress === 'object' && !Array.isArray(collections.dungeon_progress)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
