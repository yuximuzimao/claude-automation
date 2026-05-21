#!/usr/bin/env node
/**
 * migrate-to-tasks.js
 * 从 sprites.json 提取任务定义 → tasks.json
 *
 * 规则：
 * - 仅提取 base form (forms[0]) 的任务（form-independent）
 * - desc 去除宠物名
 * - skill 类解析 skillName + count
 * - capture20 → fruit
 * - desc 字符串保留，不强制原子化
 */

const fs = require('fs');
const path = require('path');

const SPRITES_FILE = path.join(__dirname, '..', 'data', 'sprites.json');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'tasks.json');

const sprites = JSON.parse(fs.readFileSync(SPRITES_FILE, 'utf8'));

// ====== Strip pet name from desc ======
function stripPetName(desc, petName) {
  // Remove pet name from desc
  // "捕捉1只迪莫" → "捕捉1只"
  // "捕捉1只了不起天分的迪莫" → "捕捉1只了不起天分的"
  // "使用闪光1次" → "使用闪光1次" (no pet name in skill descs)
  // "与迪莫的亲密度达到5级" → "亲密度达到5级"
  // "获得魔力猫命定勇者奖牌" → "获得命定勇者奖牌"
  let result = desc;

  // Replace pet name
  if (result.includes(petName)) {
    result = result.replace(petName, '');
  }

  // Clean up
  result = result.replace(/\s+/g, '');           // remove spaces
  result = result.replace(/^与的/, '');           // leftover from "与{N}的..."
  result = result.replace(/^使成功/, '成功');      // "使成功进化一次" → "成功进化一次"
  result = result.replace(/^将进化为/, '进化为');   // "将进化为首领形态" → "进化为首领形态"

  return result;
}

// ====== Parse skill task ======
function parseSkillTask(desc, petName) {
  // "使用{N}技能名{N}次" → skillName, count
  // "使用闪光1次" → skillName="闪光", count=1
  // "使用龙卷风3次" → skillName="龙卷风", count=3

  const stripped = stripPetName(desc, petName);

  // Pattern: 使用{skillName}{count}次
  const match = stripped.match(/^使用(.+?)(\d+)次$/);
  if (!match) {
    return { skillName: desc, count: 1, _parse_error: true };
  }

  return {
    desc: '使用',
    skillName: match[1],
    count: parseInt(match[2], 10),
  };
}

// ====== Main ======
const tasks = {};
const stats = {
  totalPets: 0,
  totalTasks: 0,
  skippedNoTasks: 0,
  typeDistribution: {},
};

sprites.forEach((sprite) => {
  const petKey = `pet_${sprite.id}`;
  const baseForm = sprite.forms[0]; // Only base form tasks

  if (!baseForm || !baseForm.tasks || baseForm.tasks.length === 0) {
    stats.skippedNoTasks++;
    return;
  }

  stats.totalPets++;
  const petTasks = [];

  baseForm.tasks.forEach((task) => {
    stats.totalTasks++;
    const type = task.type === 'capture20' ? 'fruit' : task.type;
    stats.typeDistribution[type] = (stats.typeDistribution[type] || 0) + 1;

    const newTask = { type };

    switch (type) {
      case 'skill': {
        const parsed = parseSkillTask(task.desc, sprite.name);
        newTask.desc = parsed.desc;
        newTask.skillName = parsed.skillName;
        newTask.count = parsed.count;
        if (parsed._parse_error) {
          newTask._parse_error = true;
          newTask._original_desc = task.desc;
        }
        break;
      }

      case 'capture':
      case 'capture_gifted':
      case 'capture_shiny':
      case 'fruit':
      case 'evolve':
      case 'leader_evolve':
      case 'destined_hero':
      case 'affection':
      case 'confirm_forms':
        newTask.desc = stripPetName(task.desc, sprite.name);
        break;

      default:
        newTask.desc = stripPetName(task.desc, sprite.name);
        newTask._unknown_type = true;
    }

    petTasks.push(newTask);
  });

  if (petTasks.length > 0) {
    tasks[petKey] = petTasks;
  }
});

fs.writeFileSync(OUTPUT_FILE, JSON.stringify(tasks, null, 2), 'utf8');

console.log('=== migrate-to-tasks.js ===');
console.log(`Pets with tasks: ${stats.totalPets}`);
console.log(`Total tasks: ${stats.totalTasks}`);
console.log(`Skipped (no tasks): ${stats.skippedNoTasks}`);
console.log(`\nTask type distribution:`);
Object.entries(stats.typeDistribution).sort((a, b) => b[1] - a[1]).forEach(([type, count]) => {
  console.log(`  ${type}: ${count}`);
});
console.log(`\nOutput: ${OUTPUT_FILE}`);
