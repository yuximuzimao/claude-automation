const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const errors = [];

function sourceBetween(startMarker, endMarker) {
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker, start);
  if (start < 0 || end < 0) return '';
  return html.slice(start, end);
}

const spriteContent = sourceBetween('function renderSpriteContent()', 'function renderSpriteCard(');
const spriteTab = sourceBetween('function renderSpriteTab()', 'function renderSpriteContent()');
const fruitList = sourceBetween('function getFruitList()', 'function renderFruitsTab()');
const fruitRow = sourceBetween('function renderFruitRow(', 'async function toggleFruit(');
const clothingTab = sourceBetween('function renderClothingTab()', 'function setClothingStatusFilter(');
const flatCollectionRenderers = [
  ['shiny', sourceBetween('function renderShinyContent()', 'function renderShinyRow(')],
  ['category', sourceBetween('function renderCategoryContent(', '// ═══════════ 多形态 Tab')],
  ['fruits', sourceBetween('function renderFruitsContent()', 'function setFruitTypeFilter(')],
  ['furniture', sourceBetween('function renderFurnitureContent()', 'function setFurnitureStatusFilter(')],
  ['titles', sourceBetween('function renderTitlesContent()', 'function formatTitleName(')],
  ['dungeons', sourceBetween('function renderDungeonsContent()', 'function renderDungeonRow(')],
];

if (/class="tb-label"/.test(html)) {
  errors.push('filter rows must not display redundant group labels');
}
if (/class="chips"\s+style="margin-bottom:8px"/.test(html)) {
  errors.push('all filter rows must use the shared tb-section layout');
}
if (/class="sprite-stats"/.test(spriteContent)) {
  errors.push('sprite content must not render a second statistics row');
}
if (!/id="sprite-stats"/.test(spriteTab) || !/getElementById\('sprite-stats'\)/.test(spriteContent) || !/匹配/.test(spriteContent)) {
  errors.push('sprite filters must update the single toolbar statistics row');
}
if (!/class="task-methods fruit-method"/.test(fruitRow) || (fruitRow.match(/class="task-methods fruit-method"/g) || []).length !== 1) {
  errors.push('fruit acquisition method and location must share one small-text row');
}
if (!/title="\$\{escAttr\(/.test(fruitRow)) {
  errors.push('single-line fruit methods must retain the full text as a tooltip');
}
if (!/\.fruit-method\s*\{[^}]*white-space\s*:\s*nowrap/.test(html)
  || /@media\s*\(max-width:\s*720px\)[\s\S]*?\.fruit-method\s*\{[^}]*white-space\s*:\s*normal/.test(html)) {
  errors.push('fruit methods must stay on one complete line in the desktop layout');
}
if (!/\.split-tab-toolbar\s*\{[^}]*margin-bottom\s*:\s*14px/.test(html)
  || !/id="sprite-toolbar"\s+class="split-tab-toolbar"/.test(html)
  || !/id="shiny-toolbar"\s+class="split-tab-toolbar"/.test(html)) {
  errors.push('sprite and shiny filters must share the desktop content gap');
}
if (/clothing-info-panel|华丽徽章说明/.test(clothingTab)) {
  errors.push('internal gorgeous badge rules must not be shown in the clothing tab');
}
if (!/const\s+petEntries\s*=\s*\(\)\s*=>[\s\S]*?\.sort\(\(a,\s*b\)\s*=>\s*petNumberFromKey/.test(html)) {
  errors.push('all pet-based lists must start from an explicit numeric pet order');
}
for (const [name, source] of flatCollectionRenderers) {
  if (/renderCollapsibleDoneSection|class="section-title"/.test(source)) {
    errors.push(`${name}: filtered results must render as one flat list without collection-status groups`);
  }
}
if (/\bSHINY_PAGE\b|\bshinyPage\b|function\s+getShinyDisplayPage|function\s+renderPagination|function\s+goShinyPage/.test(html)) {
  errors.push('collection tabs must not keep pagination state or rendering');
}
if (!/function\s+formatFruitFamilyRange\s*\(/.test(html)
  || !/fruit\.familyNumberRange/.test(fruitRow)
  || !/function\s+getFruitList\s*\(/.test(html)) {
  errors.push('fruit rows must show and sort by their Excel family number range');
}
if (!/additionalFruits/.test(fruitList)
  || !/additional_fruits_acquired/.test(fruitList)
  || !/getFruitList\(\)/.test(sourceBetween('function renderFruitsTab()', '// ═══════════ 家具 Tab'))
  || !/toggleFruit\('\$\{item\.petKey\}','\$\{item\.fruitId/.test(fruitRow)) {
  errors.push('fruit list must count and toggle additional form fruits independently');
}
if (!/fruit\?\.availability/.test(fruitRow) || !/tag-limited/.test(fruitRow)) {
  errors.push('fruit rows must display explicit channel availability without changing ownership');
}
if (!/function\s+compareStableItems\s*\(/.test(html)
  || !/getFurnitureList\([\s\S]*?\.sort\(compareStableItems\)/.test(html)
  || !/getTitleList\([\s\S]*?\.sort\(compareStableItems\)/.test(html)
  || !/getDungeonList\([\s\S]*?\.sort\(compareStableItems\)/.test(html)) {
  errors.push('non-pet collection tabs must use an explicit stable item order');
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ filterLabels: 0, spriteStatsRows: 1, fruitMethodRows: 1 }, null, 2));
