const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));
const collections = JSON.parse(fs.readFileSync(path.join(root, 'data', 'collections.json'), 'utf8'));
const extract = JSON.parse(fs.readFileSync(path.join(root, 'scripts', 'fixtures', 's3-excel-extract.json'), 'utf8'));
const syncSource = fs.readFileSync(path.join(root, 'scripts', 'sync-latest-excel.py'), 'utf8');
const auditSource = fs.readFileSync(path.join(root, 'scripts', 'audit-latest-excel.py'), 'utf8');
const readerSource = fs.readFileSync(path.join(root, 'scripts', 'read-latest-excel.py'), 'utf8');
const legacyFruitUpdaterSource = fs.readFileSync(path.join(root, 'scripts', 'update-fruit-data.js'), 'utf8');

const nameOverrides = {
  392: '饮雪狂兽',
  402: '邪眼巨魔',
};
const evolutionLevelOverrides = {
  430: 40,
};

function key(number) {
  return `pet_${number}`;
}

function elements(value) {
  return String(value || '').split(/[,，]/).map(item => item.trim()).filter(Boolean);
}

const errors = [];
const correctedFruitNames = {
  pet_4: '喵喵的果实',
  pet_11: '鸭吉吉的果实',
  pet_31: '恶魔叮的果实',
  pet_107: '阿米亚特的果实',
};
const confirmedOwnedFruitPrefixes = [
  '喵喵', '恶魔叮', '鸭吉吉', '阿米亚特', '蹦蹦种子', '奇丽草', '蒲公英', '板板壳',
  '小独角兽', '幽影树', '格兰种子', '灵狐', '治愈兔', '仪使者', '风铃鲨', '大耳帽兜',
  '小夜', '空空颅', '裘洛', '春团', '伏地兽', '拉特', '粉粉星', '机械方方', '贝瑟',
  '小翼龙', '伊雷龙', '菊花梨', '牵线木偶', '布鲁斯', '呼呼猪', '犀角鸟', '粉星仔',
  '海盔虫', '深蓝鲸', '双灯鱼', '厉毒小萝', '梦游', '柴渣虫', '幽星光', '公平鸽',
  '小黑猫', '松仔', '嗜光嗡嗡', '小丑豆豆', '爆焰仔', '墨鱿士', '火红尾', '猴麦仔',
  '加油海葵', '烟花团', '咕咕帽', '炫光迪迪', '小鼓象', '咬咬小子', '咔咔羽毛',
  '恶魔狼', '月牙雪熊', '多西', '噼啪鸟',
];
if (!readerSource.includes('NO_FRUIT_SOURCES')
  || !syncSource.includes('classify_fruit_row')
  || !auditSource.includes('classify_fruit_row')) {
  errors.push('reader, sync and audit must share the verified fruit row classifier');
}
if (!auditSource.includes('fruit_info["obtainType"]')
  || !auditSource.includes('fruit_info["familyNumberRange"]')) {
  errors.push('Excel audit must compare every fruit obtain type and family number range');
}
const groups = extract.s3Groups.filter(group => group.number >= 376 && group.number <= 439);
if (groups.length !== 64) errors.push(`expected 64 S3 groups, got ${groups.length}`);

for (const petKey of Object.keys(pets)) {
  const number = Number(petKey.replace('pet_', ''));
  if (number >= 441 && number <= 485) errors.push(`temporary pet remains: ${petKey}`);
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
    const level = evolutionLevelOverrides[group.number]
      || Number((/(\d+)级/.exec(evolveRow.note || '') || [])[1]);
    for (const evolution of evolutions) {
      if (!level || evolution.condition?.level !== level || evolution.condition?.type !== 'level') {
        errors.push(`${petKey} ${pet.name}: evolution condition does not match ${evolveRow.note}`);
      }
    }
  }
}

