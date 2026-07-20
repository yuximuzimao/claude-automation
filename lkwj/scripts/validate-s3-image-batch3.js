const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));

const expectedFamilies = [
  [['pet_456', '霹雳宝宝', ['电']], ['pet_457', '雷鸣小子', ['电']], ['pet_458', '雷神之子', ['电']]],
  [['pet_459', '芽眼魔', ['恶', '水']], ['pet_460', '叶眼魔', ['恶', '水']], ['pet_461', '障眼魔', ['恶', '水']]],
  [['pet_462', '烈钻鸟', ['火', '翼']], ['pet_463', '长尾火鸟', ['火', '翼']], ['pet_464', '火羽', ['火', '翼']]],
  [['pet_465', '叮叮卯', ['机械', '虫']], ['pet_466', '飞飞钥', ['机械', '虫']]],
  [['pet_467', '觅觅蝠', ['翼']], ['pet_468', '翻翻蝠', ['翼']], ['pet_469', '夜游魔', ['翼', '恶']]],
  [['pet_470', '火豆丁', ['火']], ['pet_471', '火蛮人', ['火']], ['pet_472', '火巨人', ['火']]],
  [['pet_473', '星云旅者', ['翼', '幻']]],
  [['pet_474', '森豆丁', ['草']], ['pet_475', '森蛮人', ['草']], ['pet_476', '森巨人', ['草']]],
  [['pet_477', '雪灵兽', ['冰']], ['pet_478', '幻雪兽', ['冰']], ['pet_479', '饮雪狂兽', ['冰']]],
  [['pet_480', '瑰眼仔', ['恶', '虫']], ['pet_481', '耳翎瑰魅', ['恶', '虫']], ['pet_482', '邪眼巨魔', ['恶', '虫']]],
  [['pet_483', '碎晶蝎', ['恶', '地']], ['pet_484', '晶尾蝎', ['恶', '地']], ['pet_485', '蝎子王', ['恶', '地']]],
];

const errors = [];

for (const family of expectedFamilies) {
  const baseKey = family[0][0];
  const chain = chains.find(item => item.baseSpeciesId === baseKey);
  if (!chain) {
    errors.push(`${baseKey}: evolution chain missing`);
    continue;
  }

  family.forEach(([petKey, name, element], index) => {
    const pet = pets[petKey];
    if (!pet) {
      errors.push(`${petKey}: pet missing`);
      return;
    }
    if (pet.name !== name) errors.push(`${petKey}: expected ${name}, got ${pet.name}`);
    if (JSON.stringify(pet.element) !== JSON.stringify(element)) {
      errors.push(`${petKey} ${name}: element mismatch ${JSON.stringify(pet.element)}`);
    }
    if (Object.keys(pet.tags || {}).length !== 0) {
      errors.push(`${petKey} ${name}: image did not establish tags; tags must remain empty`);
    }
    if (!Array.isArray(tasks[petKey]) || tasks[petKey].length !== 0) {
      errors.push(`${petKey} ${name}: tasks must remain empty until Excel stage`);
    }

    const nextKey = family[index + 1]?.[0];
    const evolvesTo = chain.nodes?.[petKey]?.evolvesTo || [];
    if (nextKey) {
      if (evolvesTo.length !== 1 || evolvesTo[0].toSpeciesId !== nextKey) {
        errors.push(`${petKey} ${name}: expected evolution to ${nextKey}`);
      }
      if (evolvesTo[0]?.condition?.type !== 'unknown') {
        errors.push(`${petKey} ${name}: evolution condition must remain unknown`);
      }
    } else if (evolvesTo.length !== 0) {
      errors.push(`${petKey} ${name}: final node must not evolve further`);
    }
  });
}

const expectedForms = [
  ['pet_57', '梦游', '穿星星睡衣的样子'],
  ['pet_58', '梦悠悠', '穿星星睡衣的样子'],
  ['pet_44', '丢丢', '火山附近的样子'],
  ['pet_45', '卡卡虫', '火山附近的样子'],
  ['pet_46', '卡瓦重', '火山附近的样子'],
];

for (const [petKey, name, formKey] of expectedForms) {
  const pet = pets[petKey];
  if (!pet || pet.name !== name) {
    errors.push(`${petKey}: expected existing pet ${name}`);
    continue;
  }
  if (!pet.forms?.[formKey] || pet.forms[formKey].formName !== formKey) {
    errors.push(`${petKey} ${name}: missing form ${formKey}`);
  }
}

const dreamTask = (tasks.pet_58 || []).find(task => task.type === 'confirm_forms');
if (!dreamTask || dreamTask.count !== 2
  || JSON.stringify(dreamTask.requiredForms) !== JSON.stringify(['穿旧睡衣的样子', '穿星星睡衣的样子'])) {
  errors.push('梦悠悠 existing confirm_forms task must remain unchanged');
}

for (const petKey of ['pet_44', 'pet_45', 'pet_46']) {
  const formTask = (tasks[petKey] || []).find(task => task.type === 'confirm_forms');
  if (!formTask || formTask.count !== 3 || formTask.requiredForms.includes('火山附近的样子')) {
    errors.push(`${petKey}: 火山附近的样子 must not be added to confirm_forms before Excel verification`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  newFamilies: expectedFamilies.length,
  newPets: expectedFamilies.flat().length,
  addedExistingForms: expectedForms.length,
  provisionalIds: 'pet_456-pet_485',
  tasksAdded: 0,
}, null, 2));
