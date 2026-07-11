const fs = require('fs');
const path = require('path');

const clothing = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'clothing.json'), 'utf8'));
const categories = new Set([
  '玩偶服/连衣', '上衣', '下装', '头饰/帽子', '发型', '手饰', '面饰',
  '鞋子', '袜子', '背包', '包挂饰', '法杖', '华丽徽章',
]);
const roles = new Set(['magic_required', 'optional']);
const obtainTypes = new Set(['standard', 'paid']);
const errors = [];
const warnings = [];
const setsById = new Map((clothing.sets || []).map(set => [set.id, set]));
const ids = new Set();
const names = new Set();

if (!clothing.definitions?.gorgeousBadge?.description) errors.push('missing gorgeousBadge definition');
if (!clothing.definitions?.gorgeousMagic?.description) errors.push('missing gorgeousMagic definition');

for (const set of clothing.sets || []) {
  if (!set.id || !set.name) errors.push('set missing id/name');
  if (!Number.isInteger(set.requiredPieceCount) || set.requiredPieceCount < 1) {
    errors.push(`${set.name}: invalid requiredPieceCount`);
  }
}

for (const piece of clothing.pieces || []) {
  if (ids.has(piece.id)) errors.push(`duplicate id: ${piece.id}`);
  ids.add(piece.id);
  if (!categories.has(piece.category)) errors.push(`${piece.pieceName}: invalid category ${piece.category}`);
  if (!obtainTypes.has(piece.obtainType)) errors.push(`${piece.pieceName}: invalid obtainType ${piece.obtainType}`);
  if (piece.collectionType === 'set' && !setsById.has(piece.setId)) errors.push(`${piece.pieceName}: orphan setId`);
  if (piece.setRole && !roles.has(piece.setRole)) errors.push(`${piece.pieceName}: invalid setRole`);
  if (piece.obtainType === 'paid' && piece.setRole === 'magic_required') {
    errors.push(`${piece.pieceName}: paid piece cannot be magic_required`);
  }
  const identity = `${piece.collectionType}|${piece.setId || ''}|${piece.pieceName}`;
  if (names.has(identity)) errors.push(`duplicate piece: ${identity}`);
  names.add(identity);
}

for (const set of clothing.sets || []) {
  const required = (clothing.pieces || []).filter(piece => piece.setId === set.id && piece.setRole === 'magic_required');
  if (required.length > set.requiredPieceCount) errors.push(`${set.name}: required pieces exceed declared count`);
  if (required.length < set.requiredPieceCount) warnings.push(`${set.name}: ${required.length}/${set.requiredPieceCount} required piece names recorded`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  sets: (clothing.sets || []).length,
  pieces: (clothing.pieces || []).length,
  paid: (clothing.pieces || []).filter(piece => piece.obtainType === 'paid').length,
  warnings,
}, null, 2));