const pet430EvolveTask = (tasks.pet_430 || []).find(task => task.type === 'evolve');
if (JSON.stringify(pet430EvolveTask?.obtainMethods) !== JSON.stringify(['40级进化'])) {
  errors.push('pet_430: verified evolution task must use 40级进化');
}

const s3Tasks = groups.flatMap(group => tasks[key(group.number)] || []);
if (s3Tasks.length !== 281) errors.push(`S3 task total ${s3Tasks.length} != 281`);
if (s3Tasks.filter(task => task.type === 'fruit').length !== 12) errors.push('S3 fruit task total must be 12');
if (s3Tasks.filter(task => task.type === 'capture_shiny').length !== 8) errors.push('S3 capture_shiny total must be 8');

const s3FruitRecords = groups.filter(group => pets[key(group.number)]?.fruit).length;
if (s3FruitRecords !== 25) errors.push(`S3 fruit record total ${s3FruitRecords} != 25`);

const additionalFruits = Object.entries(pets).flatMap(([petKey, pet]) =>
  (pet.additionalFruits || []).map(fruit => ({ petKey, fruit }))
);
if (additionalFruits.length !== 1) {
  errors.push(`additional fruit record total ${additionalFruits.length} != 1`);
} else {
  const [{ petKey, fruit }] = additionalFruits;
  if (petKey !== 'pet_11' || fruit.id !== 'burning_duck'
    || fruit.name !== '鸭吉吉-燃了鸭的果实' || fruit.formName !== '燃了鸭'
    || fruit.obtainType !== '限时活动' || fruit.obtainMethod !== '公测礼') {
    errors.push('pet_11: 燃了鸭 additional fruit definition mismatch');
  }
}
if (!collections.sprite_progress?.pet_11?.additional_fruits_acquired?.includes('burning_duck')) {
  errors.push('pet_11: 燃了鸭 additional fruit must be marked acquired');
}
if (pets.pet_339?.fruit?.availability !== '渠道限定 · 当前不可获取'
  || collections.sprite_progress?.pet_339?.fruit_acquired !== true) {
  errors.push('pet_339: 布瓜蝌 fruit must stay acquired and show its unavailable channel status');
}
if (!syncSource.includes('FRUIT_AVAILABILITY') || !syncSource.includes('339: "渠道限定 · 当前不可获取"')) {
  errors.push('Excel sync must preserve the unavailable channel status for 布瓜蝌 fruit');
}

