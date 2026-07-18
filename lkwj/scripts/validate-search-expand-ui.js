const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

const checks = [
  ['shared single-result expansion helper exists', /function\s+resolveSingleSearchExpansion\s*\(/.test(html)
    && /searchValue/.test(html)
    && /items\.length\s*===\s*1/.test(html)],
  ['sprite search uses shared expansion rule', /expandedPet\s*=\s*resolveSingleSearchExpansion\(spriteSearch,\s*entries/.test(html)],
  ['multiform search uses shared expansion rule', /expandedFormPet\s*=\s*resolveSingleSearchExpansion\(formSearch,\s*groups/.test(html)],
  ['dungeon search uses shared expansion rule', /expandedDungeon\s*=\s*resolveSingleSearchExpansion\(dungeonSearch,\s*list/.test(html)],
  ['clothing search uses shared expansion rule', /expandedClothingSet\s*=\s*resolveSingleSearchExpansion\([\s\S]*?clothingSearch,[\s\S]*?entries/.test(html)],
  ['multiform cards no longer expand every nonempty search', !/expandedFormPet\s*===\s*group\.petKey\s*\|\|\s*!!formSearch/.test(html)],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
