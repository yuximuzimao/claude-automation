const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const furniturePath = path.join(__dirname, '..', 'data', 'furniture.json');
const furniture = fs.existsSync(furniturePath)
  ? JSON.parse(fs.readFileSync(furniturePath, 'utf8'))
  : null;
const furnitureTabBody = html.slice(
  html.indexOf('function renderFurnitureTab'),
  html.indexOf('function renderFurnitureRow')
);

const checks = [
  ['server defines furniture data file', server.includes('FURNITURE_FILE')],
  ['server exposes api furniture endpoint', server.includes("url.pathname === '/api/furniture'")],
  ['game-data includes furniture definitions', server.includes('furniture') && server.includes('furniture_progress')],
  ['furniture tab routes to dedicated renderer', /if \(name === 'furniture'\) \{ renderFurnitureTab\(\); return; \}/.test(html)],
  ['renderFurnitureTab exists', /function\s+renderFurnitureTab\s*\(/.test(html)],
  ['renderFurnitureRow exists', /function\s+renderFurnitureRow\s*\(/.test(html)],
  ['toggleFurniture exists', /async\s+function\s+toggleFurniture\s*\(/.test(html)],
  ['furniture renderer uses gameData.furniture', html.includes('gameData?.furniture')],
  ['furniture progress is persisted separately', html.includes('furniture_progress')],
  ['furniture tab has status filter controls', html.includes('furnitureStatusFilter') && html.includes('setFurnitureStatusFilter')],
  ['furniture stats no longer show comfort totals', !furnitureTabBody.includes('comfortTotal') && !furnitureTabBody.includes('comfortOwned')],
  ['furniture stats no longer show total inspiration', !furnitureTabBody.includes('inspirationTotal') && !furnitureTabBody.includes('inspirationOwned')],
  ['furniture renderer shows remaining inspiration', html.includes('remainingInspiration') && html.includes('还差')],
  ['furniture row does not show source controls', !/renderFurnitureRow[\s\S]*source_url/.test(html) && !/renderFurnitureRow[\s\S]*openModal/.test(html)],
  ['furniture data file exists and is an array', Array.isArray(furniture)],
  ['furniture data has sample definition', Array.isArray(furniture) && furniture.some(i => i.id === 'furniture_1' && i.name === '木质衣柜' && i.comfort === 300 && i.inspiration === 1200)],
  ['collections has furniture_progress object', collections.furniture_progress && typeof collections.furniture_progress === 'object' && !Array.isArray(collections.furniture_progress)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