for (const number of [1, 375]) {
  if (pets[key(number)]?.fruit) errors.push(`${key(number)} must not have a fruit definition`);
}
const fruitTypes = new Set(Object.values(pets).flatMap(pet => pet.fruit ? [pet.fruit.obtainType] : []));
const expectedFruitTypes = ['课题任务', '智慧树苗', '剧情任务', '通行证契约礼券', '赛季作业', '限时活动'];
if (JSON.stringify([...fruitTypes].sort()) !== JSON.stringify([...expectedFruitTypes].sort())) {
  errors.push(`fruit types must match the six UI filters: ${JSON.stringify([...fruitTypes])}`);
}
for (const [petKey, pet] of Object.entries(pets)) {
  if (!pet.fruit) continue;
  if (!pet.fruit.name.endsWith('的果实')) {
    errors.push(`${petKey}: fruit name must end with 的果实`);
  }
  const range = pet.fruit.familyNumberRange;
  if (!Array.isArray(range) || range.length !== 2 || !range.every(Number.isInteger) || range[0] > range[1]) {
    errors.push(`${petKey}: fruit must keep its valid Excel family number range`);
  } else {
    const familyFirstName = pets[key(range[0])]?.name;
    if (pet.fruit.name !== `${familyFirstName}的果实`) {
      errors.push(`${petKey}: fruit name must use family first form ${familyFirstName}`);
    }
  }
}
for (const [petKey, expectedName] of Object.entries(correctedFruitNames)) {
  if (pets[petKey]?.fruit?.name !== expectedName) {
    errors.push(`${petKey}: fruit name must be ${expectedName}`);
  }
}
if (!syncSource.includes('fruit_info["familyNumberRange"][0]') || !syncSource.includes("的果实")) {
  errors.push('Excel sync must generate fruit names from the family first form');
}
if (!legacyFruitUpdaterSource.includes("pets['pet_' + firstNum]?.name")) {
  errors.push('legacy fruit updater must generate fruit names from the family first form');
}
for (const prefix of confirmedOwnedFruitPrefixes) {
  const memberEntry = Object.entries(pets).find(([, pet]) => pet.name === prefix);
  const memberNumber = Number(memberEntry?.[0].replace('pet_', ''));
  const fruitEntry = Object.entries(pets).find(([, pet]) => {
    const range = pet.fruit?.familyNumberRange;
    return range && memberNumber >= range[0] && memberNumber <= range[1];
  });
  if (!fruitEntry) {
    errors.push(`${prefix}: confirmed owned fruit cannot be mapped to a family`);
  } else if (collections.sprite_progress?.[fruitEntry[0]]?.fruit_acquired !== true) {
    errors.push(`${prefix}: confirmed owned fruit must be marked acquired`);
  }
}
if (!collections.sprite_progress?.pet_11?.forms_collected?.includes('燃了鸭')) {
  errors.push('pet_11: 燃了鸭 fruit form must remain collected separately from the family fruit');
}
if (JSON.stringify(pets.pet_7?.fruit?.familyNumberRange) !== JSON.stringify([5, 7])) {
  errors.push('pet_7 fire fruit family range must be [5, 7]');
}
const expectedFruitGroups = {
  starter_gen1: [4, 7, 10], starter_gen2: [155, 158, 161],
  pass_s1: [309, 312], pass_s2: [355, 357], pass_s3: [419, 421],
};
for (const [group, numbers] of Object.entries(expectedFruitGroups)) {
  for (const number of numbers) {
    if (pets[key(number)]?.fruit?.exclusiveGroup !== group) {
      errors.push(`${key(number)} fruit must belong to ${group}`);
    }
  }
}

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
  pet_56: '幽冥眼',
  pet_392: '饮雪狂兽',
  pet_402: '邪眼巨魔',
  pet_411: '珀尔鼬',
  pet_423: '铆钉毛毛',
  pet_424: '徘徊爪爪',
  pet_440: '睡铃雪影娃娃',
};
for (const [petKey, expectedName] of Object.entries(expectedCorrections)) {
  if (pets[petKey]?.name !== expectedName) errors.push(`${petKey}: expected corrected name ${expectedName}`);
}

for (const petKey of ['pet_63', 'pet_64', 'pet_65']) {
  const forms = Object.keys(pets[petKey]?.forms || {});
  const formTask = (tasks[petKey] || []).find(task => task.type === 'confirm_forms');
  if (!forms.includes('象牙球形态') || forms.includes('象牙花形态')
    || !formTask?.requiredForms?.includes('象牙球形态')) {
    errors.push(`${petKey}: must use verified 象牙球形态 calibration`);
  }
}

const frogElements = { pet_427: ['水'], pet_428: ['水'], pet_429: ['水', '武'] };
for (const [petKey, expected] of Object.entries(frogElements)) {
  if (JSON.stringify(pets[petKey]?.element) !== JSON.stringify(expected)) {
    errors.push(`${petKey}: verified frog element calibration mismatch`);
  }
}

if (JSON.stringify(pets.pet_440?.element) !== JSON.stringify([])
  || JSON.stringify(tasks.pet_440) !== JSON.stringify([])
  || Object.keys(pets.pet_440?.forms || {}).join(',') !== 'basic') {
  errors.push('pet_440 must remain a name-only placeholder with empty tasks');
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
  pets: 440,
  tasks: 2192,
  fruitTasks: 108,
  fruitRecords: 168,
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
  additionalFruitRecords: additionalFruits.length,
  totals,
}, null, 2));
