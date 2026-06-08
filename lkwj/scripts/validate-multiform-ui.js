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
  ['forms_collected is persisted', html.includes('forms_collected')],
  ['dashboard has random modules', /function\s+renderRandomModule\s*\(/.test(html) && html.includes('randomTasks')],
  ['random supports form module', /function\s+pickRandomForm\s*\(/.test(html) && /markRandomFormTask/.test(html)],
  ['random supports fruit module', /function\s+pickRandomFruit\s*\(/.test(html) && /markRandomFruitTask/.test(html)],
  ['random displays pet number', html.includes('formatPetNo')],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
