#!/usr/bin/env node
/**
 * migrate-to-evolution-chains.js
 * 从 sprites.json 的 acquire 字段自动构建进化链 → evolution-chains.json
 *
 * 解析规则：
 * - "喵喵16级进化" → from 喵喵 at level 16
 * - "火花16级进化" → from 火花 at level 16
 * - 分支检测：同一 source 多个 target
 * - S2 新精灵（无 acquire）单独成链或标记待补
 */

const fs = require('fs');
const path = require('path');

const SPRITES_FILE = path.join(__dirname, '..', 'data', 'sprites.json');
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'evolution-chains.json');

const sprites = JSON.parse(fs.readFileSync(SPRITES_FILE, 'utf8'));

// ====== Build name → id lookup ======
const nameToId = {};
sprites.forEach(s => { nameToId[s.name] = s.id; });

// ====== Parse evolution acquire ======
// Returns { sourceId, level, condition, isEvolution } or null if not evolution
function parseEvolutionAcquire(acquire) {
  if (!acquire) return null;

  // Don't treat "亲密度" as evolution
  if (acquire.includes('亲密度')) return null;

  // Multiple parts separated by / or |
  const parts = acquire.split(/[/|]/);

  for (const part of parts) {
    const trimmed = part.trim();

    // Try standard pattern: "喵喵16级进化" or with trailing conditions
    // Also handles: "柴渣虫40级进化燃烧技能击败3次"
    let match = trimmed.match(/^(\S+?)(\d+)级进化(.*)$/);
    if (match) {
      let sourceName = match[1];
      const level = parseInt(match[2], 10);
      const trail = match[3] || '';

      // Check if sourceName is pure digits (part of level, not a real name)
      // e.g. "28级进化击败3光系" → sourceName would be "2", level would be 8
      if (/^\d+$/.test(sourceName)) {
        // Missing source name: the "source" digits + level digits form the full level
        // e.g. "28" → level 28
        const fullMatch = trimmed.match(/^(\d+)级进化(.*)$/);
        if (fullMatch) {
          const fullLevel = parseInt(fullMatch[1], 10);
          const fullTrail = fullMatch[2] || '';
          return {
            sourceId: null,
            sourceName: null,
            level: fullLevel,
            condition: { type: 'level', level: fullLevel, note: fullTrail || null },
            isEvolution: true,
            _needsSource: true,
          };
        }
      }

      const sourceId = nameToId[sourceName];
      if (!sourceId) {
        console.warn(`  WARNING: source '${sourceName}' not found for acquire '${acquire}'`);
        return null;
      }

      // Build condition
      const condition = { type: 'level', level };
      if (trail) {
        condition.note = trail;
      }

      return {
        sourceId,
        sourceName,
        level,
        condition,
        isEvolution: true,
      };
    }
  }

  return null;
}

// ====== Build chains ======
const evolutionMap = {}; // sourceId → [{ targetId, level, condition }]
const allChainedIds = new Set(); // IDs that are targets of evolution

const needsSourceSprites = []; // sprites whose evolution source couldn't be determined

sprites.forEach(sprite => {
  const parsed = parseEvolutionAcquire(sprite.acquire);
  if (parsed) {
    allChainedIds.add(sprite.id);

    if (parsed.sourceId === null) {
      // Try to infer source from adjacent sprite ID (common pattern: sequential IDs)
      // Look for a sprite with id = this.id - 1 that is a base form (direct acquire)
      const prevSprite = sprites.find(s => s.id === sprite.id - 1);
      if (prevSprite && !(prevSprite.acquire || '').includes('进化')) {
        parsed.sourceId = prevSprite.id;
        parsed.sourceName = prevSprite.name;
        console.warn(`  INFERRED: '${sprite.name}' (${sprite.id}) source → '${prevSprite.name}' (${prevSprite.id})`);
      } else {
        needsSourceSprites.push({ id: sprite.id, name: sprite.name, acquire: sprite.acquire, level: parsed.level });
        return; // skip this sprite
      }
    }

    if (!evolutionMap[parsed.sourceId]) {
      evolutionMap[parsed.sourceId] = [];
    }
    evolutionMap[parsed.sourceId].push({
      targetId: sprite.id,
      targetName: sprite.name,
      level: parsed.level,
      condition: parsed.condition,
    });
  }
});

// Find base species (not targets of evolution, but have outgoing)
const baseSpeciesIds = Object.keys(evolutionMap)
  .map(Number)
  .filter(id => !allChainedIds.has(id));

