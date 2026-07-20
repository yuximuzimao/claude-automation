const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const petsPath = path.join(root, 'data', 'pets.json');
const tasksPath = path.join(root, 'data', 'tasks.json');
const chainsPath = path.join(root, 'data', 'evolution-chains.json');

const pets = JSON.parse(fs.readFileSync(petsPath, 'utf8'));
const tasks = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));
const chains = JSON.parse(fs.readFileSync(chainsPath, 'utf8'));

// 本批图片未展示正式图鉴编号。pet_456-pet_485 仅作为当前连续稳定 ID 暂录，
// 等全部图片处理完后再通过最新 Excel 统一核对编号、任务和进化条件。
const definitions = {
  pet_456: ['霹雳宝宝', ['电'], 'pilibaobao', 'plbb'],
  pet_457: ['雷鸣小子', ['电'], 'leimingxiaozi', 'lmxz'],
  pet_458: ['雷神之子', ['电'], 'leishenzhizi', 'lszz'],
  pet_459: ['芽眼魔', ['恶', '水'], 'yayanmo', 'yym'],
  pet_460: ['叶眼魔', ['恶', '水'], 'yeyanmo', 'yym'],
  pet_461: ['障眼魔', ['恶', '水'], 'zhangyanmo', 'zym'],
  pet_462: ['烈钻鸟', ['火', '翼'], 'liezuanniao', 'lzn'],
  pet_463: ['长尾火鸟', ['火', '翼'], 'changweihuoniao', 'cwhn'],
  pet_464: ['火羽', ['火', '翼'], 'huoyu', 'hy'],
  pet_465: ['叮叮卯', ['机械', '虫'], 'dingdingmao', 'ddm'],
  pet_466: ['飞飞钥', ['机械', '虫'], 'feifeiyao', 'ffy'],
  pet_467: ['觅觅蝠', ['翼'], 'mimifu', 'mmf'],
  pet_468: ['翻翻蝠', ['翼'], 'fanfanfu', 'fff'],
  pet_469: ['夜游魔', ['翼', '恶'], 'yeyoumo', 'yym'],
  pet_470: ['火豆丁', ['火'], 'huodouding', 'hdd'],
  pet_471: ['火蛮人', ['火'], 'huomanren', 'hmr'],
  pet_472: ['火巨人', ['火'], 'huojuren', 'hjr'],
  pet_473: ['星云旅者', ['翼', '幻'], 'xingyunlvzhe', 'xylz'],
  pet_474: ['森豆丁', ['草'], 'sendouding', 'sdd'],
  pet_475: ['森蛮人', ['草'], 'senmanren', 'smr'],
  pet_476: ['森巨人', ['草'], 'senjuren', 'sjr'],
  pet_477: ['雪灵兽', ['冰'], 'xuelingshou', 'xls'],
  pet_478: ['幻雪兽', ['冰'], 'huanxueshou', 'hxs'],
  pet_479: ['饮雪狂兽', ['冰'], 'yinxuekuangshou', 'yxks'],
  pet_480: ['瑰眼仔', ['恶', '虫'], 'guiyanzai', 'gyz'],
  pet_481: ['耳翎瑰魅', ['恶', '虫'], 'erlingguimei', 'elgm'],
  pet_482: ['邪眼巨魔', ['恶', '虫'], 'xieyanjumo', 'xyjm'],
  pet_483: ['碎晶蝎', ['恶', '地'], 'suijingxie', 'sjx'],
  pet_484: ['晶尾蝎', ['恶', '地'], 'jingweixie', 'jwx'],
  pet_485: ['蝎子王', ['恶', '地'], 'xieziwang', 'xzw'],
};

for (const [petKey, [name, element, full, initial]] of Object.entries(definitions)) {
  pets[petKey] = {
    forms: {
      basic: {
        formName: '基础形态',
        obtainMethods: [],
      },
    },
    tags: {},
    name,
    element,
    pinyin: { full, initial },
  };
  if (!Array.isArray(tasks[petKey])) tasks[petKey] = [];
}

function addForm(petKey, formKey) {
  if (!pets[petKey]) throw new Error(`${petKey} missing while adding form ${formKey}`);
  if (!pets[petKey].forms) pets[petKey].forms = {};
  if (!pets[petKey].forms[formKey]) {
    pets[petKey].forms[formKey] = {
      formName: formKey,
      obtainMethods: [],
    };
  }
}

addForm('pet_57', '穿星星睡衣的样子');
addForm('pet_58', '穿星星睡衣的样子');
for (const petKey of ['pet_44', 'pet_45', 'pet_46']) {
  addForm(petKey, '火山附近的样子');
}

const unknownCondition = () => ({
  type: 'unknown',
  note: '进化条件待补充',
});

const chainDefinitions = [
  [197, 'pet_456', ['pet_456', 'pet_457', 'pet_458']],
  [198, 'pet_459', ['pet_459', 'pet_460', 'pet_461']],
  [199, 'pet_462', ['pet_462', 'pet_463', 'pet_464']],
  [200, 'pet_465', ['pet_465', 'pet_466']],
  [201, 'pet_467', ['pet_467', 'pet_468', 'pet_469']],
  [202, 'pet_470', ['pet_470', 'pet_471', 'pet_472']],
  [203, 'pet_473', ['pet_473']],
  [204, 'pet_474', ['pet_474', 'pet_475', 'pet_476']],
  [205, 'pet_477', ['pet_477', 'pet_478', 'pet_479']],
  [206, 'pet_480', ['pet_480', 'pet_481', 'pet_482']],
  [207, 'pet_483', ['pet_483', 'pet_484', 'pet_485']],
];

for (const [chainId, baseSpeciesId, petKeys] of chainDefinitions) {
  const nodes = {};
  petKeys.forEach((petKey, index) => {
    nodes[petKey] = {
      evolvesTo: index === petKeys.length - 1
        ? []
        : [{
          toSpeciesId: petKeys[index + 1],
          condition: unknownCondition(),
        }],
    };
  });
  const chain = { chainId, baseSpeciesId, nodes };
  const existingIndex = chains.findIndex(item =>
    item.chainId === chainId || item.baseSpeciesId === baseSpeciesId);
  if (existingIndex >= 0) chains[existingIndex] = chain;
  else chains.push(chain);
}

fs.writeFileSync(petsPath, `${JSON.stringify(pets, null, 2)}\n`);
fs.writeFileSync(tasksPath, `${JSON.stringify(tasks, null, 2)}\n`);
fs.writeFileSync(chainsPath, `${JSON.stringify(chains, null, 2)}\n`);

console.log(JSON.stringify({
  addedPets: Object.keys(definitions).length,
  addedFamilies: chainDefinitions.length,
  provisionalRange: 'pet_456-pet_485',
  addedForms: {
    梦游家族: 1,
    丢丢家族: 3,
  },
}, null, 2));
