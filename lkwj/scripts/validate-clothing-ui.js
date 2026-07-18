const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = path.join(__dirname, '..', 'index.html');
const defaultHtml = fs.readFileSync(htmlPath, 'utf8');
const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const collections = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'collections.json'), 'utf8'));
const clothingPath = path.join(__dirname, '..', 'data', 'clothing.json');
const clothing = fs.existsSync(clothingPath)
  ? JSON.parse(fs.readFileSync(clothingPath, 'utf8'))
  : null;
const sets = clothing?.sets || [];
const pieces = clothing?.pieces || [];
const setSample = sets.find(i => i.name === '熔岩布丁印象');
const setPieceSample = pieces.find(i => i.pieceName === '连衣-熔岩布丁印象');
const singleSample = pieces.find(i => i.pieceName === '初始法杖');

function extractInlineScript(html) {
  const scriptMatch = html.match(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/);
  if (!scriptMatch) throw new Error('inline script not found');
  return scriptMatch[1];
}

function extractClothingSource(html) {
  const script = extractInlineScript(html);
  const start = script.indexOf('// ═══════════ 服装 Tab ═══════════');
  const end = script.indexOf('// 属性 → 颜色 CSS class', start);
  if (start < 0 || end < 0) throw new Error('clothing source markers not found');
  return script.slice(start, end);
}

function renderDashboardInSandbox(html, data, gameData) {
  const element = { innerHTML: '' };
  const script = extractInlineScript(html);
  const withoutInit = script.replace(/\binit\(\);\s*$/, '');
  if (withoutInit === script) throw new Error('dashboard sandbox could not remove init call');
  const sandbox = {
    __data: data,
    __gameData: gameData,
    document: {
      getElementById: id => {
        if (id === 'tab-dashboard') return element;
        if (id === 'source-modal') return { addEventListener: () => {} };
        return null;
      },
    },
    localStorage: {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    },
    fetch: async () => { throw new Error('unexpected fetch in dashboard sandbox'); },
    setTimeout: () => 0,
    clearTimeout: () => {},
  };
  vm.createContext(sandbox);
  const source = `${withoutInit}
    data = globalThis.__data;
    gameData = globalThis.__gameData;
    currentTab = 'dashboard';
    randomTasks = {};
    renderDashboard();
  `;
  new vm.Script(source, { filename: 'index.html#dashboard' }).runInContext(sandbox);
  return element.innerHTML;
}

function createClothingSandbox(html, options = {}) {
  const elements = options.elements || {};
  let saveCalls = 0;
  const sandbox = {
    __data: options.data || { clothing_progress: {} },
    __gameData: options.gameData || { clothing: { sets: [], pieces: [] } },
    __saveData: async () => { saveCalls += 1; },
    __addDoneToday: () => {},
    document: { getElementById: id => elements[id] || null },
  };
  vm.createContext(sandbox);
  const source = `
    let data = globalThis.__data;
    let gameData = globalThis.__gameData;
    let currentTab = 'validator';
    let clothingSearch = '';
    let clothingStatusFilter = 'all';
    let clothingTypeFilter = 'all';
    let clothingCategoryFilter = 'all';
    let expandedClothingSet = null;
    const STATUS = { DONE: '已收集', PENDING: '未收集' };
    async function saveData() { return globalThis.__saveData(); }
    function addDoneToday(entry) { return globalThis.__addDoneToday(entry); }
    function renderDashboard() {}
    ${extractClothingSource(html)}
    globalThis.__api = {
      isClothingTargetPiece,
      getClothingStats,
      getGorgeousMagicProgress,
      getClothingList,
      getClothingSetInfoStatus,
      getClothingMissingSetIds,
      sortClothingPieces,
      buildClothingDisplayEntries,
      renderClothingTab,
      renderClothingSetCard,
      renderClothingSingleRow,
      setClothingStatusFilter,
      setClothingCategoryFilter,
      toggleClothingPiece,
      escAttr,
    };
  `;
  new vm.Script(source, { filename: 'index.html#clothing' }).runInContext(sandbox);
  return {
    api: sandbox.__api,
    data: sandbox.__data,
    gameData: sandbox.__gameData,
    elements,
    getSaveCalls: () => saveCalls,
  };
}

