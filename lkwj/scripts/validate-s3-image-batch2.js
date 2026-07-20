const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));
const chains = JSON.parse(fs.readFileSync(path.join(root, 'data', 'evolution-chains.json'), 'utf8'));

const expected = {
  pet_440: ['加灵', ['普通', '萌']],
  pet_441: ['加益', ['普通', '萌']],
  pet_442: ['加尔', ['普通', '萌']],
  pet_443: ['黑化加尔', ['普通', '幽']],
  pet_444: ['足尖元件', ['幻', '机械']],
  pet_445: ['离心舞者', ['幻', '机械']],
  pet_446: ['咬咬小子', ['机械']],
  pet_447: ['胡桃王子', ['机械']],
  pet_448: ['不咕钟', ['机械', '幻']],
  pet_449: ['溯源钟', ['机械', '幻']],
  pet_450: ['莫比乌乌', ['龙', '萌']],
  pet_451: ['克莱因龙', ['龙', '萌']],
  pet_452: ['友爱天天', ['普通']],
  pet_453: ['友爱星飞', ['普通']],
  pet_454: ['点点', ['萌']],
  pet_455: ['珀尔翩', ['萌']],
};

const errors = [];
for (const [petKey, [name, element]] of Object.entries(expected)) {
  const pet = pets[petKey];
  if (!pet) {
    errors.push(`${petKey}: missing`);
    continue;
  }
  if (pet.name !== name) errors.push(`${petKey}: expected ${name}, got ${pet.name}`);
  if (JSON.stringify(pet.element) !== JSON.stringify(element)) {
    errors.push(`${petKey} ${name}: element mismatch`);
  }
  if (!Array.isArray(tasks[petKey]) || tasks[petKey].length !== 0) {
    errors.push(`${petKey} ${name}: tasks must remain empty until official task data arrives`);
  }
}

const branchChain = chains.find(item => item.baseSpeciesId === 'pet_440');
if (!branchChain) {
  errors.push('加灵 family chain missing');
} else {
  const first = branchChain.nodes?.pet_440?.evolvesTo || [];
  const branches = branchChain.nodes?.pet_441?.evolvesTo || [];
  if (first.length !== 1 || first[0].toSpeciesId !== 'pet_441') {
    errors.push('加灵 must evolve to 加益');
  }
  const targets = branches.map(item => item.toSpeciesId).sort();
  if (JSON.stringify(targets) !== JSON.stringify(['pet_442', 'pet_443'])) {
    errors.push('加益 must branch to 加尔 and 黑化加尔');
  }
}

for (const baseKey of ['pet_444', 'pet_446', 'pet_448', 'pet_450', 'pet_452', 'pet_454']) {
  const chain = chains.find(item => item.baseSpeciesId === baseKey);
  if (!chain) errors.push(`${baseKey}: chain missing`);
}

for (const shinyKey of ['pet_445', 'pet_447']) {
  if (pets[shinyKey]?.tags?.shiny?.limitedTime !== 'S3通行证') {
    errors.push(`${shinyKey}: S3 pass shiny tag missing`);
  }
}

for (const petKey of Object.keys(expected)) {
  const chain = chains.find(item => item.nodes?.[petKey]);
  for (const evolution of chain?.nodes?.[petKey]?.evolvesTo || []) {
    if (evolution.condition?.type !== 'unknown') {
      errors.push(`${petKey}: evolution condition must remain unknown`);
    }
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  pets: Object.keys(expected).length,
  families: 7,
  passShinyFinals: 2,
  provisionalIds: 'pet_440-pet_455',
}, null, 2));
