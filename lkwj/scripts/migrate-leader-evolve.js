// migrate-leader-evolve.js
// Phase 0-2 进度迁移脚本
// 删除 sprites.json leader form 的 leader_evolve 任务前，同步用户已有进度到 base form
// 用法：node scripts/migrate-leader-evolve.js [--dry-run]
//
// 由于当前 sprite_progress 为空，此脚本保留为安全网。
// 未来若 sprites.json 重新导入或新增精灵时，必须先运行此脚本再执行删除。

const fs = require('fs');
const path = require('path');

const collectionsPath = path.join(__dirname, '..', 'data', 'collections.json');
const spritesPath = path.join(__dirname, '..', 'data', 'sprites.json');

const dryRun = process.argv.includes('--dry-run');

const collections = JSON.parse(fs.readFileSync(collectionsPath, 'utf8'));
const sprites = JSON.parse(fs.readFileSync(spritesPath, 'utf8'));

const progress = collections.sprite_progress || {};
if (Object.keys(progress).length === 0) {
  console.log('sprite_progress 为空，无需迁移。');
  process.exit(0);
}

let migrated = 0;

sprites.forEach(sp => {
  const spProg = progress[String(sp.id)];
  if (!spProg || !spProg.forms) return;

  const baseFormIdx = sp.forms.findIndex(f => f.type === 'base');
  const leaderFormIdx = sp.forms.findIndex(f => f.type === 'leader');
  if (baseFormIdx === -1 || leaderFormIdx === -1) return;

  // 找到 base form 的 leader_evolve task index
  const baseForm = sp.forms[baseFormIdx];
  const baseTaskIdx = baseForm.tasks.findIndex(t => t.type === 'leader_evolve');
  if (baseTaskIdx === -1) return; // base form 没有 leader_evolve（不应发生）

  // 找到 leader form 的 leader_evolve task index
  const leaderForm = sp.forms[leaderFormIdx];
  const leaderTaskIdx = leaderForm.tasks.findIndex(t => t.type === 'leader_evolve');
  if (leaderTaskIdx === -1) return; // 已经删过了

  const fp = spProg.forms[String(leaderFormIdx)];
  if (!fp || !fp.tasks) return;

  const leaderDone = fp.tasks[String(leaderTaskIdx)];
  if (leaderDone) {
    // 同步到 base form
    if (!spProg.forms[String(baseFormIdx)]) spProg.forms[String(baseFormIdx)] = { collected: false, tasks: {} };
    spProg.forms[String(baseFormIdx)].tasks[String(baseTaskIdx)] = true;
    console.log(`迁移: ${sp.name} leader_evolve 进度 → base form`);
    migrated++;
  }

  // 删除 leader form 的 leader_evolve 进度条目
  delete fp.tasks[String(leaderTaskIdx)];
});

console.log(`迁移完成: ${migrated} 条进度同步${dryRun ? ' (dry-run, 未写入)' : ''}`);

if (!dryRun) {
  collections.meta.last_updated = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(collectionsPath, JSON.stringify(collections, null, 2), 'utf8');
  console.log('collections.json 已更新');
}
