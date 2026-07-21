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

function luminance(hex) {
  const channels = hex.slice(1).match(/.{2}/g).map(part => parseInt(part, 16) / 255)
    .map(value => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(foreground, background) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

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
  } else if (contrast(foreground, background) < 4.5) {
    errors.push(`${element}: text contrast below 4.5:1`);
  }
}

for (const tag of ['boss', 'shiny', 'chromatic']) {
  const rule = selectorRule(`.pet-status-badge.tag-${tag}`);
  const background = colorFrom(rule, 'background');
  const foreground = colorFrom(rule, 'color');
  if (!background || !foreground) {
    errors.push(`${tag}: missing independent background or text color`);
  } else if (foreground.toLowerCase() !== '#ffffff') {
    errors.push(`${tag}: badge text must be white`);
  } else if (contrast(foreground, background) < 4.5) {
    errors.push(`${tag}: text contrast below 4.5:1`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ elements: elements.length, statusTags: 3, minContrast: 4.5 }, null, 2));
