const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const pets = JSON.parse(fs.readFileSync(path.join(root, 'data', 'pets.json'), 'utf8'));
const errors = [];

function selectorRule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return html.match(new RegExp(`(?:^|[}\\n])\\s*${escaped}\\s*\\{([^}]*)\\}`))?.[1] || '';
}

function colorFrom(rule, property) {
  return rule.match(new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*(#[0-9a-fA-F]{6})`))?.[1];
}

const officialElementColors = {
  草: '#4ebc73', 水: '#62a8ff', 火: '#df561e', 电: '#e5ca00', 毒: '#ba62e0', 幻: '#9ca9ff',
  冰: '#63aeda', 武: '#ff9531', 萌: '#ff7cb1', 光: '#4fc0ff', 龙: '#e84a60', 机械: '#24b9a3',
  幽: '#9446ec', 恶: '#cf467a', 虫: '#9ece21', 普通: '#3f89b4', 翼: '#3ec7ca', 地: '#987d44',
};
const statusColors = { boss: '#dc2626', shiny: '#a16207', chromatic: '#7c3aed' };

if (!/function\s+renderElementBadges\s*\(/.test(html)
  || !/class="element-badge el-\$\{/.test(html)) {
  errors.push('elements must render as independent badges');
}
if (!/function\s+renderPetBadges\s*\(/.test(html)
  || !/renderPetBadges\(pet\)/.test(html)
  || !/renderPetBadges\(group\.pet,\s*false\)/.test(html)) {
  errors.push('sprite and multiform headers must share badge rendering');
}
if (!/elements:\s*pet\.element\s*\|\|\s*\[\]/.test(html)
  || !/renderElementBadges\(s\.elements\)/.test(html)) {
  errors.push('shiny list must split dual elements into independent badges');
}
if (/<span class="se\s+el-/.test(html)) {
  errors.push('headers must not wrap elements and tags in the old shared badge');
}

const groupRule = selectorRule('.pet-badges');
if (!/background\s*:\s*transparent/.test(groupRule)) {
  errors.push('badge group must have no shared background');
}

const elements = [...new Set(Object.values(pets).flatMap(pet => pet.element || []))].sort();
for (const element of elements) {
  const rule = selectorRule(`.element-badge.el-${element}`);
  const background = colorFrom(rule, 'background');
  const foreground = colorFrom(rule, 'color');
  if (!background || !foreground) {
    errors.push(`${element}: missing independent background or text color`);
  } else if (foreground.toLowerCase() !== '#ffffff') {
    errors.push(`${element}: badge text must be white`);
  } else if (background.toLowerCase() !== officialElementColors[element]) {
    errors.push(`${element}: background must use the official original color`);
  }
}

for (const tag of ['boss', 'shiny', 'chromatic']) {
  const rule = selectorRule(`.pet-status-badge.tag-${tag}`);
  const foreground = colorFrom(rule, 'color');
  if (!/background\s*:\s*transparent/.test(rule) || !/border\s*:\s*1px\s+solid\s+currentColor/.test(rule)) {
    errors.push(`${tag}: status tag must use a transparent outlined style`);
  } else if (!foreground || foreground.toLowerCase() !== statusColors[tag]) {
    errors.push(`${tag}: status tag must use its vivid semantic text color`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ elements: elements.length, statusTags: 3, palette: 'official-elements-with-outlined-status' }, null, 2));
