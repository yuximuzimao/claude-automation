const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

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
  ['confirm_forms task renders jump action', html.includes('去多形态') && /jumpToForms\('\$\{petKey\}'\)/.test(html)],
  ['jump action targets and expands the matching pet', /function\s+jumpToForms\s*\(\s*petKey\s*\)/.test(html)
    && /formSearch\s*=\s*pet\.name/.test(html)
    && /formStatus\s*=\s*['"]all['"]/.test(html)
    && /expandedFormPet\s*=\s*petKey/.test(html)
    && /switchTab\(['"]forms['"]\)/.test(html)],
  ['jump action scrolls to stable form card anchor', html.includes('form-pet-${group.petKey}')
    && html.includes('form-pet-${petKey}')
    && html.includes('scrollIntoView')],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
