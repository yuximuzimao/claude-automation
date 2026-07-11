const fs = require('fs');
const path = require('path');

const clothing = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'clothing.json'), 'utf8'));
const categories = new Set([
  '玩偶服/连衣', '上衣', '下装', '头饰/帽子', '发型', '手饰', '面饰',
  '鞋子', '袜子', '背包', '包挂饰', '法杖', '华丽徽章',
]);
const roles = new Set(['magic_required', 'optional']);
const obtainTypes = new Set(['standard', 'paid']);
const collectionTypes = new Set(['set', 'single']);
const errors = [];
const warnings = [];
const sets = Array.isArray(clothing.sets) ? clothing.sets : [];
const pieces = Array.isArray(clothing.pieces) ? clothing.pieces : [];
const setsById = new Map();
const setIds = new Set();
const setNames = new Set();
const pieceIds = new Set();
const pieceNames = new Set();

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

if (!Array.isArray(clothing.sets)) errors.push('sets must be an array');
if (!Array.isArray(clothing.pieces)) errors.push('pieces must be an array');

for (const definitionName of ['gorgeousBadge', 'gorgeousMagic']) {
  const definition = clothing.definitions?.[definitionName];
  if (!isNonEmptyString(definition?.name)) errors.push(`missing ${definitionName} definition name`);
  if (!isNonEmptyString(definition?.description)) errors.push(`missing ${definitionName} definition description`);
}

for (const set of sets) {
  if (!set || typeof set !== 'object' || Array.isArray(set)) {
    errors.push('set must be an object');
    continue;
  }
  if (!isNonEmptyString(set.id)) {
    errors.push('set missing id');
  } else if (setIds.has(set.id)) {
    errors.push(`duplicate set id: ${set.id}`);
  } else {
    setIds.add(set.id);
    setsById.set(set.id, set);
  }
  if (!isNonEmptyString(set.name)) {
    errors.push(`${set.id || 'unknown set'}: missing name`);
  } else if (setNames.has(set.name)) {
    errors.push(`duplicate set name: ${set.name}`);
  } else {
    setNames.add(set.name);
  }
  if (!Number.isInteger(set.requiredPieceCount) || set.requiredPieceCount < 1) {
    errors.push(`${set.name || set.id || 'unknown set'}: invalid requiredPieceCount`);
  }
  if (!isNonEmptyString(set.obtainMethod)) errors.push(`${set.name || set.id || 'unknown set'}: missing obtainMethod`);
  if (typeof set.gorgeousMagicPetName !== 'string') {
    errors.push(`${set.name || set.id || 'unknown set'}: missing gorgeousMagicPetName`);
  }
}

for (const piece of pieces) {
  if (!piece || typeof piece !== 'object' || Array.isArray(piece)) {
    errors.push('piece must be an object');
    continue;
  }
  const label = piece.pieceName || piece.id || 'unknown piece';
  if (!isNonEmptyString(piece.id)) {
    errors.push(`${label}: missing id`);
  } else if (pieceIds.has(piece.id)) {
    errors.push(`duplicate piece id: ${piece.id}`);
  } else {
    pieceIds.add(piece.id);
  }
  if (!isNonEmptyString(piece.pieceName)) errors.push(`${piece.id || 'unknown piece'}: missing pieceName`);
  if (!collectionTypes.has(piece.collectionType)) errors.push(`${label}: invalid collectionType ${piece.collectionType}`);
  if (!categories.has(piece.category)) errors.push(`${piece.pieceName}: invalid category ${piece.category}`);
  if (!obtainTypes.has(piece.obtainType)) errors.push(`${piece.pieceName}: invalid obtainType ${piece.obtainType}`);
  if (!isNonEmptyString(piece.obtainMethod)) errors.push(`${label}: missing obtainMethod`);
  if (piece.setRole !== undefined && !roles.has(piece.setRole)) errors.push(`${label}: invalid setRole ${piece.setRole}`);
  if (piece.collectionType === 'set') {
    if (!isNonEmptyString(piece.setId) || !setsById.has(piece.setId)) errors.push(`${label}: invalid setId ${piece.setId}`);
  }
  if (piece.collectionType === 'single') {
    if (Object.prototype.hasOwnProperty.call(piece, 'setId')) errors.push(`${label}: single piece cannot have setId`);
    if (Object.prototype.hasOwnProperty.call(piece, 'setRole')) errors.push(`${label}: single piece cannot have setRole`);
  }
  if (piece.obtainType === 'paid' && piece.setRole === 'magic_required') {
    errors.push(`${label}: paid piece cannot be magic_required`);
  }
  const identity = `${piece.collectionType}|${piece.setId || ''}|${piece.pieceName}`;
  if (pieceNames.has(identity)) errors.push(`duplicate piece: ${identity}`);
  pieceNames.add(identity);
}

for (const set of sets) {
  if (!set || typeof set !== 'object' || Array.isArray(set)) continue;
  const required = pieces.filter(piece =>
    piece
    && typeof piece === 'object'
    && !Array.isArray(piece)
    && piece.collectionType === 'set'
    && piece.setId === set.id
    && piece.setRole === 'magic_required'
  );
  if (required.length > set.requiredPieceCount) errors.push(`${set.name}: required pieces exceed declared count`);
  if (required.length < set.requiredPieceCount) warnings.push(`${set.name}: ${required.length}/${set.requiredPieceCount} required piece names recorded`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({
  sets: sets.length,
  pieces: pieces.length,
  paid: pieces.filter(piece => piece.obtainType === 'paid').length,
  warnings,
}, null, 2));
