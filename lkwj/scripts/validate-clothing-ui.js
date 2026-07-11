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
      renderClothingTab,
      renderClothingSetCard,
      renderClothingSingleRow,
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
    production.api.renderClothingTab();
    const tabHtml = elements['tab-clothing'].innerHTML;
    checks.push(
      ['target predicate rejects paid unknown and missing types',
        production.api.isClothingTargetPiece({ obtainType: 'standard' })
        && !production.api.isClothingTargetPiece({ obtainType: 'paid' })
        && !production.api.isClothingTargetPiece({ obtainType: 'unknown' })
        && !production.api.isClothingTargetPiece({})],
      ['real clothing stats are 242 owned targets and 136 paid references',
        stats.targetTotal === 242 && stats.targetOwned === 242 && stats.paidTotal === 136],
      ['clothing tab renders shared clothing stats',
        tabHtml.includes('目标共 <strong>242</strong> 件 · 已收集 <strong>242</strong>')
        && tabHtml.includes('付费资料 <strong>136</strong> 件')],
    );

    const dashboardHtml = renderDashboardInSandbox(
      html,
      { activities: [], clothing_progress: { ...collections.clothing_progress }, meta: {} },
      { pets: {}, clothing, furniture: [], titles: [], dungeons: [] },
    );
    checks.push(
      ['dashboard renders shared target-only clothing stats',
        dashboardHtml.includes('<span class="ds-label">服装</span><span class="ds-val">242</span><span class="ds-total">/ 242</span>')],
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
    };
    const unknownSet = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装' }, [syntheticPiece]);
    const trueSet = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装', hasEffect: true }, [syntheticPiece]);
    const falseSet = production.api.renderClothingSetCard('synthetic_set', { id: 'synthetic_set', name: '测试套装', hasEffect: false }, [syntheticPiece]);
    const singleBase = { id: 'synthetic_single', collectionType: 'single', pieceName: '测试单件', category: '上衣', obtainType: 'standard' };
    const unknownSingle = production.api.renderClothingSingleRow(singleBase);
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
