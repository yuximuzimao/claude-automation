const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, '..', 'data');
const clothingPath = path.join(dataDir, 'clothing.json');
const collectionsPath = path.join(dataDir, 'collections.json');
const clothing = JSON.parse(fs.readFileSync(clothingPath, 'utf8'));
const categories = new Set([
  '连衣', '玩偶服', '上衣', '下装', '帽子', '发型', '手饰', '面饰',
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
const todayRandomShopPieces = [
  ['背包-千棘盔印象', 'clothing_set_76', '背包'],
  ['鞋子-嘟嘟锅印象', 'clothing_set_38', '鞋子'],
  ['下装-魔眷鸟印象', 'clothing_set_47', '下装'],
  ['背包-翠顶夫人印象', 'clothing_set_11', '背包'],
  ['袜子-迷迷箱怪印象', 'clothing_set_77', '袜子'],
  ['鞋子-高脚鹬印象', 'clothing_set_44', '鞋子'],
  ['连衣-千棘盔印象', 'clothing_set_76', '连衣'],
  ['帽子-花衣蝶印象', 'clothing_set_41', '帽子'],
];
const confirmedMissingPieces = [
  ['鞋子-翠顶夫人印象', 'clothing_set_11', '鞋子'],
  ['帽子-翠顶夫人印象', 'clothing_set_11', '帽子'],
  ['手饰-獠牙猪印象', 'clothing_set_13', '手饰'],
  ['上衣-奇丽花印象', 'clothing_set_28', '上衣'],
  ['袜子-奇丽花印象', 'clothing_set_28', '袜子'],
  ['手饰-奇丽花印象', 'clothing_set_28', '手饰'],
  ['连衣-星光狮印象', 'clothing_set_29', '连衣'],
  ['手饰-星光狮印象', 'clothing_set_29', '手饰'],
  ['连衣-皇家狮鹫印象', 'clothing_set_30', '连衣'],
  ['背包-花魁蜂后印象', 'clothing_set_31', '背包'],
  ['连衣-花魁蜂后印象', 'clothing_set_31', '连衣'],
  ['鞋子-花魁蜂后印象', 'clothing_set_31', '鞋子'],
  ['手饰-卡洛儿印象', 'clothing_set_32', '手饰'],
  ['连衣-梦悠悠印象', 'clothing_set_33', '连衣'],
  ['背包-雪影娃娃印象', 'clothing_set_35', '背包'],
  ['手饰-雪影娃娃印象', 'clothing_set_35', '手饰'],
  ['鞋子-雪影娃娃印象', 'clothing_set_35', '鞋子'],
  ['袜子-魔草巫灵印象', 'clothing_set_37', '袜子'],
  ['背包-魔草巫灵印象', 'clothing_set_37', '背包'],
  ['上衣-魔草巫灵印象', 'clothing_set_37', '上衣'],
  ['下装-魔草巫灵印象', 'clothing_set_37', '下装'],
  ['帽子-魔草巫灵印象', 'clothing_set_37', '帽子'],
  ['连衣-嘟嘟锅印象', 'clothing_set_38', '连衣'],
  ['帽子-嘟嘟锅印象', 'clothing_set_38', '帽子'],
  ['背包-嘟嘟锅印象', 'clothing_set_38', '背包'],
  ['帽子-九幽菇印象', 'clothing_set_39', '帽子'],
  ['背包-九幽菇印象', 'clothing_set_39', '背包'],
  ['连衣-九幽菇印象', 'clothing_set_39', '连衣'],
  ['手饰-蒲公英娃娃印象', 'clothing_set_40', '手饰'],
  ['袜子-蒲公英娃娃印象', 'clothing_set_40', '袜子'],
  ['连衣-蒲公英娃娃印象', 'clothing_set_40', '连衣'],
  ['帽子-蒲公英娃娃印象', 'clothing_set_40', '帽子'],
  ['袜子-花衣蝶印象', 'clothing_set_41', '袜子'],
  ['连衣-花衣蝶印象', 'clothing_set_41', '连衣'],
  ['背包-红绒十字印象', 'clothing_set_42', '背包'],
  ['手饰-红绒十字印象', 'clothing_set_42', '手饰'],
  ['帽子-红绒十字印象', 'clothing_set_42', '帽子'],
  ['连衣-红绒十字印象', 'clothing_set_42', '连衣'],
  ['背包-白金独角兽印象', 'clothing_set_43', '背包'],
  ['手饰-白金独角兽印象', 'clothing_set_43', '手饰'],
  ['连衣-白金独角兽印象', 'clothing_set_43', '连衣'],
  ['帽子-白金独角兽印象', 'clothing_set_43', '帽子'],
  ['上衣-高脚鹬印象', 'clothing_set_44', '上衣'],
  ['帽子-高脚鹬印象', 'clothing_set_44', '帽子'],
  ['连衣-琉璃水母印象', 'clothing_set_45', '连衣'],
  ['帽子-琉璃水母印象', 'clothing_set_45', '帽子'],
  ['背包-琉璃水母印象', 'clothing_set_45', '背包'],
  ['手饰-琉璃水母印象', 'clothing_set_45', '手饰'],
  ['鞋子-琉璃水母印象', 'clothing_set_45', '鞋子'],
  ['袜子-雪灵印象', 'clothing_set_46', '袜子'],
  ['鞋子-雪灵印象', 'clothing_set_46', '鞋子'],
  ['连衣-雪灵印象', 'clothing_set_46', '连衣'],
  ['帽子-雪灵印象', 'clothing_set_46', '帽子'],
  ['手饰-雪灵印象', 'clothing_set_46', '手饰'],
  ['帽子-魔眷鸟印象', 'clothing_set_47', '帽子'],
  ['手饰-魔眷鸟印象', 'clothing_set_47', '手饰'],
  ['袜子-魔眷鸟印象', 'clothing_set_47', '袜子'],
  ['鞋子-魔眷鸟印象', 'clothing_set_47', '鞋子'],
  ['上衣-橙花的追忆', 'clothing_set_51', '上衣'],
  ['下装-橙花的追忆', 'clothing_set_51', '下装'],
  ['帽子-橙花的追忆', 'clothing_set_51', '帽子'],
  ['背包-橙花的追忆', 'clothing_set_51', '背包'],
  ['手饰-橙花的追忆', 'clothing_set_51', '手饰'],
  ['袜子-橙花的追忆', 'clothing_set_51', '袜子'],
  ['鞋子-橙花的追忆', 'clothing_set_51', '鞋子'],
  ['上衣-唱诗班的礼赞', 'clothing_set_52', '上衣'],
  ['下装-唱诗班的礼赞', 'clothing_set_52', '下装'],
  ['帽子-唱诗班的礼赞', 'clothing_set_52', '帽子'],
  ['背包-唱诗班的礼赞', 'clothing_set_52', '背包'],
  ['鞋子-唱诗班的礼赞', 'clothing_set_52', '鞋子'],
  ['帽子-烈火守护印象', 'clothing_set_53', '帽子'],
  ['背包-烈火守护印象', 'clothing_set_53', '背包'],
  ['手饰-烈火守护印象', 'clothing_set_53', '手饰'],
  ['上衣-圆号鱼印象', 'clothing_set_60', '上衣'],
  ['下装-圆号鱼印象', 'clothing_set_60', '下装'],
  ['帽子-圆号鱼印象', 'clothing_set_60', '帽子'],
  ['手饰-圆号鱼印象', 'clothing_set_60', '手饰'],
  ['袜子-圆号鱼印象', 'clothing_set_60', '袜子'],
  ['鞋子-圆号鱼印象', 'clothing_set_60', '鞋子'],
  ['背包-圆号鱼印象', 'clothing_set_60', '背包'],
  ['上衣-蹦床松鼠印象', 'clothing_set_61', '上衣'],
  ['下装-蹦床松鼠印象', 'clothing_set_61', '下装'],
  ['帽子-蹦床松鼠印象', 'clothing_set_61', '帽子'],
  ['手饰-蹦床松鼠印象', 'clothing_set_61', '手饰'],
  ['袜子-蹦床松鼠印象', 'clothing_set_61', '袜子'],
  ['鞋子-蹦床松鼠印象', 'clothing_set_61', '鞋子'],
  ['背包-蹦床松鼠印象', 'clothing_set_61', '背包'],
  ['上衣-卡瓦重印象', 'clothing_set_62', '上衣'],
  ['下装-卡瓦重印象', 'clothing_set_62', '下装'],
  ['帽子-卡瓦重印象', 'clothing_set_62', '帽子'],
  ['背包-卡瓦重印象', 'clothing_set_62', '背包'],
  ['手饰-卡瓦重印象', 'clothing_set_62', '手饰'],
  ['袜子-卡瓦重印象', 'clothing_set_62', '袜子'],
  ['鞋子-卡瓦重印象', 'clothing_set_62', '鞋子'],
  ['上衣-里拉鳐印象', 'clothing_set_63', '上衣'],
  ['下装-里拉鳐印象', 'clothing_set_63', '下装'],
  ['帽子-里拉鳐印象', 'clothing_set_63', '帽子'],
  ['背包-里拉鳐印象', 'clothing_set_63', '背包'],
  ['手饰-里拉鳐印象', 'clothing_set_63', '手饰'],
  ['袜子-里拉鳐印象', 'clothing_set_63', '袜子'],
  ['鞋子-里拉鳐印象', 'clothing_set_63', '鞋子'],
  ['连衣-幻影灵菇印象', 'clothing_set_64', '连衣'],
  ['帽子-幻影灵菇印象', 'clothing_set_64', '帽子'],
  ['背包-幻影灵菇印象', 'clothing_set_64', '背包'],
  ['手饰-幻影灵菇印象', 'clothing_set_64', '手饰'],
  ['袜子-幻影灵菇印象', 'clothing_set_64', '袜子'],
  ['鞋子-幻影灵菇印象', 'clothing_set_64', '鞋子'],
  ['连衣-怖哭菇印象', 'clothing_set_65', '连衣'],
  ['帽子-怖哭菇印象', 'clothing_set_65', '帽子'],
  ['背包-怖哭菇印象', 'clothing_set_65', '背包'],
  ['手饰-怖哭菇印象', 'clothing_set_65', '手饰'],
  ['袜子-怖哭菇印象', 'clothing_set_65', '袜子'],
  ['鞋子-怖哭菇印象', 'clothing_set_65', '鞋子'],
  ['连衣-流浪鼠印象', 'clothing_set_66', '连衣'],
  ['帽子-流浪鼠印象', 'clothing_set_66', '帽子'],
  ['背包-流浪鼠印象', 'clothing_set_66', '背包'],
  ['手饰-流浪鼠印象', 'clothing_set_66', '手饰'],
  ['袜子-流浪鼠印象', 'clothing_set_66', '袜子'],
  ['鞋子-流浪鼠印象', 'clothing_set_66', '鞋子'],
  ['上衣-咕德帽帽印象', 'clothing_set_67', '上衣'],
  ['下装-咕德帽帽印象', 'clothing_set_67', '下装'],
  ['帽子-咕德帽帽印象', 'clothing_set_67', '帽子'],
  ['背包-咕德帽帽印象', 'clothing_set_67', '背包'],
  ['手饰-咕德帽帽印象', 'clothing_set_67', '手饰'],
  ['袜子-咕德帽帽印象', 'clothing_set_67', '袜子'],
  ['鞋子-咕德帽帽印象', 'clothing_set_67', '鞋子'],
  ['上衣-巨鼓象印象', 'clothing_set_69', '上衣'],
  ['下装-巨鼓象印象', 'clothing_set_69', '下装'],
  ['帽子-巨鼓象印象', 'clothing_set_69', '帽子'],
  ['背包-巨鼓象印象', 'clothing_set_69', '背包'],
  ['手饰-巨鼓象印象', 'clothing_set_69', '手饰'],
  ['袜子-巨鼓象印象', 'clothing_set_69', '袜子'],
  ['鞋子-巨鼓象印象', 'clothing_set_69', '鞋子'],
  ['上衣-烟花伯爵印象', 'clothing_set_71', '上衣'],
  ['下装-烟花伯爵印象', 'clothing_set_71', '下装'],
  ['帽子-烟花伯爵印象', 'clothing_set_71', '帽子'],
  ['背包-烟花伯爵印象', 'clothing_set_71', '背包'],
  ['手饰-烟花伯爵印象', 'clothing_set_71', '手饰'],
  ['袜子-烟花伯爵印象', 'clothing_set_71', '袜子'],
  ['鞋子-烟花伯爵印象', 'clothing_set_71', '鞋子'],
  ['上衣-小丑公爵印象', 'clothing_set_73', '上衣'],
  ['下装-小丑公爵印象', 'clothing_set_73', '下装'],
  ['帽子-小丑公爵印象', 'clothing_set_73', '帽子'],
  ['背包-小丑公爵印象', 'clothing_set_73', '背包'],
  ['手饰-小丑公爵印象', 'clothing_set_73', '手饰'],
  ['袜子-小丑公爵印象', 'clothing_set_73', '袜子'],
  ['鞋子-小丑公爵印象', 'clothing_set_73', '鞋子'],
  ['连衣-海豹船长印象', 'clothing_set_75', '连衣'],
  ['帽子-海豹船长印象', 'clothing_set_75', '帽子'],
  ['背包-海豹船长印象', 'clothing_set_75', '背包'],
  ['手饰-海豹船长印象', 'clothing_set_75', '手饰'],
  ['袜子-海豹船长印象', 'clothing_set_75', '袜子'],
  ['鞋子-海豹船长印象', 'clothing_set_75', '鞋子'],
  ['帽子-千棘盔印象', 'clothing_set_76', '帽子'],
  ['手饰-千棘盔印象', 'clothing_set_76', '手饰'],
  ['袜子-千棘盔印象', 'clothing_set_76', '袜子'],
  ['鞋子-千棘盔印象', 'clothing_set_76', '鞋子'],
  ['帽子-迷迷箱怪印象', 'clothing_set_77', '帽子'],
  ['鞋子-迷迷箱怪印象', 'clothing_set_77', '鞋子'],
  ['玩偶服-轻风省的果实', 'clothing_set_78', '玩偶服'],
  ['手饰-轻风省的果实', 'clothing_set_78', '手饰'],
  ['鞋子-轻风省的果实', 'clothing_set_78', '鞋子'],
  ['连衣-朔夜伊芙印象', 'clothing_set_79', '连衣'],
  ['帽子-朔夜伊芙印象', 'clothing_set_79', '帽子'],
  ['背包-朔夜伊芙印象', 'clothing_set_79', '背包'],
  ['手饰-朔夜伊芙印象', 'clothing_set_79', '手饰'],
  ['袜子-朔夜伊芙印象', 'clothing_set_79', '袜子'],
  ['鞋子-朔夜伊芙印象', 'clothing_set_79', '鞋子'],
  ['连衣-乌拉塔印象', 'clothing_set_81', '连衣'],
  ['帽子-乌拉塔印象', 'clothing_set_81', '帽子'],
  ['背包-乌拉塔印象', 'clothing_set_81', '背包'],
  ['手饰-乌拉塔印象', 'clothing_set_81', '手饰'],
  ['袜子-乌拉塔印象', 'clothing_set_81', '袜子'],
  ['鞋子-乌拉塔印象', 'clothing_set_81', '鞋子'],
  ['连衣-裘卡印象', 'clothing_set_82', '连衣'],
  ['帽子-裘卡印象', 'clothing_set_82', '帽子'],
  ['背包-裘卡印象', 'clothing_set_82', '背包'],
  ['手饰-裘卡印象', 'clothing_set_82', '手饰'],
  ['袜子-裘卡印象', 'clothing_set_82', '袜子'],
  ['鞋子-裘卡印象', 'clothing_set_82', '鞋子'],
  ['上衣-鎏金礼赞', 'clothing_set_83', '上衣'],
  ['下装-鎏金礼赞', 'clothing_set_83', '下装'],
  ['帽子-鎏金礼赞', 'clothing_set_83', '帽子'],
  ['鞋子-鎏金礼赞', 'clothing_set_83', '鞋子'],
];
const confirmedChromaticPairs = [
  ['clothing_set_13', 'clothing_set_54'],
  ['clothing_set_42', 'clothing_set_55'],
  ['clothing_set_43', 'clothing_set_56'],
  ['clothing_set_28', 'clothing_set_57'],
  ['clothing_set_35', 'clothing_set_58'],
  ['clothing_set_38', 'clothing_set_59'],
  ['clothing_set_67', 'clothing_set_68'],
  ['clothing_set_69', 'clothing_set_70'],
  ['clothing_set_71', 'clothing_set_72'],
  ['clothing_set_73', 'clothing_set_74'],
  ['clothing_set_79', 'clothing_set_80'],
];
const setIdPattern = /^clothing_set_[1-9]\d*$/;
const pieceIdPattern = /^clothing_[1-9]\d*$/;
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

for (const [pieceName, setId, category] of todayRandomShopPieces) {
  const matches = pieces.filter(piece => piece.pieceName === pieceName);
  if (matches.length !== 1) {
    errors.push(`${pieceName}: expected exactly one random-shop definition`);
    continue;
  }
  const piece = matches[0];
  if (piece.setId !== setId || piece.category !== category || piece.collectionType !== 'set'
    || piece.setRole !== 'magic_required' || piece.obtainType !== 'standard') {
    errors.push(`${pieceName}: random-shop definition fields mismatch`);
  }
}

for (const [pieceName, setId, category] of confirmedMissingPieces) {
  const matches = pieces.filter(piece => piece.pieceName === pieceName);
  if (matches.length !== 1) {
    errors.push(`${pieceName}: expected exactly one confirmed definition`);
    continue;
  }
  const piece = matches[0];
  if (piece.setId !== setId || piece.category !== category || piece.collectionType !== 'set'
    || piece.setRole !== 'magic_required' || piece.obtainType !== 'standard') {
    errors.push(`${pieceName}: confirmed definition fields mismatch`);
  }
}

for (const [normalSetId, chromaticSetId] of confirmedChromaticPairs) {
  const normalSet = setsById.get(normalSetId);
  const chromaticSet = setsById.get(chromaticSetId);
  const normalPieces = pieces.filter(piece => piece.setId === normalSetId && piece.setRole === 'magic_required');
  for (const normalPiece of normalPieces) {
    const expectedName = normalPiece.pieceName.replace(normalSet.name, chromaticSet.name);
    const matches = pieces.filter(piece => piece.setId === chromaticSetId && piece.pieceName === expectedName);
    if (matches.length !== 1 || matches[0].category !== normalPiece.category
      || matches[0].collectionType !== 'set' || matches[0].setRole !== 'magic_required'
      || matches[0].obtainType !== 'standard') {
      errors.push(`${expectedName}: chromatic definition must match the normal set piece`);
    }
  }
}

for (const piece of pieces) {
  if (!piece || typeof piece !== 'object' || Array.isArray(piece)) {
    errors.push('piece must be an object');
    continue;
  }
  const label = piece.pieceName || piece.id || 'unknown piece';
  if (piece.pieceName?.startsWith('头饰-')) errors.push(`${label}: piece name must use 帽子`);
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
