const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const petsPath = path.join(root, 'data', 'pets.json');
const tasksPath = path.join(root, 'data', 'tasks.json');
const chainsPath = path.join(root, 'data', 'evolution-chains.json');

const pets = JSON.parse(fs.readFileSync(petsPath, 'utf8'));
const tasks = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));
const chains = JSON.parse(fs.readFileSync(chainsPath, 'utf8'));

const S3_PASS_SHINY = { tagName: '异色', limitedTime: 'S3通行证' };

// 官方家族介绍图未展示图鉴编号。以下 pet_440-pet_455 仅按当前数据连续编号暂录，
// 等后续官方编号资料到齐后统一核对；名称、元素和进化结构只来自本批图片。
const definitions = {
  pet_440: ['加灵', ['普通', '萌'], 'jialing', 'jl', []],
  pet_441: ['加益', ['普通', '萌'], 'jiayi', 'jy', []],
  pet_442: ['加尔', ['普通', '萌'], 'jiaer', 'je', []],
  pet_443: ['黑化加尔', ['普通', '幽'], 'heihuajiaer', 'hhje', []],
  pet_444: ['足尖元件', ['幻', '机械'], 'zujianyuanjian', 'zjyj', ['S3通行证']],
  pet_445: ['离心舞者', ['幻', '机械'], 'lixinwuzhe', 'lxwz', []],
  pet_446: ['咬咬小子', ['机械'], 'yaoyaoxiaozi', 'yyxz', ['S3通行证']],
  pet_447: ['胡桃王子', ['机械'], 'hutaowangzi', 'htwz', []],
  pet_448: ['不咕钟', ['机械', '幻'], 'buguzhong', 'bgz', []],
  pet_449: ['溯源钟', ['机械', '幻'], 'suyuanzhong', 'syz', []],
  pet_450: ['莫比乌乌', ['龙', '萌'], 'mobiwuwu', 'mbww', []],
  pet_451: ['克莱因龙', ['龙', '萌'], 'kelaiyinlong', 'klyl', []],
  pet_452: ['友爱天天', ['普通'], 'youaitiantian', 'yatt', []],
  pet_453: ['友爱星飞', ['普通'], 'youaixingfei', 'yaxf', []],
  pet_454: ['点点', ['萌'], 'diandian', 'dd', []],
  pet_455: ['珀尔翩', ['萌'], 'poerpian', 'pep', []],
};

const shinyFinals = new Set(['pet_445', 'pet_447']);

for (const [petKey, [name, element, full, initial, obtainMethods]] of Object.entries(definitions)) {
  pets[petKey] = {
    forms: {
      basic: {
        formName: '基础形态',
        obtainMethods,
      },
    },
    tags: shinyFinals.has(petKey) ? { shiny: S3_PASS_SHINY } : {},
    name,
    element,
    pinyin: { full, initial },
  };
  if (!Array.isArray(tasks[petKey])) tasks[petKey] = [];
}

const unknownCondition = () => ({
  type: 'unknown',
  note: '进化条件待补充',
});

const chainDefinitions = [
  {
    chainId: 190,
    baseSpeciesId: 'pet_440',
    nodes: {
      pet_440: { evolvesTo: [{ toSpeciesId: 'pet_441', condition: unknownCondition() }] },
      pet_441: {
        evolvesTo: [
          { toSpeciesId: 'pet_442', condition: unknownCondition() },
          { toSpeciesId: 'pet_443', condition: unknownCondition() },
        ],
      },
      pet_442: { evolvesTo: [] },
      pet_443: { evolvesTo: [] },
    },
  },
  [191, 'pet_444', ['pet_444', 'pet_445']],
  [192, 'pet_446', ['pet_446', 'pet_447']],
  [193, 'pet_448', ['pet_448', 'pet_449']],
  [194, 'pet_450', ['pet_450', 'pet_451']],
  [195, 'pet_452', ['pet_452', 'pet_453']],
  [196, 'pet_454', ['pet_454', 'pet_455']],
].map(item => {
  if (!Array.isArray(item)) return item;
  const [chainId, baseSpeciesId, petKeys] = item;
  const nodes = {};
  petKeys.forEach((petKey, index) => {
    nodes[petKey] = {
      evolvesTo: index === petKeys.length - 1
        ? []
        : [{ toSpeciesId: petKeys[index + 1], condition: unknownCondition() }],
    };
  });
  return { chainId, baseSpeciesId, nodes };
});

for (const chain of chainDefinitions) {
  const existingIndex = chains.findIndex(item =>
    item.chainId === chain.chainId || item.baseSpeciesId === chain.baseSpeciesId);
  if (existingIndex >= 0) chains[existingIndex] = chain;
  else chains.push(chain);
}

fs.writeFileSync(petsPath, `${JSON.stringify(pets, null, 2)}\n`);
fs.writeFileSync(tasksPath, `${JSON.stringify(tasks, null, 2)}\n`);
fs.writeFileSync(chainsPath, `${JSON.stringify(chains, null, 2)}\n`);

console.log(JSON.stringify({
  addedPets: Object.keys(definitions).length,
  addedFamilies: chainDefinitions.length,
  provisionalRange: 'pet_440-pet_455',
  shinyFinals: [...shinyFinals],
}, null, 2));
