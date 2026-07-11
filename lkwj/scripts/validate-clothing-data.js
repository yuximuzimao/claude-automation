const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, '..', 'data');
const clothingPath = path.join(dataDir, 'clothing.json');
const collectionsPath = path.join(dataDir, 'collections.json');
const csvPath = path.join(dataDir, '_待采集', '服装图鉴.csv');
const clothing = JSON.parse(fs.readFileSync(clothingPath, 'utf8'));
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
const setIdPattern = /^clothing_set_[1-9]\d*$/;
const pieceIdPattern = /^clothing_[1-9]\d*$/;
const csvHeaders = [
  'collectionType', 'setName', 'requiredPieceCount', 'gorgeousMagicPetName',
  'pieceName', 'category', 'setRole', 'obtainType', 'obtainMethod',
  'obtained', 'rawText', 'notes',
];

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"' && field.length === 0) {
      quoted = true;
    } else if (char === ',') {
      row.push(field);
      field = '';
    } else if (char === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else if (char !== '\r') {
      field += char;
    }
  }

  if (quoted) throw new Error('unterminated quoted CSV field');
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

if (!Array.isArray(clothing.sets)) errors.push('sets must be an array');
if (!Array.isArray(clothing.pieces)) errors.push('pieces must be an array');

for (const definitionName of ['gorgeousBadge', 'gorgeousMagic']) {
  const definition = clothing.definitions?.[definitionName];
  if (!isNonEmptyString(definition?.name)) errors.push(`missing ${definitionName} definition name`);
  if (!isNonEmptyString(definition?.description)) errors.push(`missing ${definitionName} definition description`);
}

const gorgeousBadgeDescription = clothing.definitions?.gorgeousBadge?.description || '';
for (const phrase of ['炫彩染料', '亲昵互动', '自定义搭配']) {
  if (!gorgeousBadgeDescription.includes(phrase)) errors.push(`gorgeousBadge definition must include ${phrase}`);
}
const gorgeousMagicDescription = clothing.definitions?.gorgeousMagic?.description || '';
for (const phrase of ['必需部件', '特殊登场演出']) {
  if (!gorgeousMagicDescription.includes(phrase)) errors.push(`gorgeousMagic definition must include ${phrase}`);
}

