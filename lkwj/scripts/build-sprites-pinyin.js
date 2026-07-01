// build-sprites-pinyin.js
// 为 sprites.json 中每条精灵生成 pinyin 字段（全拼 + 首字母）
// 用法：node scripts/build-sprites-pinyin.js

const fs = require('fs');
const path = require('path');
const { pinyin } = require('pinyin-pro');

const spritesPath = path.join(__dirname, '..', 'data', 'sprites.json');

// 多音字修正表（游戏常见名）
const polyphoneFix = {
  '乐': 'yue',
  '重': 'chong',
  '长': 'chang',
  '传': 'chuan',
  '行': 'xing',
  '了': 'le',
  '的': 'de',
  '地': 'di',
  '会': 'hui',
  '都': 'dou',
};

const sprites = JSON.parse(fs.readFileSync(spritesPath, 'utf8'));

sprites.forEach(sp => {
  // 对每个字逐个查 pinyin，应用多音字修正
  const chars = sp.name.split('');
  const fullPinyin = chars.map(ch => {
    if (polyphoneFix[ch]) return polyphoneFix[ch];
    const py = pinyin(ch, { toneType: 'none', type: 'array' });
    return py[0] || ch;
  });

  sp.pinyin = {
    full: fullPinyin.join(''),
    initial: fullPinyin.map(p => p[0]).join(''),
  };
});

fs.writeFileSync(spritesPath, JSON.stringify(sprites, null, 2), 'utf8');

console.log(`已为 ${sprites.length} 只精灵生成 pinyin 字段`);
console.log('样例:');
sprites.slice(0, 5).forEach(sp => {
  console.log(`  ${sp.name} → ${sp.pinyin.full} / ${sp.pinyin.initial}`);
});
console.log('搜索效果验证:');
const testQueries = ['jxff', 'jixiefangfang', '机械', 'dim', 'huoshen'];
testQueries.forEach(q => {
  const matches = sprites.filter(sp => {
    const t = q.toLowerCase();
    return sp.name.includes(q) ||
      sp.pinyin.full.includes(t) ||
      sp.pinyin.initial.includes(t) ||
      sp.element.includes(q);
  }).slice(0, 3).map(s => s.name);
  console.log(`  "${q}" → ${matches.join(', ')}${matches.length >= 3 ? '...' : ''}`);
});