async function validateUi(html) {
  const dashboardStart = html.indexOf('function renderDashboard()');
  const dashboardEnd = html.indexOf('function renderRandomModule(', dashboardStart);
  const dashboardSource = html.slice(dashboardStart, dashboardEnd);
  const tabStart = html.indexOf('function renderClothingTab()');
  const tabEnd = html.indexOf('function renderClothingContent()', tabStart);
  const tabSource = html.slice(tabStart, tabEnd);

  const checks = [
    ['server defines clothing data file', server.includes('CLOTHING_FILE')],
    ['server exposes api clothing endpoint', server.includes("url.pathname === '/api/clothing'")],
    ['game-data includes clothing and progress', server.includes('clothing') && server.includes('clothing_progress')],
    ['clothing tab routes to dedicated renderer', /if \(name === 'clothing'\) \{ renderClothingTab\(\); return; \}/.test(html)],
    ['renderClothingTab exists', /function\s+renderClothingTab\s*\(/.test(html)],
    ['renderClothingSetCard exists for set cards', /function\s+renderClothingSetCard\s*\(/.test(html)],
    ['renderClothingSingleRow exists for single items', /function\s+renderClothingSingleRow\s*\(/.test(html)],
    ['toggleClothingPiece exists', /async\s+function\s+toggleClothingPiece\s*\(/.test(html)],
    ['clothing renderer uses gameData.clothing sets and pieces', html.includes('gameData?.clothing') && html.includes('.sets') && html.includes('.pieces')],
    ['clothing progress is persisted separately', html.includes('clothing_progress')],
    ['clothing UI has type filter chips', html.includes('clothingTypeFilter') && html.includes('套装') && html.includes('单件')],
    ['clothing UI explains gorgeous badge from definitions', html.includes('华丽徽章说明') && /(?:gameData\?\.clothing|clothing)(?:\?\.|\.)definitions/.test(html) && html.includes('gorgeousBadge') && html.includes('gorgeousMagic')],
    ['clothing UI computes and renders gorgeous magic progress', /function\s+getGorgeousMagicProgress\s*\(\s*set\s*,\s*pieces\s*\)/.test(html) && /(?:const|let)\s+\w+\s*=\s*getGorgeousMagicProgress\s*\(\s*set\s*,\s*pieces\s*\)/.test(html) && html.includes('requiredPieceCount') && html.includes('magic_required')],
    ['clothing targets fail closed to standard pieces', /function\s+isClothingTargetPiece\s*\(\s*item\s*\)/.test(html) && /item\.obtainType\s*===\s*['"]standard['"]/.test(html)],
    ['clothing stats helper exists', /function\s+getClothingStats\s*\(\s*items\s*\)/.test(html)],
    ['dashboard and clothing tab share clothing stats', dashboardSource.includes('getClothingStats(clothing)') && tabSource.includes('getClothingStats(clothing)')],
    ['clothing UI renders paid non-target label conditionally', html.includes('付费 · 非收集目标') && /item\.obtainType\s*===\s*['"]paid['"]/.test(html)],
    ['clothing UI filters by piece category', /\bclothingCategoryFilter\s*=\s*['"]all['"]/.test(html) && /item\.category\s*===\s*clothingCategoryFilter/.test(html)],
    ['category filter rerenders toolbar selection state', /function\s+setClothingCategoryFilter\s*\(/.test(html) && html.includes("setClothingCategoryFilter('all')")],
    ['clothing names have leading set and single type labels', html.includes('clothing-kind-tag set') && html.includes('clothing-kind-tag single')],
    ['shared obtain method is rendered inline with clothing names', html.includes('clothing-name-note')],
    ['set cards expand manually like sprite cards', /const\s+isExpanded\s*=\s*expandedClothingSet\s*===\s*setKey\s*;/.test(html)],
    ['clothing UI uses shared tab hierarchy while preserving detailed cards', tabSource.includes('sprite-stats') && tabSource.includes('sprite-search') && tabSource.includes('tb-section') && html.includes('clothing-set-card') && html.includes('clothing-piece-row')],
    ['clothing UI exposes deterministic piece sorting helpers', /function\s+sortClothingPieces\s*\(/.test(html) && /function\s+buildClothingDisplayEntries\s*\(/.test(html)],
    ['UI no longer points to legacy pending CSV templates', !html.includes('data/_待采集/') && !/\bcsv\s*:/.test(html)],
    ['clothing UI shows set-level paired pet in card', html.includes('pairedPetName') && html.includes('配对精灵')],
    ['set card pieces do not duplicate shared set fields', html.includes("toggleClothingPiece('${item.id}')") && html.includes('pieceName')],
    ['clothing data file exists as sets and pieces object', Array.isArray(sets) && Array.isArray(pieces)],
    ['real set sample stores gorgeous magic contract', !!setSample && setSample.requiredPieceCount === 6 && setSample.gorgeousMagicPetName === '熔岩布丁' && !!setSample.obtainMethod],
    ['real set piece sample follows set detail contract', !!setPieceSample && setPieceSample.collectionType === 'set' && setPieceSample.setId === setSample?.id && setPieceSample.category === '玩偶服/连衣' && setPieceSample.setRole === 'magic_required' && setPieceSample.obtainType === 'standard'],
    ['real single sample follows standalone detail contract', !!singleSample && singleSample.collectionType === 'single' && !Object.prototype.hasOwnProperty.call(singleSample, 'setId') && !Object.prototype.hasOwnProperty.call(singleSample, 'setRole') && singleSample.category === '法杖' && singleSample.obtainType === 'standard' && !!singleSample.obtainMethod],
    ['collections has clothing_progress object', collections.clothing_progress && typeof collections.clothing_progress === 'object' && !Array.isArray(collections.clothing_progress)],
  ];

  let production;
  try {
    const elements = {
      'tab-clothing': { innerHTML: '' },
      'clothing-content': { innerHTML: '' },
    };
    production = createClothingSandbox(html, {
      data: { clothing_progress: { ...collections.clothing_progress } },
      gameData: { clothing },
      elements,
    });
    const list = production.api.getClothingList();
    const stats = production.api.getClothingStats(list);
    const missingSetIds = production.api.getClothingMissingSetIds(sets, list);
    production.api.renderClothingTab();
    const tabHtml = elements['tab-clothing'].innerHTML;
    const contentHtml = elements['clothing-content'].innerHTML;
    production.api.setClothingStatusFilter('missing');
    const missingTabHtml = elements['tab-clothing'].innerHTML;
    const missingContentHtml = elements['clothing-content'].innerHTML;
    production.api.setClothingStatusFilter('pending');
    const pendingContentHtml = elements['clothing-content'].innerHTML;
    production.api.setClothingStatusFilter('all');
    production.api.setClothingCategoryFilter('鞋子');
    const categorySelectedHtml = elements['tab-clothing'].innerHTML;
    checks.push(
      ['target predicate rejects paid unknown and missing types',
        production.api.isClothingTargetPiece({ obtainType: 'standard' })
        && !production.api.isClothingTargetPiece({ obtainType: 'paid' })
        && !production.api.isClothingTargetPiece({ obtainType: 'unknown' })
        && !production.api.isClothingTargetPiece({})],
      ['real clothing stats are 256 owned of 275 targets with 148 paid references',
        stats.targetTotal === 275 && stats.targetOwned === 256 && stats.paidTotal === 148],
      ['clothing tab renders shared clothing stats',
        tabHtml.includes('目标共 <strong>275</strong> 件 · 已收集 <strong>256</strong>')
        && tabHtml.includes('信息缺失套装 <strong>54</strong>')
        && tabHtml.includes('付费资料 <strong>148</strong> 件')],
      ['clothing tab follows title stats search filters content order without legacy wrappers',
        tabHtml.indexOf('👗 服装') < tabHtml.indexOf('sprite-stats')
        && tabHtml.indexOf('sprite-stats') < tabHtml.indexOf('sprite-search')
        && tabHtml.indexOf('sprite-search') < tabHtml.indexOf('展示类型')
        && !tabHtml.includes('clothing-overview') && !tabHtml.includes('clothing-toolbar')],
      ['definition-only sets remain visible as incomplete set cards',
        contentHtml.includes('异色朔夜伊芙印象')
        && contentHtml.includes('鎏金礼赞')
        && contentHtml.includes('<span class="sm">0/6</span>')
        && contentHtml.includes('<span class="sm">0/4</span>')],
      ['missing information filter reports and selects all 54 incomplete sets',
        missingSetIds.size === 54
        && missingTabHtml.includes('chip active')
        && missingTabHtml.includes("setClothingStatusFilter('missing')\">信息缺失 54</span>")],
      ['missing information filter includes partial and definition-only sets but excludes complete sets',
        missingContentHtml.includes('翠顶夫人印象')
        && missingContentHtml.includes('异色朔夜伊芙印象')
        && missingContentHtml.includes('clothing-set-badge missing')
        && !missingContentHtml.includes('电球咩咩印象')],
      ['pending filter also keeps acquired sets whose required piece information is incomplete',
        pendingContentHtml.includes('翠顶夫人印象')
        && pendingContentHtml.includes('信息缺失 3/6')],
      ['confirmed clothing corrections and new data are present',
        sets.some(set => set.name === '精灵学分院服' && set.requiredPieceCount === 4)
        && sets.some(set => set.name === '炼金学分院服' && set.requiredPieceCount === 4)
        && sets.some(set => set.name === '宁静星愿' && set.requiredPieceCount === 6)
        && pieces.some(item => item.pieceName === '眼型-花魁蜂后印象')
        && pieces.some(item => item.pieceName === '华丽徽章-小丑公爵')],
      ['category filter refreshes the active chip state',
        categorySelectedHtml.includes('chip active')
        && categorySelectedHtml.includes("setClothingCategoryFilter('鞋子')\">鞋子</span>")],
    );

    const sortedPieces = production.api.sortClothingPieces([
      { id: 'clothing_9', pieceName: '付费头饰', category: '头饰/帽子', obtainType: 'paid', setRole: 'optional' },
      { id: 'clothing_4', pieceName: '标准鞋子', category: '鞋子', obtainType: 'standard', setRole: 'magic_required' },
      { id: 'clothing_3', pieceName: '标准上衣', category: '上衣', obtainType: 'standard', setRole: 'magic_required' },
      { id: 'clothing_2', pieceName: '标准连衣', category: '玩偶服/连衣', obtainType: 'standard', setRole: 'magic_required' },
      { id: 'clothing_8', pieceName: '可选法杖', category: '法杖', obtainType: 'standard', setRole: 'optional' },
    ]);
    const displayEntries = production.api.buildClothingDisplayEntries([
      { id: 'clothing_40', collectionType: 'single', pieceName: '独立鞋子', category: '鞋子', obtainType: 'standard' },
      { id: 'clothing_11', collectionType: 'set', setId: 'clothing_set_2', pieceName: '套装二上衣', category: '上衣', obtainType: 'standard', set: { id: 'clothing_set_2', name: '二号套装' } },
      { id: 'clothing_10', collectionType: 'set', setId: 'clothing_set_1', pieceName: '套装一鞋子', category: '鞋子', obtainType: 'standard', set: { id: 'clothing_set_1', name: '一号套装' } },
      { id: 'clothing_9', collectionType: 'set', setId: 'clothing_set_1', pieceName: '套装一上衣', category: '上衣', obtainType: 'standard', set: { id: 'clothing_set_1', name: '一号套装' } },
      { id: 'clothing_41', collectionType: 'single', pieceName: '独立上衣', category: '上衣', obtainType: 'standard' },
    ]);
    checks.push(
      ['set pieces sort target required items before optional and paid references',
        sortedPieces.map(item => item.id).join(',') === 'clothing_2,clothing_3,clothing_4,clothing_8,clothing_9'],
      ['display entries group sets before singles and keep deterministic order',
        displayEntries.map(entry => entry.type === 'set' ? entry.setKey : entry.item.id).join(',') === 'clothing_set_1,clothing_set_2,clothing_41,clothing_40'
        && displayEntries[0].pieces.map(item => item.id).join(',') === 'clothing_9,clothing_10'],
    );

    const dashboardHtml = renderDashboardInSandbox(
      html,
      { activities: [], clothing_progress: { ...collections.clothing_progress }, meta: {} },
      { pets: {}, clothing, furniture: [], titles: [], dungeons: [] },
    );
    checks.push(
      ['dashboard renders shared target-only clothing stats',
        dashboardHtml.includes('<span class="ds-label">服装</span><span class="ds-val">256</span><span class="ds-total">/ 275</span>')],
    );

    const lavaPieces = list.filter(item => item.setId === setSample.id);
    const lavaTargetPieces = lavaPieces.filter(production.api.isClothingTargetPiece);
    const lavaPaidPieces = lavaPieces.filter(item => item.obtainType === 'paid');
    const magic = production.api.getGorgeousMagicProgress(setSample, lavaPieces);
    checks.push(
      ['lava pudding unlocks at 6 of 6 without four paid pieces',
        lavaTargetPieces.length === 6 && lavaPaidPieces.length === 4
        && magic?.acquired === 6 && magic.total === 6 && magic.unlocked === true],
    );

    const mixedMagic = production.api.getGorgeousMagicProgress(
      { requiredPieceCount: 3, gorgeousMagicPetName: '测试精灵' },
      [
        { obtainType: 'standard', setRole: 'magic_required', acquired: true },
        { obtainType: 'standard', setRole: 'magic_required', acquired: true },
        { obtainType: 'standard', setRole: 'magic_required', acquired: false },
        { obtainType: 'standard', setRole: 'optional', acquired: true },
        { obtainType: 'paid', setRole: 'magic_required', acquired: true },
        { obtainType: 'unknown', setRole: 'magic_required', acquired: true },
      ],
    );
    checks.push(
      ['gorgeous magic counts only acquired standard required pieces',
        mixedMagic?.acquired === 2 && mixedMagic.total === 3 && mixedMagic.unlocked === false],
    );

    const visibleLavaPieces = [lavaTargetPieces[0]];
    const lavaCard = production.api.renderClothingSetCard(setSample.id, setSample, visibleLavaPieces);
    checks.push(
      ['set card keeps full target denominator for visible subset',
        lavaCard.includes('<span class="sm">6/6</span>')],
    );

    const escaped = production.api.escAttr(`a"&'<>\\`);
    checks.push(
      ['attribute escaping protects html and javascript boundaries',
        escaped === `a&quot;&amp;\\'&lt;&gt;\\\\`],
    );

    const syntheticPiece = {
      id: 'synthetic_piece', collectionType: 'set', setId: 'synthetic_set',
      pieceName: '测试部件', category: '上衣', obtainType: 'standard', acquired: false,
      obtainMethod: '不应在部件下重复显示',
    };
    const syntheticSet = { id: 'synthetic_set', name: '测试套装', obtainMethod: '套装统一获取方式' };
    const unknownSet = production.api.renderClothingSetCard('synthetic_set', syntheticSet, [syntheticPiece]);
    const trueSet = production.api.renderClothingSetCard('synthetic_set', { ...syntheticSet, hasEffect: true }, [syntheticPiece]);
    const falseSet = production.api.renderClothingSetCard('synthetic_set', { ...syntheticSet, hasEffect: false }, [syntheticPiece]);
    const singleBase = { id: 'synthetic_single', collectionType: 'single', pieceName: '测试单件', category: '上衣', obtainType: 'standard', obtainMethod: '单品获取方式' };
    const unknownSingle = production.api.renderClothingSingleRow(singleBase);
    const pendingMethodSingle = production.api.renderClothingSingleRow({ ...singleBase, obtainMethod: '待补充' });
    const trueSingle = production.api.renderClothingSingleRow({ ...singleBase, hasEffect: true });
    const falseSingle = production.api.renderClothingSingleRow({ ...singleBase, hasEffect: false });
    const paidPiece = { ...syntheticPiece, id: 'paid_piece', obtainType: 'paid' };
    const unknownPiece = { ...syntheticPiece, id: 'unknown_piece', obtainType: 'unknown' };
    const missingTypePiece = { ...syntheticPiece, id: 'missing_type_piece', obtainType: undefined };
    const standardSetRow = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装' }, [syntheticPiece]);
    const paidSetRow = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装' }, [paidPiece]);
    const unknownSetRow = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装' }, [unknownPiece]);
    const missingTypeSetRow = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装' }, [missingTypePiece]);
    const paidSingle = production.api.renderClothingSingleRow({ ...singleBase, id: 'paid_single', obtainType: 'paid' });
    const unknownTypeSingle = production.api.renderClothingSingleRow({ ...singleBase, id: 'unknown_single', obtainType: 'unknown' });
    const missingTypeSingle = production.api.renderClothingSingleRow({ ...singleBase, id: 'missing_single', obtainType: undefined });
    checks.push(
      ['set effect metadata distinguishes unknown true and false',
        !unknownSet.includes('特效：') && trueSet.includes('特效：有') && falseSet.includes('特效：无')],
      ['single effect metadata distinguishes unknown true and false',
        !unknownSingle.includes('特效：') && trueSingle.includes('特效：有') && falseSingle.includes('特效：无')],
      ['set and single type labels appear before their names',
        unknownSet.indexOf('clothing-kind-tag set') < unknownSet.indexOf('测试套装')
        && unknownSingle.indexOf('clothing-kind-tag single') < unknownSingle.indexOf('测试单件')],
      ['set obtain method is inline once and not repeated under pieces',
        unknownSet.includes('clothing-name-note') && unknownSet.includes('套装统一获取方式')
        && !unknownSet.includes('不应在部件下重复显示')],
      ['single obtain method is inline with its name',
        unknownSingle.includes('clothing-name-note') && unknownSingle.includes('单品获取方式')],
      ['pending obtain method placeholders stay hidden',
        !pendingMethodSingle.includes('clothing-name-note') && !pendingMethodSingle.includes('待补充')],
      ['set piece controls distinguish standard paid and invalid metadata',
        standardSetRow.includes('check-btn')
        && !paidSetRow.includes('check-btn') && paidSetRow.includes('付费 · 非收集目标')
        && !unknownSetRow.includes('check-btn') && unknownSetRow.includes('资料异常 · 不可操作')
        && !missingTypeSetRow.includes('check-btn') && missingTypeSetRow.includes('资料异常 · 不可操作')],
      ['single controls distinguish standard paid and invalid metadata',
        production.api.renderClothingSingleRow(singleBase).includes('check-btn')
        && !paidSingle.includes('check-btn') && paidSingle.includes('付费 · 非收集目标')
        && !unknownTypeSingle.includes('check-btn') && unknownTypeSingle.includes('资料异常 · 不可操作')
        && !missingTypeSingle.includes('check-btn') && missingTypeSingle.includes('资料异常 · 不可操作')],
    );
  } catch (error) {
    checks.push(['production clothing functions execute in sandbox', false]);
    checks.push([`sandbox error: ${error.message}`, false]);
  }

  try {
    const standard = { id: 'standard_id', collectionType: 'single', pieceName: '标准', obtainType: 'standard' };
    const paid = { id: 'paid_id', collectionType: 'single', pieceName: '付费', obtainType: 'paid' };
    const unknown = { id: 'unknown_type_id', collectionType: 'single', pieceName: '未知', obtainType: 'unknown' };
    const toggle = createClothingSandbox(html, {
      data: { clothing_progress: {} },
      gameData: { clothing: { sets: [], pieces: [standard, paid, unknown] } },
    });
    const before = JSON.stringify(toggle.data.clothing_progress);
    await toggle.api.toggleClothingPiece(paid.id);
    await toggle.api.toggleClothingPiece(unknown.id);
    await toggle.api.toggleClothingPiece('missing_id');
    const rejectedUnchanged = JSON.stringify(toggle.data.clothing_progress) === before && toggle.getSaveCalls() === 0;
    await toggle.api.toggleClothingPiece(standard.id);
    checks.push(
      ['toggle rejects paid unknown-type and missing ids before saving', rejectedUnchanged],
      ['toggle persists standard piece normally', toggle.data.clothing_progress[standard.id] === true && toggle.getSaveCalls() === 1],
    );
  } catch (error) {
    checks.push([`toggle sandbox error: ${error.message}`, false]);
  }

  return {
    checks: checks.length,
    failures: checks.filter(([, ok]) => !ok).map(([name]) => name),
  };
}

async function main() {
  const result = await validateUi(defaultHtml);
  if (result.failures.length) {
    console.error(result.failures.join('\n'));
    process.exit(1);
  }
  console.log(JSON.stringify({ checks: result.checks }, null, 2));
}

if (require.main === module) {
  main().catch(error => {
    console.error(error);
    process.exit(1);
  });
}

module.exports = { validateUi };
