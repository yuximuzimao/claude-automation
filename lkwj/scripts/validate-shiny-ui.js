const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));

function isFinal(petKey) {
  const chain = chains.find(item => item.nodes?.[petKey]);
  return !chain || !(chain.nodes[petKey]?.evolvesTo || []).length;
}

const shinyFinals = Object.entries(pets).filter(([petKey, pet]) => pet.tags?.shiny && isFinal(petKey));
const shinyEntries = shinyFinals.flatMap(([petKey, pet]) => {
  const forms = Object.keys(pet.forms || {}).filter(formKey => formKey !== 'basic' && formKey !== 'leader');
  return forms.length ? forms.map(formKey => `${petKey}::${formKey}`) : [petKey];
});

const checks = [
  ['shiny list uses actual forms and only falls back to basic when none exist', /function\s+getShinyFormEntries\s*\(/.test(html)
    && /getCollectibleFormEntries\(petKey\)/.test(html)
    && /if\s*\(!variants\.length\)[\s\S]*?formKey:\s*['"]basic['"]/.test(html)
    && /return\s+variants\.map/.test(html)],
  ['multiform shiny entries use stable progress keys', /function\s+getShinyProgressKey\s*\(/.test(html)
    && /petKey.*formKey/.test(html)
    && /::/.test(html)],
  ['single-form shiny progress keeps the pet-level key', /formKey\s*===\s*['"]basic['"]/.test(html)
    && /return\s+petKey/.test(html)],
  ['shiny rows display form names and toggle the matching entry', /s\.formName/.test(html)
    && /toggleShinyTask\('\$\{s\.petKey\}','\$\{escAttr\(s\.formKey\)\}'\)/.test(html)],
  ['shiny toggle persists by progress key rather than only pet id', /const\s+progressKey\s*=\s*getShinyProgressKey\(petKey,\s*formKey\)/.test(html)
    && /data\.shiny_progress\[progressKey\]/.test(html)],
  ['current 38 shiny finals expand to 39 collection entries', shinyFinals.length === 38 && shinyEntries.length === 39],
  ['加油蟹 has exactly two form-level shiny keys and no basic entry', !shinyEntries.includes('pet_361')
    && shinyEntries.includes('pet_361::单只海葵的样子')
    && shinyEntries.includes('pet_361::（双只海葵的样子）')
    && shinyEntries.filter(key => key.startsWith('pet_361')).length === 2],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