// Also include species that are neither source nor target (standalone)
const allSpriteIds = new Set(sprites.map(s => s.id));
const chainedSourceIds = new Set(Object.keys(evolutionMap).map(Number));
const standaloneIds = [...allSpriteIds].filter(id =>
  !chainedSourceIds.has(id) && !allChainedIds.has(id)
);

// BFS to build chains from each base species
const visited = new Set();
const chains = [];
let chainIdCounter = 0;

function buildChain(startId) {
  chainIdCounter++;
  const chain = {
    chainId: chainIdCounter,
    baseSpeciesId: `pet_${startId}`,
    nodes: {},
  };

  // BFS
  const queue = [startId];
  const localVisited = new Set();

  while (queue.length > 0) {
    const currentId = queue.shift();
    if (localVisited.has(currentId)) continue;
    localVisited.add(currentId);
    visited.add(currentId);

    const sprite = sprites.find(s => s.id === currentId);
    const nodeKey = `pet_${currentId}`;

    const evolvesTo = (evolutionMap[currentId] || []).map(ev => {
      if (!localVisited.has(ev.targetId)) {
        queue.push(ev.targetId);
      }
      return {
        toSpeciesId: `pet_${ev.targetId}`,
        condition: ev.condition,
      };
    });

    chain.nodes[nodeKey] = { evolvesTo };
  }

  return chain;
}

// Build chains from base species
baseSpeciesIds.forEach(id => {
  if (!visited.has(id)) {
    chains.push(buildChain(id));
  }
});

// Handle remaining chained species (might be mid-chain without detected base, or orphans)
// This covers cases where the base wasn't detected
const remainingSources = [...chainedSourceIds].filter(id => !visited.has(id));
remainingSources.forEach(id => {
  chains.push(buildChain(id));
});

// Add standalone species (no evolution)
standaloneIds.forEach(id => {
  if (!visited.has(id)) {
    chainIdCounter++;
    chains.push({
      chainId: chainIdCounter,
      baseSpeciesId: `pet_${id}`,
      nodes: {
        [`pet_${id}`]: { evolvesTo: [] },
      },
    });
    visited.add(id);
  }
});

// Catch any remaining
sprites.forEach(s => {
  if (!visited.has(s.id)) {
    chainIdCounter++;
    chains.push({
      chainId: chainIdCounter,
      baseSpeciesId: `pet_${s.id}`,
      nodes: {
        [`pet_${s.id}`]: { evolvesTo: [] },
      },
    });
  }
});

// Sort chains by chainId
chains.sort((a, b) => a.chainId - b.chainId);

// ====== Stats ======
fs.writeFileSync(OUTPUT_FILE, JSON.stringify(chains, null, 2), 'utf8');

const branchingChains = chains.filter(c =>
  Object.values(c.nodes).some(n => n.evolvesTo.length > 1)
);

const maxDepth = Math.max(...chains.map(c => Object.keys(c.nodes).length));

console.log('=== migrate-to-evolution-chains.js ===');
console.log(`Total chains: ${chains.length}`);
console.log(`Base species (no evolution source): ${baseSpeciesIds.length}`);
console.log(`Evolution edges: ${Object.values(evolutionMap).reduce((sum, arr) => sum + arr.length, 0)}`);
console.log(`Branching chains: ${branchingChains.length}`);
console.log(`Max chain depth: ${maxDepth}`);
console.log(`Standalone species: ${standaloneIds.length}`);
console.log(`Needs source (orphans): ${needsSourceSprites.length}`);
console.log(`Output: ${OUTPUT_FILE}`);

if (needsSourceSprites.length > 0) {
  console.log(`\nOrphan sprites (source not found, added as standalone):`);
  needsSourceSprites.forEach(s => {
    console.log(`  [${s.id}] ${s.name}: ${s.acquire} (level=${s.level})`);
  });
}

// List branching chains for review
if (branchingChains.length > 0) {
  console.log(`\nBranching chains (review needed):`);
  branchingChains.forEach(c => {
    const baseName = sprites.find(s => `pet_${s.id}` === c.baseSpeciesId)?.name || '?';
    const branches = Object.entries(c.nodes)
      .filter(([, n]) => n.evolvesTo.length > 1)
      .map(([key, n]) => {
        const srcName = sprites.find(s => `pet_${s.id}` === key)?.name || '?';
        const targets = n.evolvesTo.map(e => {
          const tgtName = sprites.find(s => `pet_${s.id}` === e.toSpeciesId)?.name || '?';
          return tgtName;
        });
        return `  ${srcName} → ${targets.join(' | ')}`;
      });
    console.log(`Chain #${c.chainId} (${baseName}):`);
    branches.forEach(b => console.log(b));
  });
}
