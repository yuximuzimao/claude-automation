const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));
const extract = JSON.parse(fs.readFileSync(path.join(root, 'scripts', 'fixtures', 's3-excel-extract.json'), 'utf8'));

const nameOverrides = {
  392: '饮雪狂兽',
  402: '邪眼巨魔',
};

function key(number) {
  return `pet_${number}`;
}

function elements(value) {
  return String(value || '').split(/[,，]/).map(item => item.trim()).filter(Boolean);
}

const errors = [];
const groups = extract.s3Groups.filter(group => group.number >= 376 && group.number <= 439);
if (groups.length !== 64) errors.push(`expected 64 S3 groups, got ${groups.length}`);

for (const petKey of Object.keys(pets)) {
  const number = Number(petKey.replace('pet_', ''));
  if (number >= 440 && number <= 485) errors.push(`temporary pet remains: ${petKey}`);
}

for (const group of groups) {
  const petKey = key(group.number);
  const pet = pets[petKey];
  if (!pet) {
    errors.push(`${petKey}: pet missing`);
    continue;
  }
  const expectedName = nameOverrides[group.number] || group.name;
  if (pet.name !== expectedName) errors.push(`${petKey}: name ${pet.name} != ${expectedName}`);
  if (JSON.stringify(pet.element) !== JSON.stringify(elements(group.element))) {
    errors.push(`${petKey} ${pet.name}: element mismatch ${JSON.stringify(pet.element)} != ${group.element}`);
  }
  const expectedTaskCount = group.rows.filter(row => row.type).length;
  if ((tasks[petKey] || []).length !== expectedTaskCount) {
    errors.push(`${petKey} ${pet.name}: task count ${(tasks[petKey] || []).length} != ${expectedTaskCount}`);
  }

  const evolveRow = group.rows.find(row => row.type === '进化');
  if (evolveRow) {
    const chain = chains.find(item => item.nodes?.[petKey]);
    const evolutions = chain?.nodes?.[petKey]?.evolvesTo || [];
    if (!evolutions.length) {
      errors.push(`${petKey} ${pet.name}: evolve task has no chain target`);
    }
    const level = Number((/(\d+)级/.exec(evolveRow.note || '') || [])[1]);
    for (const evolution of evolutions) {
      if (!level || evolution.condition?.level !== level || evolution.condition?.type !== 'level') {
        errors.push(`${petKey} ${pet.name}: evolution condition does not match ${evolveRow.note}`);
      }
    }
  }
}

const s3Tasks = groups.flatMap(group => tasks[key(group.number)] || []);
if (s3Tasks.length !== 281) errors.push(`S3 task total ${s3Tasks.length} != 281`);
if (s3Tasks.filter(task => task.type === 'fruit').length !== 12) errors.push('S3 fruit task total must be 12');
if (s3Tasks.filter(task => task.type === 'capture_shiny').length !== 8) errors.push('S3 capture_shiny total must be 8');

const s3FruitRecords = groups.filter(group => pets[key(group.number)]?.fruit).length;
if (s3FruitRecords !== 25) errors.push(`S3 fruit record total ${s3FruitRecords} != 25`);

for (const number of [419, 421]) {
  const pet = pets[key(number)];
  if (pet?.tags?.shiny?.limitedTime !== 'S3通行证') errors.push(`${key(number)} must be S3 pass shiny`);
  if ((tasks[key(number)] || []).some(task => task.type === 'capture_shiny')) {
    errors.push(`${key(number)} pass shiny must not have capture_shiny task`);
  }
}

for (const number of [72, 78, 101, 178, 233, 241, 268, 269, 279, 424, 426, 429, 431, 433, 435, 437, 439]) {
  const pet = pets[key(number)];
  if (pet?.tags?.shiny?.limitedTime !== 'S3「铅字幻梦」') {
    errors.push(`${key(number)} must have S3 season shiny tag`);
  }
  if (!(tasks[key(number)] || []).some(task => task.type === 'capture_shiny')) {
    errors.push(`${key(number)} must have capture_shiny task`);
  }
}

const expectedCorrections = {
  pet_392: '饮雪狂兽',
  pet_402: '邪眼巨魔',
  pet_411: '珀尔鼬',
  pet_423: '铆钉毛毛',
  pet_424: '徘徊爪爪',
};
for (const [petKey, expectedName] of Object.entries(expectedCorrections)) {
  if (pets[petKey]?.name !== expectedName) errors.push(`${petKey}: expected corrected name ${expectedName}`);
}

const regionalForms = ['沙地附近的样子', '草地附近的样子', '雪山附近的样子', '火山附近的样子'];
for (const petKey of ['pet_44', 'pet_45', 'pet_46']) {
  const forms = Object.keys(pets[petKey]?.forms || {}).filter(formKey => !['basic', 'leader'].includes(formKey));
  const formTask = (tasks[petKey] || []).find(task => task.type === 'confirm_forms');
  if (JSON.stringify(forms) !== JSON.stringify(regionalForms)
    || formTask?.count !== 3
    || JSON.stringify(formTask?.requiredForms) !== JSON.stringify(regionalForms)) {
    errors.push(`${petKey}: regional any-3-of-4 form setup mismatch`);
  }
}

for (const petKey of ['pet_57', 'pet_58']) {
  const forms = Object.keys(pets[petKey]?.forms || {}).filter(formKey => !['basic', 'leader'].includes(formKey));
  const task = (tasks[petKey] || []).find(item => item.type === 'confirm_forms');
  if (JSON.stringify(forms) !== JSON.stringify(['穿旧睡衣的样子', '穿星星睡衣的样子'])
    || task?.count !== 2
    || JSON.stringify(task?.requiredForms) !== JSON.stringify(forms)) {
    errors.push(`${petKey}: pajama form setup mismatch`);
  }
}

const allTasks = Object.values(tasks).flat();
const multiformItems = Object.values(pets)
  .flatMap(pet => Object.keys(pet.forms || {}).filter(formKey => !['basic', 'leader'].includes(formKey))).length;
const expectedTotals = {
  pets: 439,
  tasks: 2192,
  fruitTasks: 108,
  fruitRecords: 170,
  confirmForms: 53,
  multiformItems: 144,
  chains: 191,
};
const totals = {
  pets: Object.keys(pets).length,
  tasks: allTasks.length,
  fruitTasks: allTasks.filter(task => task.type === 'fruit').length,
  fruitRecords: Object.values(pets).filter(pet => pet.fruit).length,
  confirmForms: allTasks.filter(task => task.type === 'confirm_forms').length,
  multiformItems,
  chains: chains.length,
};
for (const [name, expected] of Object.entries(expectedTotals)) {
  if (totals[name] !== expected) errors.push(`${name}: ${totals[name]} != ${expected}`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  groups: groups.length,
  s3Tasks: s3Tasks.length,
  s3FruitRecords,
  totals,
}, null, 2));
