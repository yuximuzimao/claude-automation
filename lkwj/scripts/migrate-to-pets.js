#!/usr/bin/env node
/**
 * migrate-to-pets.js
 * 从 sprites.json 迁移到 pets.json
 *
 * 转换规则（来自修正规则.rtf）：
 * - ID: integer → "pet_N" key
 * - element: string → array
 * - forms: array indices → semantic keys (basic/spring/summer/autumn/winter/molting/variant_N)
 * - leader form → tags.boss (不作为 form)
 * - capture_shiny task → tags.shiny
 * - acquire 含"进化" → 不进 obtainMethods（进化来源进 evolution-chains）
 */

const fs = require('fs');
const path = require('path');

const SPRITES_FILE = path.join(__dirname, '..', 'data', 'sprites.json');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'pets.json');

const sprites = JSON.parse(fs.readFileSync(SPRITES_FILE, 'utf8'));

// ====== Semantic form key mapping ======

function mapFormLabelToKey(label, petName) {
  // Remove pet name prefix from label, leaving just the variant description
  // e.g. "雪绒鸟（春天的样子）" → "春天的样子"
  // e.g. "化蝶（幽冥眼的样子）" → "幽冥眼的样子"
  let variant = label;
  if (label.startsWith(petName + '（')) {
    variant = label.slice(petName.length + 1, -1); // strip "{name}（" and "）"
  } else if (label.startsWith(petName)) {
    variant = label.slice(petName.length);
  }

  // --- Clear semantic patterns (auto-detectable) ---

  // Seasonal
  if (variant === '春天的样子') return { key: 'spring', todoRename: false };
  if (variant === '夏天的样子') return { key: 'summer', todoRename: false };
  if (variant === '秋天的样子') return { key: 'autumn', todoRename: false };
  if (variant === '冬天的样子') return { key: 'winter', todoRename: false };

  // Molting
  if (variant === '蜕皮时的样子') return { key: 'molting', todoRename: false };

  // Numbered variants (形态1, 形态2, ...)
  const variantMatch = variant.match(/^形态(\d+)$/);
  if (variantMatch) return { key: `variant_${variantMatch[1]}`, todoRename: true };

  // --- Needs human naming (use variant_N + _todo_rename) ---
  // All other patterns get variant_N placeholder
  return { key: null, todoRename: true, originalLabel: label, variantDesc: variant };
}

// ====== Element conversion ======

function elementToArray(el) {
  if (!el || el.length === 0) return ['普'];
  // All elements in this dataset are 1-2 Chinese chars
  // Single-element: "光" → ["光"]
  // Dual-element: "幽恶" → ["幽", "恶"]
  if (el.length === 1) return [el];
  if (el.length === 2) return [el[0], el[1]];
  // Edge case: keep as-is (e.g. "草莓" if it exists)
  return [el];
}

// ====== Check if acquire is evolution (contains "进化") ======

function isEvolutionAcquire(acquire) {
  if (!acquire) return false;
  return acquire.includes('进化');
}

// ====== Main migration ======

const pets = {};
let stats = {
  total: 0,
  leaderToBoss: 0,
  shinyTags: 0,
  todoRenameForms: 0,
  evolutionAcquires: 0,
  directAcquires: 0,
  emptyAcquires: 0,
};

sprites.forEach((sprite) => {
  stats.total++;
  const petKey = `pet_${sprite.id}`;
  const pet = {
    name: sprite.name,
    element: elementToArray(sprite.element),
    forms: {},
    tags: {},
    pinyin: sprite.pinyin || null,
  };

  // Optional fields
  if (sprite.fruit) {
    pet.fruit = sprite.fruit;
  }
  if (sprite.notes) {
    pet.notes = sprite.notes;
  }
  if (sprite.destined_hero) {
    pet.destined_hero = sprite.destined_hero;
  }

  // Track variant_N counter per pet
  let variantCounter = 0;

  // Process forms
  sprite.forms.forEach((form) => {
    // Leader forms → tags.boss
    if (form.type === 'leader') {
      pet.tags.boss = { tagName: '首领' };
      stats.leaderToBoss++;
      return; // Don't add as a form
    }

    // Determine form key
    let formKey;
    let todoRename = false;
    let originalLabel = null;
    let variantDesc = null;

    if (form.label === '基础形态') {
      formKey = 'basic';
    } else {
      const result = mapFormLabelToKey(form.label, sprite.name);
      if (result.key) {
        formKey = result.key;
        todoRename = result.todoRename;
      } else {
        // Assign variant_N
        variantCounter++;
        formKey = `variant_${variantCounter}`;
        todoRename = true;
        originalLabel = result.originalLabel;
        variantDesc = result.variantDesc;
      }
    }

    if (todoRename) stats.todoRenameForms++;

    // Build form entry
    const formEntry = {
      formName: form.label,
      obtainMethods: [],
    };

    if (todoRename) {
      formEntry._todo_rename = true;
      if (originalLabel) formEntry._original_label = originalLabel;
    }

    pet.forms[formKey] = formEntry;

    // Check for capture_shiny tag
    form.tasks.forEach((task) => {
      if (task.type === 'capture_shiny' && !pet.tags.shiny) {
        pet.tags.shiny = { tagName: '异色' };
        stats.shinyTags++;
      }
    });
  });

  // Process acquire → basic form obtainMethods
  const acquire = sprite.acquire || '';
  if (acquire) {
    if (isEvolutionAcquire(acquire)) {
      stats.evolutionAcquires++;
      // Don't add to obtainMethods
    } else {
      stats.directAcquires++;
      if (pet.forms.basic) {
        pet.forms.basic.obtainMethods = [acquire];
      }
    }
  } else {
    stats.emptyAcquires++;
  }

  // Clean up empty tags
  if (Object.keys(pet.tags).length === 0) {
    delete pet.tags;
  }

  // Clean up null pinyin
  if (pet.pinyin === null) {
    delete pet.pinyin;
  }

  pets[petKey] = pet;
});

// Write output
fs.writeFileSync(OUTPUT_FILE, JSON.stringify(pets, null, 2), 'utf8');

// Stats
console.log('=== migrate-to-pets.js ===');
console.log(`Total pets migrated: ${stats.total}`);
console.log(`Leader forms → tags.boss: ${stats.leaderToBoss}`);
console.log(`Shiny tags added: ${stats.shinyTags}`);
console.log(`Forms with _todo_rename: ${stats.todoRenameForms}`);
console.log(`Evolution acquires (NOT in obtainMethods): ${stats.evolutionAcquires}`);
console.log(`Direct acquires (in obtainMethods): ${stats.directAcquires}`);
console.log(`Empty acquires: ${stats.emptyAcquires}`);
console.log(`Output: ${OUTPUT_FILE}`);

// List all unique _todo_rename form labels for manual review
const todoLabels = new Set();
Object.values(pets).forEach(pet => {
  Object.entries(pet.forms).forEach(([key, form]) => {
    if (form._todo_rename && form._original_label) {
      todoLabels.add(form._original_label);
    }
  });
});
console.log(`\nTodo rename unique labels (${todoLabels.size}):`);
[...todoLabels].sort().forEach(label => console.log(`  ${label}`));
