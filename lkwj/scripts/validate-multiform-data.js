const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(root, 'data', 'tasks.json'), 'utf8'));

const errors = [];

function formKeysForTask(pet) {
  return Object.keys(pet.forms || {}).filter((key) => key !== 'basic' && key !== 'leader');
}

for (const [petKey, taskList] of Object.entries(tasks)) {
  const pet = pets[petKey];
  if (!pet) {
    errors.push(`${petKey}: tasks exist without pet definition`);
    continue;
  }

  for (const task of taskList) {
    if (task.type !== 'confirm_forms') continue;

    if (!Array.isArray(task.requiredForms)) {
      errors.push(`${petKey} ${pet.name}: confirm_forms missing requiredForms`);
      continue;
    }

    if (task.requiredForms.length < task.count) {
      errors.push(`${petKey} ${pet.name}: requiredForms length ${task.requiredForms.length} < count ${task.count}`);
    }

    for (const formKey of task.requiredForms) {
      if (!pet.forms || !pet.forms[formKey]) {
        errors.push(`${petKey} ${pet.name}: requiredForms references missing form ${formKey}`);
      }
      if (formKey === 'basic' || formKey === 'leader') {
        errors.push(`${petKey} ${pet.name}: requiredForms must not include ${formKey}`);
      }
    }
  }
}

const duckTask = (tasks.pet_11 || []).find((task) => task.type === 'confirm_forms');
if (!duckTask || JSON.stringify(duckTask.requiredForms) !== JSON.stringify(['蓬松的样子', '紧实的样子'])) {
  errors.push('pet_11 鸭吉吉: requiredForms must be 蓬松的样子 + 紧实的样子');
}

const dreamForms = formKeysForTask(pets.pet_58 || {});
if (JSON.stringify(dreamForms) !== JSON.stringify(['穿旧睡衣的样子', '穿星星睡衣的样子'])) {
  errors.push('pet_58 梦悠悠: forms must be 穿旧睡衣的样子 + 穿星星睡衣的样子');
}
const dreamTask = (tasks.pet_58 || []).find((task) => task.type === 'confirm_forms');
if (!dreamTask
  || dreamTask.count !== 2
  || dreamTask.desc !== '确认2种不同样子的梦悠悠'
  || JSON.stringify(dreamTask.requiredForms) !== JSON.stringify(dreamForms)) {
  errors.push('pet_58 梦悠悠: confirm_forms task must require both pajama forms');
}

const dreamBaseForms = formKeysForTask(pets.pet_57 || {});
const dreamBaseTask = (tasks.pet_57 || []).find((task) => task.type === 'confirm_forms');
if (JSON.stringify(dreamBaseForms) !== JSON.stringify(['穿旧睡衣的样子', '穿星星睡衣的样子'])
  || !dreamBaseTask
  || dreamBaseTask.count !== 2
  || JSON.stringify(dreamBaseTask.requiredForms) !== JSON.stringify(dreamBaseForms)) {
  errors.push('pet_57 梦游: must contain both pajama forms and a count-2 confirm_forms task');
}

const regionalForms = ['沙地附近的样子', '草地附近的样子', '雪山附近的样子', '火山附近的样子'];
for (const petKey of ['pet_44', 'pet_45', 'pet_46']) {
  const formKeys = formKeysForTask(pets[petKey] || {});
  const formTask = (tasks[petKey] || []).find((task) => task.type === 'confirm_forms');
  if (JSON.stringify(formKeys) !== JSON.stringify(regionalForms)
    || !formTask
    || formTask.count !== 3
    || JSON.stringify(formTask.requiredForms) !== JSON.stringify(regionalForms)) {
    errors.push(`${petKey}: must support any 3 of the 4 regional forms`);
  }
}

const moleForms = formKeysForTask(pets.pet_279 || {});
for (const wrongForm of ['单只海葵的样子', '双只海葵的样子']) {
  if (moleForms.includes(wrongForm)) {
    errors.push(`pet_279 遁地鼠: must not contain 加油蟹 form ${wrongForm}`);
  }
}

const moleTask = (tasks.pet_279 || []).find((task) => task.type === 'confirm_forms');
const expectedMoleForms = ['储水时的样子', '枯水期的样子'];
if (!moleTask
  || moleTask.count !== 2
  || moleTask.requiredForms.length !== 2
  || expectedMoleForms.some((formKey) => !moleTask.requiredForms.includes(formKey))) {
  errors.push('pet_279 遁地鼠: requiredForms must contain 储水时的样子 + 枯水期的样子');
}

const coneSweetForms = formKeysForTask(pets.pet_234 || {});
if (coneSweetForms.length > 0) {
  errors.push(`pet_234 脆筒甜甜: must not contain multiform entries (${coneSweetForms.join(', ')})`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

const confirmForms = Object.values(tasks).flat().filter((task) => task.type === 'confirm_forms').length;
const multiformPets = Object.values(pets).filter((pet) => formKeysForTask(pet).length > 0).length;

console.log(JSON.stringify({ confirmForms, multiformPets }, null, 2));
