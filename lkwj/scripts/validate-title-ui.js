const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const titlePath = path.join(__dirname, '..', 'data', 'titles.json');
const titles = fs.existsSync(titlePath)
  ? JSON.parse(fs.readFileSync(titlePath, 'utf8'))
  : null;

const checks = [
  ['server defines title data file', server.includes('TITLES_FILE')],
  ['server exposes api titles endpoint', server.includes("url.pathname === '/api/titles'")],
  ['game-data includes titles and progress', server.includes('titles') && server.includes('title_progress')],
  ['titles tab routes to dedicated renderer', /if \(name === 'titles'\) \{ renderTitlesTab\(\); return; \}/.test(html)],
  ['renderTitlesTab exists', /function\s+renderTitlesTab\s*\(/.test(html)],
  ['renderTitleRow exists', /function\s+renderTitleRow\s*\(/.test(html)],
  ['toggleTitle exists', /async\s+function\s+toggleTitle\s*\(/.test(html)],
  ['title renderer uses gameData.titles', html.includes('gameData?.titles')],
  ['title progress is persisted separately', html.includes('title_progress')],
  ['title row shows obtain method', html.includes('obtainMethod') && html.includes('获取方式')],
  ['title row formats upper and lower as one title', html.includes('formatTitleName') && html.includes(' · ')],
  ['title row no longer labels upper and lower parts separately', !html.includes('上半段') && !html.includes('下半段')],
  ['title data file exists and is an array', Array.isArray(titles)],
  ['title data has sample title with method', Array.isArray(titles) && titles.some(i => i.id === 'title_1' && i.upper === '百分之零' && i.lower === '魔法师' && Object.prototype.hasOwnProperty.call(i, 'obtainMethod'))],
  ['collections has title_progress object', collections.title_progress && typeof collections.title_progress === 'object' && !Array.isArray(collections.title_progress)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
