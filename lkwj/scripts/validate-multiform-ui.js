const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const evolutionChains = Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'evolution-chains.json'), 'utf8')));
const getEvolutionPathsStart = html.indexOf('function getEvolutionPaths(petKey)');
const getEvolutionPathsEnd = html.indexOf('\n// 直线链', getEvolutionPathsStart);
const getEvolutionPathsSource = getEvolutionPathsStart >= 0 && getEvolutionPathsEnd > getEvolutionPathsStart
  ? html.slice(getEvolutionPathsStart, getEvolutionPathsEnd)
  : '';
const runtimeGameData = { evolutionChains };
const runtimeGetChain = (petKey) => evolutionChains.find((chain) => chain.nodes?.[petKey]);
const runtimeGetEvolutionPaths = getEvolutionPathsSource
  ? new Function('gameData', 'getChain', `${getEvolutionPathsSource}; return getEvolutionPaths;`)(runtimeGameData, runtimeGetChain)
  : () => [];

const checks = [
  ['nav has multiform tab', /switchTab\('forms'\)[\s\S]*多形态/.test(html)],
  ['container has tab-forms', html.includes('id="tab-forms"')],
  ['ALL_TABS includes forms', /ALL_TABS\s*=\s*\[[^\]]*'forms'/.test(html)],
  ['renderFormsTab exists', /function\s+renderFormsTab\s*\(/.test(html)],
  ['forms tab renders grouped pets', /function\s+getFormsPetGroups\s*\(/.test(html) && /function\s+renderFormPetCard\s*\(/.test(html)],
  ['toggleForm exists', /async\s+function\s+toggleForm\s*\(/.test(html)],
  ['confirm_forms uses derived task state', /function\s+isTaskDone\s*\(/.test(html) && /confirm_forms/.test(html)],
  ['confirm_forms supports any count from an eligible form pool', /const\s+targetCount\s*=\s*Math\.min\(task\.count/.test(html)
    && /const\s+collectedCount\s*=\s*required\.filter/.test(html)
    && /collectedCount\s*>=\s*targetCount/.test(html)],
  ['forms_collected is persisted', html.includes('forms_collected')],
  ['dashboard has random modules', /function\s+renderRandomModule\s*\(/.test(html) && html.includes('randomTasks')],
  ['random supports form module', /function\s+pickRandomForm\s*\(/.test(html) && /markRandomFormTask/.test(html)],
  ['random supports fruit module', /function\s+pickRandomFruit\s*\(/.test(html) && /markRandomFruitTask/.test(html)],
  ['random displays pet number', html.includes('formatPetNo')],
  ['confirm_forms task title is the inline jump action', /task-inline-link/.test(html)
    && /jumpToForms\('\$\{petKey\}'\)/.test(html)
    && !/<button class="task-jump-btn"/.test(html)],
  ['jump action targets and expands the matching pet', /function\s+jumpToForms\s*\(\s*petKey\s*\)/.test(html)
    && /formSearch\s*=\s*petKey\.replace\(['"]pet_['"],\s*['"]['"]\)/.test(html)
    && /formStatus\s*=\s*['"]all['"]/.test(html)
    && /expandedFormPet\s*=\s*petKey/.test(html)
    && /switchTab\(['"]forms['"]\)/.test(html)],
  ['jump action scrolls to stable form card anchor', html.includes('form-pet-${group.petKey}')
    && html.includes('form-pet-${petKey}')
    && html.includes('scrollIntoView')],
  ['full evolution chain is rendered in sprite and multiform details', /function\s+getEvolutionPaths\s*\(/.test(html)
    && /function\s+renderEvolutionChain\s*\(/.test(html)
    && /paths\.some\(\(path\)\s*=>\s*path\.length\s*>\s*1\)/.test(html)
    && html.includes('>进化链</div>')
    && /renderEvolutionChain\(petKey,\s*['"]sprite['"]\)/.test(html)
    && /renderEvolutionChain\(group\.petKey,\s*['"]forms['"]\)/.test(html)],
  ['evolution chain links search exact pets in the appropriate tab', /function\s+jumpToChainPet\s*\(/.test(html)
    && /jumpToChainPet\('\$\{nodePetKey\}',\s*'\$\{targetTab\}'\)/.test(html)],
  ['multiform chain links fall back to sprite for pets without forms', /tabName\s*===\s*['"]forms['"][\s\S]*getCollectibleFormEntries\(nodePetKey\)\.length[\s\S]*['"]sprite['"]/.test(html)],
  ['evolution chain keeps pet numbers but excludes evolution conditions', /\$\{formatPetNo\(nodePetKey\)\}/.test(html)
    && !/function\s+formatEvolutionCondition\s*\(/.test(html)
    && !/evolution-condition/.test(html)],
  ['split evolution records still produce one complete chain', runtimeGetEvolutionPaths('pet_18')
    .some((path) => JSON.stringify(path) === JSON.stringify(['pet_18', 'pet_19', 'pet_20']))],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
