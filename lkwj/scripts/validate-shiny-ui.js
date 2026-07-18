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
  return [petKey, ...forms.map(formKey => `${petKey}::${formKey}`)];
});

const checks = [
  ['shiny list expands every multiform pet', /function\s+getShinyFormEntries\s*\(/.test(html)
    && /getCollectibleFormEntries\(petKey\)/.test(html)
    && /formKey:\s*['"]basic['"]/.test(html)],
  ['multiform shiny entries use stable progress keys', /function\s+getShinyProgressKey\s*\(/.test(html)
    && /petKey.*formKey/.test(html)
    && /::/.test(html)],
  ['legacy pet-level shiny progress remains the default-form key', /formKey\s*===\s*['"]basic['"]/.test(html)
    && /return\s+petKey/.test(html)],
  ['shiny rows display form names and toggle the matching entry', /s\.formName/.test(html)
    && /toggleShinyTask\('\$\{s\.petKey\}','\$\{escAttr\(s\.formKey\)\}'\)/.test(html)],
  ['shiny toggle persists by progress key rather than only pet id', /const\s+progressKey\s*=\s*getShinyProgressKey\(petKey,\s*formKey\)/.test(html)
    && /data\.shiny_progress\[progressKey\]/.test(html)],
  ['current 38 shiny finals expand to 40 collection entries', shinyFinals.length === 38 && shinyEntries.length === 40],
  ['加油蟹 default and both forms have independent shiny keys', shinyEntries.includes('pet_361')
    && shinyEntries.includes('pet_361::单只海葵的样子')
    && shinyEntries.includes('pet_361::（双只海葵的样子）')],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
