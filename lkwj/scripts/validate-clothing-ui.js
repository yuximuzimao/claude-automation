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
const setSample = sets.find(i => i.id === 'clothing_set_1');
const setPieceSample = pieces.find(i => i.id === 'clothing_1');
const singleSample = pieces.find(i => i.id === 'clothing_6');

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
  ['set sample stores shared effect and method once', !!setSample && setSample.name === '木之本樱魔法装扮' && setSample.hasEffect === true && setSample.pairedPetName === '小可' && setSample.obtainMethod],
  ['set piece sample references set without duplicated shared fields', !!setPieceSample && setPieceSample.collectionType === 'set' && setPieceSample.setId === 'clothing_set_1' && setPieceSample.pieceName === '发型' && !hasSharedSetFields(setPieceSample)],
  ['single sample is a standalone collectible piece with own method', !!singleSample && singleSample.collectionType === 'single' && !singleSample.setId && singleSample.obtainMethod],
  ['collections has clothing_progress object', collections.clothing_progress && typeof collections.clothing_progress === 'object' && !Array.isArray(collections.clothing_progress)],
];

function hasSharedSetFields(item) {
  return Object.prototype.hasOwnProperty.call(item, 'obtainMethod')
    || Object.prototype.hasOwnProperty.call(item, 'pairedPetName')
    || Object.prototype.hasOwnProperty.call(item, 'hasEffect');
}

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
