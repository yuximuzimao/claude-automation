const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));

const expectedFamilies = [
  [['pet_422', '蝴蝶陶陶', ['萌']], ['pet_423', '钢耳毛毛', ['萌', '毒']], ['pet_424', '绯红爪爪', ['萌', '毒']]],
  [['pet_425', '苞米仔', ['草', '火']], ['pet_426', '炮米花', ['草', '火']]],
  [['pet_427', '十字蝌蚪', ['水', '地']], ['pet_428', '十字蛙', ['水', '地']], ['pet_429', '深渊蛙', ['水', '地']]],
  [['pet_430', '卡波', ['恶']], ['pet_431', '卡拉波斯', ['恶']]],
  [['pet_432', '守夜烛', ['火', '光']], ['pet_433', '流明坎德拉', ['火', '光']]],
  [['pet_434', '蜜果骸', ['幽', '草']], ['pet_435', '半朽蜜果灵', ['幽', '草']]],
  [['pet_436', '稻草人', ['萌', '武']], ['pet_437', '稻草守护者', ['萌', '武']]],
  [['pet_438', '栗鼠', ['毒', '普通']], ['pet_439', '壳栗丝鼠', ['毒', '普通']]],
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
    if (!pet.tags?.chromatic) errors.push(`${petKey} ${name}: chromatic tag missing`);
    if (!Array.isArray(tasks[petKey]) || tasks[petKey].length !== 0) {
      errors.push(`${petKey} ${name}: tasks should remain empty until official task data arrives`);
    }

    const nextKey = family[index + 1]?.[0];
    const evolvesTo = chain.nodes?.[petKey]?.evolvesTo || [];
    if (nextKey) {
      if (evolvesTo.length !== 1 || evolvesTo[0].toSpeciesId !== nextKey) {
        errors.push(`${petKey} ${name}: expected evolution to ${nextKey}`);
      }
      if (evolvesTo[0]?.condition?.type !== 'unknown') {
        errors.push(`${petKey} ${name}: evolution condition must remain unknown until sourced`);
      }
    } else {
      if (evolvesTo.length) errors.push(`${petKey} ${name}: final evolution should not evolve further`);
      if (pet.tags?.shiny?.limitedTime !== 'S3「铅字幻梦」') {
        errors.push(`${petKey} ${name}: S3 shiny tag missing`);
      }
    }
  });

  const obtainMethods = pets[baseKey]?.forms?.basic?.obtainMethods || [];
  if (!obtainMethods.includes('S3赛季奇遇·精灵童话')) {
    errors.push(`${baseKey}: S3 encounter obtain method missing`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  families: expectedFamilies.length,
  pets: expectedFamilies.flat().length,
  pendingTasks: expectedFamilies.flat().length,
}, null, 2));
