const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const petsPath = path.join(root, 'data', 'pets.json');
const tasksPath = path.join(root, 'data', 'tasks.json');
const chainsPath = path.join(root, 'data', 'evolution-chains.json');

const pets = JSON.parse(fs.readFileSync(petsPath, 'utf8'));
const tasks = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));
const chains = JSON.parse(fs.readFileSync(chainsPath, 'utf8'));

const S3_SHINY = { tagName: '异色', limitedTime: 'S3「铅字幻梦」' };
const CHROMATIC = { tagName: '炫彩' };
const S3_ENCOUNTER = ['S3赛季奇遇·精灵童话'];

const definitions = {
  pet_422: ['蝴蝶陶陶', ['萌'], 'hudietaotao', 'hdtt', true, false],
  pet_423: ['钢耳毛毛', ['萌', '毒'], 'gangermaomao', 'gemm', false, false],
  pet_424: ['绯红爪爪', ['萌', '毒'], 'feihongzhuazhua', 'fhzz', false, true],
  pet_425: ['苞米仔', ['草', '火'], 'baomizai', 'bmz', true, false],
  pet_426: ['炮米花', ['草', '火'], 'paomihua', 'pmh', false, true],
  pet_427: ['十字蝌蚪', ['水', '地'], 'shizikedou', 'szkd', true, false],
  pet_428: ['十字蛙', ['水', '地'], 'shiziwa', 'szw', false, false],
  pet_429: ['深渊蛙', ['水', '地'], 'shenyuanwa', 'syw', false, true],
  pet_430: ['卡波', ['恶'], 'kabo', 'kb', true, false],
  pet_431: ['卡拉波斯', ['恶'], 'kalabosi', 'klbs', false, true],
  pet_432: ['守夜烛', ['火', '光'], 'shouyezhu', 'syz', true, false],
  pet_433: ['流明坎德拉', ['火', '光'], 'liumingkandela', 'lmkdl', false, true],
  pet_434: ['蜜果骸', ['幽', '草'], 'miguohai', 'mgh', true, false],
  pet_435: ['半朽蜜果灵', ['幽', '草'], 'banxiumiguoling', 'bxmgl', false, true],
  pet_436: ['稻草人', ['萌', '武'], 'daocaoren', 'dcr', true, false],
  pet_437: ['稻草守护者', ['萌', '武'], 'daocaoshouhuzhe', 'dcshz', false, true],
  pet_438: ['栗鼠', ['毒', '普通'], 'lishu', 'ls', true, false],
  pet_439: ['壳栗丝鼠', ['毒', '普通'], 'kelisishu', 'klss', false, true],
};

for (const [petKey, [name, element, full, initial, isBase, isShinyFinal]] of Object.entries(definitions)) {
  pets[petKey] = {
    forms: {
      basic: {
        formName: '基础形态',
        obtainMethods: isBase ? S3_ENCOUNTER : [],
      },
    },
    tags: {
      chromatic: CHROMATIC,
      ...(isShinyFinal ? { shiny: S3_SHINY } : {}),
    },
    name,
    element,
    pinyin: { full, initial },
  };
  if (!Array.isArray(tasks[petKey])) tasks[petKey] = [];
}

const chainDefinitions = [
  [182, 'pet_422', ['pet_422', 'pet_423', 'pet_424']],
  [183, 'pet_425', ['pet_425', 'pet_426']],
  [184, 'pet_427', ['pet_427', 'pet_428', 'pet_429']],
  [185, 'pet_430', ['pet_430', 'pet_431']],
  [186, 'pet_432', ['pet_432', 'pet_433']],
  [187, 'pet_434', ['pet_434', 'pet_435']],
  [188, 'pet_436', ['pet_436', 'pet_437']],
  [189, 'pet_438', ['pet_438', 'pet_439']],
];

for (const [chainId, baseSpeciesId, petKeys] of chainDefinitions) {
  const nodes = {};
  petKeys.forEach((petKey, index) => {
    nodes[petKey] = {
      evolvesTo: index === petKeys.length - 1 ? [] : [{
        toSpeciesId: petKeys[index + 1],
        condition: {
          type: 'unknown',
          note: '进化条件待补充',
        },
      }],
    };
  });
  const chain = { chainId, baseSpeciesId, nodes };
  const existingIndex = chains.findIndex(item => item.chainId === chainId || item.baseSpeciesId === baseSpeciesId);
  if (existingIndex >= 0) chains[existingIndex] = chain;
  else chains.push(chain);
}

fs.writeFileSync(petsPath, `${JSON.stringify(pets, null, 2)}\n`);
fs.writeFileSync(tasksPath, `${JSON.stringify(tasks, null, 2)}\n`);
fs.writeFileSync(chainsPath, `${JSON.stringify(chains, null, 2)}\n`);

console.log(JSON.stringify({
  addedPets: Object.keys(definitions).length,
  addedFamilies: chainDefinitions.length,
  range: 'pet_422-pet_439',
}, null, 2));
