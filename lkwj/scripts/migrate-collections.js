#!/usr/bin/env node
/**
 * migrate-collections.js
 * 重写 collections.json 格式 + 回填 pets.json tags.shiny 的 limitedTime
 *
 * 变更：
 * - sprite_progress: 整数 ID → pet_N，form index → 语义 key
 * - 新增 shiny_progress
 * - 旧 items[] → 提取 limitedTime 到 pets.json
 * - 保留非宠物类 items
 */

const fs = require('fs');
const path = require('path');

const COLL_FILE = path.join(__dirname, '..', 'data', 'collections.json');
const PETS_FILE = path.join(__dirname, '..', 'data', 'pets.json');
const SPRITES_FILE = path.join(__dirname, '..', 'data', 'sprites.json');
const OUTPUT_COLL = path.join(__dirname, '..', 'data', 'collections.json');
const OUTPUT_PETS = path.join(__dirname, '..', 'data', 'pets.json');

const collections = JSON.parse(fs.readFileSync(COLL_FILE, 'utf8'));
const pets = JSON.parse(fs.readFileSync(PETS_FILE, 'utf8'));
const sprites = JSON.parse(fs.readFileSync(SPRITES_FILE, 'utf8'));

// ====== Build form index → semantic key mapping ======
const formIndexMap = {}; // { spriteId: { formIndex: semanticKey } }
sprites.forEach(sprite => {
  const map = {};
  let variantCount = 0;
  sprite.forms.forEach((form, fi) => {
    if (form.type === 'leader') {
      // Leader forms are not in new model → skip
      return;
    }
    const petKey = `pet_${sprite.id}`;
    const pet = pets[petKey];
    if (!pet) return;

    if (form.label === '基础形态') {
      map[fi] = 'basic';
    } else {
      // Find matching form key in pets.json
      const formKeys = Object.keys(pet.forms).filter(k => k !== 'basic');
      // Try to match by formName
      for (const fk of formKeys) {
        if (pet.forms[fk].formName === form.label && !Object.values(map).includes(fk)) {
          map[fi] = fk;
          break;
        }
      }
      // If no match by name, assign variant_N
      if (!map[fi]) {
        variantCount++;
        map[fi] = `variant_${variantCount}`;
      }
    }
  });
  formIndexMap[sprite.id] = map;
});

// ====== Build sprite name → pet key mapping ======
const nameToPetKey = {};
Object.entries(pets).forEach(([key, pet]) => {
  nameToPetKey[pet.name] = key;
});

// ====== Migrate sprite_progress ======
const oldProgress = collections.sprite_progress || {};
const newSpriteProgress = {};
let progressStats = { migrated: 0, tasks: 0, forms: 0 };

Object.entries(oldProgress).forEach(([oldId, progress]) => {
  const newKey = `pet_${oldId}`;
  const newEntry = {};

  // Form collected status
  if (progress.forms) {
    const formMap = formIndexMap[parseInt(oldId)] || {};
    const formsCollected = [];
    Object.entries(progress.forms).forEach(([fi, fp]) => {
      const formKey = formMap[parseInt(fi)];
      if (formKey && fp.collected) {
        formsCollected.push(formKey);
        progressStats.forms++;
      }
    });
    if (formsCollected.length > 0) {
      newEntry.forms_collected = formsCollected;
    }

    // Task progress (only from form[0] = base form)
    const baseFormProgress = progress.forms['0'];
    if (baseFormProgress && baseFormProgress.tasks) {
      const taskProgress = {};
      Object.entries(baseFormProgress.tasks).forEach(([ti, done]) => {
        if (done) {
          taskProgress[ti] = true;
          progressStats.tasks++;
        }
      });
      if (Object.keys(taskProgress).length > 0) {
        newEntry.tasks = taskProgress;
      }
    }
  }

  // Pet collected status
  if (progress.collected) {
    newEntry.collected = true;
  }

  if (Object.keys(newEntry).length > 0) {
    newSpriteProgress[newKey] = newEntry;
    progressStats.migrated++;
  }
});

// ====== Extract shiny progress from old items[] ======
const oldItems = collections.items || [];
const shinyProgress = {};
const shinyLimitedTime = {}; // petKey → limitedTime mapping for backfill
let shinyStats = { completed: 0, total: 0 };

oldItems.forEach(item => {
  if (item.category !== '异色炫彩' && item.category !== '異色炫彩') return;

  // Try to map item name to pet
  // Item names can be like "机械方" or "粉星仔（形态一）"
  const baseName = item.name.replace(/（.+）$/, ''); // strip form suffix
  const petKey = nameToPetKey[baseName];

  if (petKey) {
    shinyStats.total++;
    if (item.status === '已完成') {
      shinyProgress[petKey] = true;
      shinyStats.completed++;
    }

    // Track limitedTime for backfill
    if (item.limited_status && item.limited_status !== '可获取') {
      if (!shinyLimitedTime[petKey]) {
        shinyLimitedTime[petKey] = item.limited_status;
      }
    }
  }
});

// ====== Backfill limitedTime into pets.json ======
let backfillCount = 0;
Object.entries(shinyLimitedTime).forEach(([petKey, limitedTime]) => {
  if (pets[petKey] && pets[petKey].tags && pets[petKey].tags.shiny) {
    pets[petKey].tags.shiny.limitedTime = limitedTime;
    backfillCount++;
  }
});

// ====== Build new collections.json ======
const newCollections = {
  meta: collections.meta || { last_updated: new Date().toISOString().slice(0, 10), game: '洛克王国世界' },
  categories: collections.categories || {},
  items: oldItems.filter(item => item.category !== '异色炫彩' && item.category !== '異色炫彩'),
  sprite_progress: newSpriteProgress,
  shiny_progress: shinyProgress,
  activities: collections.activities || [],
};

// Preserve regions if present
if (collections.regions) {
  newCollections.regions = collections.regions;
}

// ====== Write outputs ======
// Backup original collections first
const backupFile = COLL_FILE.replace('.json', '-backup.json');
fs.writeFileSync(backupFile, JSON.stringify(collections, null, 2), 'utf8');

fs.writeFileSync(OUTPUT_COLL, JSON.stringify(newCollections, null, 2), 'utf8');
fs.writeFileSync(OUTPUT_PETS, JSON.stringify(pets, null, 2), 'utf8');

// ====== Stats ======
console.log('=== migrate-collections.js ===');
console.log(`Sprite progress entries migrated: ${progressStats.migrated}`);
console.log(`Tasks migrated: ${progressStats.tasks}`);
console.log(`Forms collected: ${progressStats.forms}`);
console.log(`Shiny progress: ${shinyStats.completed}/${shinyStats.total}`);
console.log(`LimitedTime backfilled to pets.json: ${backfillCount}`);
console.log(`Non-pet items preserved: ${newCollections.items.length}`);
console.log(`Backup: ${backupFile}`);
console.log(`Output collections: ${OUTPUT_COLL}`);
console.log(`Output pets (updated): ${OUTPUT_PETS}`);
