const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const clothingPath = path.join(__dirname, '..', 'data', 'clothing.json');
const clothing = fs.existsSync(clothingPath)
  ? JSON.parse(fs.readFileSync(clothingPath, 'utf8'))
  : null;
const sets = clothing?.sets || [];
const pieces = clothing?.pieces || [];
const setSample = sets.find(i => i.name === '熔岩布丁印象');
const setPieceSample = pieces.find(i => i.pieceName === '连衣-熔岩布丁印象');
const singleSample = pieces.find(i => i.pieceName === '初始法杖');

const checks = [
  ['server defines clothing data file', server.includes('CLOTHING_FILE')],
  ['server exposes api clothing endpoint', server.includes("url.pathname === '/api/clothing'")],
  ['game-data includes clothing and progress', server.includes('clothing') && server.includes('clothing_progress')],
  ['clothing tab routes to dedicated renderer', /if \(name === 'clothing'\) \{ renderClothingTab\(\); return; \}/.test(html)],
  ['renderClothingTab exists', /function\s+renderClothingTab\s*\(/.test(html)],
  ['renderClothingSetCard exists for set cards', /function\s+renderClothingSetCard\s*\(/.test(html)],
  ['renderClothingSingleRow exists for single items', /function\s+renderClothingSingleRow\s*\(/.test(html)],
  ['toggleClothingPiece exists', /async\s+function\s+toggleClothingPiece\s*\(/.test(html)],
  ['clothing renderer uses gameData.clothing sets and pieces', html.includes('gameData?.clothing') && html.includes('.sets') && html.includes('.pieces')],
  ['clothing progress is persisted separately', html.includes('clothing_progress')],
  ['clothing UI has type filter chips', html.includes('clothingTypeFilter') && html.includes('套装') && html.includes('单件')],
  ['clothing UI explains gorgeous badge from definitions', html.includes('华丽徽章说明') && /(?:gameData\?\.clothing|clothing)(?:\?\.|\.)definitions/.test(html) && html.includes('gorgeousBadge') && html.includes('gorgeousMagic')],
  ['clothing UI computes and renders gorgeous magic progress', /function\s+getGorgeousMagicProgress\s*\(\s*set\s*,\s*pieces\s*\)/.test(html) && /(?:const|let)\s+\w+\s*=\s*getGorgeousMagicProgress\s*\(\s*set\s*,\s*pieces\s*\)/.test(html) && html.includes('requiredPieceCount') && html.includes('magic_required')],
  ['clothing UI excludes paid pieces from target statistics', /function\s+isClothingTargetPiece\s*\(\s*item\s*\)/.test(html) && /item\.obtainType\s*!==\s*['"]paid['"]/.test(html) && /clothing\.filter\(isClothingTargetPiece\)/.test(html)],
  ['clothing UI renders paid non-target label conditionally', html.includes('付费 · 非收集目标') && /item\.obtainType\s*===\s*['"]paid['"]/.test(html)],
  ['clothing UI filters by piece category', /\bclothingCategoryFilter\s*=\s*['"]all['"]/.test(html) && /item\.category\s*===\s*clothingCategoryFilter/.test(html)],
  ['clothing UI shows set-level paired pet in card', html.includes('pairedPetName') && html.includes('配对精灵')],
  ['set card pieces do not duplicate shared set fields', html.includes("toggleClothingPiece('${item.id}')") && html.includes('pieceName')],
  ['clothing data file exists as sets and pieces object', Array.isArray(sets) && Array.isArray(pieces)],
  ['real set sample stores gorgeous magic contract', !!setSample && setSample.requiredPieceCount === 6 && setSample.gorgeousMagicPetName === '熔岩布丁' && !!setSample.obtainMethod],
  ['real set piece sample follows set detail contract', !!setPieceSample && setPieceSample.collectionType === 'set' && setPieceSample.setId === setSample?.id && setPieceSample.category === '玩偶服/连衣' && setPieceSample.setRole === 'magic_required' && setPieceSample.obtainType === 'standard'],
  ['real single sample follows standalone detail contract', !!singleSample && singleSample.collectionType === 'single' && !Object.prototype.hasOwnProperty.call(singleSample, 'setId') && !Object.prototype.hasOwnProperty.call(singleSample, 'setRole') && singleSample.category === '法杖' && singleSample.obtainType === 'standard' && !!singleSample.obtainMethod],
  ['collections has clothing_progress object', collections.clothing_progress && typeof collections.clothing_progress === 'object' && !Array.isArray(collections.clothing_progress)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
