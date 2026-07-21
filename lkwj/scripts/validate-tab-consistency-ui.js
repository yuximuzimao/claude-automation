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
const fruitRow = sourceBetween('function renderFruitRow(', 'async function toggleFruit(');
const clothingTab = sourceBetween('function renderClothingTab()', 'function setClothingStatusFilter(');

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
if (/\.fruit-method\s*\{[^}]*overflow\s*:\s*hidden/.test(html)
  || !/@media\s*\(max-width:\s*720px\)[\s\S]*?\.fruit-method\s*\{[^}]*white-space\s*:\s*normal/.test(html)) {
  errors.push('fruit methods must stay complete: one line on desktop and wrapping on narrow screens');
}
if (/clothing-info-panel|华丽徽章说明/.test(clothingTab)) {
  errors.push('internal gorgeous badge rules must not be shown in the clothing tab');
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ filterLabels: 0, spriteStatsRows: 1, fruitMethodRows: 1 }, null, 2));