for (const set of sets) {
  if (!set || typeof set !== 'object' || Array.isArray(set)) {
    errors.push('set must be an object');
    continue;
  }
  if (!isNonEmptyString(set.id)) {
    errors.push('set missing id');
  } else if (!setIdPattern.test(set.id)) {
    errors.push(`${set.id}: invalid set id format`);
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
  } else if (!pieceIdPattern.test(piece.id)) {
    errors.push(`${piece.id}: invalid piece id format`);
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

let clothingProgress = null;
if (fs.existsSync(collectionsPath)) {
  const collections = JSON.parse(fs.readFileSync(collectionsPath, 'utf8'));
  clothingProgress = collections.clothing_progress || {};
  const piecesById = new Map(pieces.map(piece => [piece.id, piece]));
  for (const id of Object.keys(clothingProgress)) {
    const piece = piecesById.get(id);
    if (!piece) {
      errors.push(`unknown clothing progress id: ${id}`);
    } else if (piece.obtainType === 'paid') {
      errors.push(`paid piece cannot appear in clothing_progress: ${id}`);
    }
  }
}

if (!fs.existsSync(csvPath)) {
  errors.push('missing clothing CSV');
} else {
  let rows;
  try {
    rows = parseCsv(fs.readFileSync(csvPath, 'utf8'));
  } catch (error) {
    errors.push(`invalid clothing CSV: ${error.message}`);
    rows = [];
  }

  const headerMatches = rows.length > 0
    && rows[0].length === csvHeaders.length
    && rows[0].every((header, index) => header === csvHeaders[index]);
  if (!headerMatches) {
    errors.push('clothing CSV header must exactly match required 12 columns');
  }
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    if (rows[rowIndex].length !== csvHeaders.length) {
      errors.push(`clothing CSV row ${rowIndex + 1}: expected 12 columns, got ${rows[rowIndex].length}`);
    }
  }

  if (headerMatches) {
    const setsByName = new Map(sets.map(set => [set.name, set]));
    const piecesByIdentity = new Map(pieces.map(piece => [
      `${piece.collectionType}|${piece.setId || ''}|${piece.pieceName}`,
      piece,
    ]));
    const csvPiecesByIdentity = new Map();
    const setOnlyRowsBySetId = new Map();

    for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex];
      if (row.length !== csvHeaders.length) continue;
      const record = Object.fromEntries(csvHeaders.map((header, index) => [header, row[index]]));
      const set = setsByName.get(record.setName);

      if (!record.pieceName) {
        if (record.collectionType !== 'set') {
          errors.push(`set-only declaration must use collectionType=set: row ${rowIndex + 1}`);
          continue;
        }
        if (!set) {
          errors.push(`set-only declaration references unknown set: row ${rowIndex + 1} ${record.setName}`);
          continue;
        }
        const declarations = setOnlyRowsBySetId.get(set.id) || [];
        declarations.push({ rowIndex: rowIndex + 1, record });
        setOnlyRowsBySetId.set(set.id, declarations);
        if (record.requiredPieceCount !== String(set.requiredPieceCount)) {
          errors.push(`set-only field mismatch requiredPieceCount: row ${rowIndex + 1} ${set.name}`);
        }
        if (record.gorgeousMagicPetName !== set.gorgeousMagicPetName) {
          errors.push(`set-only field mismatch gorgeousMagicPetName: row ${rowIndex + 1} ${set.name}`);
        }
        if (record.obtainMethod !== set.obtainMethod) {
          errors.push(`set-only field mismatch obtainMethod: row ${rowIndex + 1} ${set.name}`);
        }
        for (const field of ['category', 'setRole', 'obtainType', 'obtained']) {
          if (record[field] !== '') {
            errors.push(`set-only field must be empty ${field}: row ${rowIndex + 1} ${set.name}`);
          }
        }
        continue;
      }

      const setId = record.collectionType === 'set' ? set?.id || '' : '';
      const identity = `${record.collectionType}|${setId}|${record.pieceName}`;
      const csvEntries = csvPiecesByIdentity.get(identity) || [];
      csvEntries.push({ rowIndex: rowIndex + 1, record });
      csvPiecesByIdentity.set(identity, csvEntries);
      if (csvEntries.length > 1) errors.push(`duplicate CSV piece: ${identity}`);

      const piece = piecesByIdentity.get(identity);
      if (!piece) {
        errors.push(`CSV piece has no matching JSON piece: ${identity}`);
        continue;
      }
      const pieceSet = piece.collectionType === 'set' ? setsById.get(piece.setId) : null;
      const expectedFields = {
        collectionType: piece.collectionType,
        setName: pieceSet?.name || '',
        requiredPieceCount: pieceSet ? String(pieceSet.requiredPieceCount) : '',
        gorgeousMagicPetName: pieceSet?.gorgeousMagicPetName || '',
        pieceName: piece.pieceName,
        category: piece.category,
        setRole: piece.setRole || '',
        obtainType: piece.obtainType,
        obtainMethod: piece.obtainMethod,
      };
      for (const [field, expected] of Object.entries(expectedFields)) {
        if (record[field] !== expected) {
          errors.push(`CSV field mismatch ${field}: row ${rowIndex + 1} ${piece.pieceName}; expected ${JSON.stringify(expected)}, got ${JSON.stringify(record[field])}`);
        }
      }

      if (piece.obtainType === 'paid' && record.obtained !== '否') {
        errors.push(`paid CSV row must be obtained=否: row ${rowIndex + 1} ${piece.pieceName}`);
      }
      if (clothingProgress) {
        const hasProgressKey = Object.prototype.hasOwnProperty.call(clothingProgress, piece.id);
        const progressIsTrue = clothingProgress[piece.id] === true;
        const obtainedMatches = record.obtained === '是'
          ? progressIsTrue
          : record.obtained === '否' && !hasProgressKey;
        if (!obtainedMatches) {
          errors.push(`CSV obtained/progress mismatch: row ${rowIndex + 1} ${piece.pieceName}`);
        }
      }
    }

    for (const [identity, piece] of piecesByIdentity) {
      const csvEntries = csvPiecesByIdentity.get(identity) || [];
      if (csvEntries.length === 0) errors.push(`JSON piece missing from CSV: ${identity}`);
      if (csvEntries.length > 1) errors.push(`JSON piece appears multiple times in CSV: ${identity}`);
      if (clothingProgress && Object.prototype.hasOwnProperty.call(clothingProgress, piece.id)) {
        if (clothingProgress[piece.id] !== true) {
          errors.push(`clothing_progress value must be true: ${piece.id}`);
        }
        if (csvEntries.length === 1 && csvEntries[0].record.obtained !== '是') {
          errors.push(`clothing_progress ID must map to CSV obtained=是: ${piece.id}`);
        }
      }
    }

    const pieceSetIds = new Set(pieces.filter(piece => piece.collectionType === 'set').map(piece => piece.setId));
    for (const set of sets) {
      const declarations = setOnlyRowsBySetId.get(set.id) || [];
      const expectedCount = pieceSetIds.has(set.id) ? 0 : 1;
      if (declarations.length !== expectedCount) {
        errors.push(`set-only declaration count mismatch: ${set.name} expected ${expectedCount}, got ${declarations.length}`);
      }
    }
  }
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
