const state = {
  catalog: null,
  cases: [],
  selectedCase: null,
  selectedProduct: null,
  mode: "custom",
  brandId: "kgos",
  lines: [],
  cartonId: "",
  result: null,
  view: "iso",
  catalogSection: "cartons",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const COLORS = ["#4f79c8", "#6f8f4f", "#a86e55", "#7d69ad", "#3f8c91", "#b0803e", "#c06480"];

const labels = {
  experiment_allowed: "输入可计算",
  capability_not_enabled: "暂未开放",
  missing_product_dimensions: "缺少尺寸",
  brand_mismatch: "品牌不匹配",
  carton_not_integrated: "纸箱不可用于计算",
  carton_retired: "纸箱已停用",
  carton_scope_restricted: "纸箱用途受限",
  blocked_by_confirmed_rule: "规则限制",
  fits_inner_geometry: "找到摆放",
  fits_outer_bound_only: "仅理论可放",
  does_not_fit: "当前箱不合适",
  unknown: "暂时无法判断",
  not_run: "未计算",
  confirmed_capacity: "固定箱规",
  confirmed_rule: "固定规则",
  geometry_only: "几何计算",
  geometry_result: "几何结果",
  insufficient: "资料不足",
  catalog_only: "仅资料展示",
  none: "无",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function initNavigation() {
  $$(".main-tab").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".main-tab").forEach((item) => item.classList.toggle("is-active", item === button));
      $$(".page").forEach((page) => page.classList.toggle("is-active", page.id === button.dataset.tab));
      if (button.dataset.tab === "catalog") renderCatalog();
      else requestAnimationFrame(drawPacking);
    });
  });
}

async function loadCatalog() {
  state.catalog = await api("/api/catalog");
  const preferred = state.catalog.brands.find((item) => item.brandId === "kgos");
  state.brandId = preferred?.brandId || state.catalog.brands[0]?.brandId || "";
  renderBrandButtons();
  renderBrandCapability();
  clearProductSearch();
  renderCartonSelect();
  renderCatalog();
}

function brandInfo(brandId = state.brandId) {
  return state.catalog?.brands.find((item) => item.brandId === brandId) || null;
}

function renderBrandButtons() {
  const container = $("#brand-buttons");
  container.innerHTML = "";
  state.catalog.brands.forEach((brand) => {
    const button = document.createElement("button");
    button.className = `brand-button${brand.brandId === state.brandId ? " is-active" : ""}`;
    button.textContent = brand.displayName;
    button.addEventListener("click", () => selectBrand(brand.brandId));
    container.append(button);
  });
}

function selectBrand(brandId) {
  if (brandId === state.brandId) return;
  state.brandId = brandId;
  state.lines = [];
  state.selectedCase = null;
  state.cartonId = "";
  state.selectedProduct = null;
  resetResult();
  clearProductSearch();
  renderBrandButtons();
  renderBrandCapability();
  renderCartonSelect();
  renderLines();
  renderSavedAnswer();
}

function renderBrandCapability() {
  const brand = brandInfo();
  $("#simulation-brand-name").textContent = brand?.displayName || state.brandId.toUpperCase();
  $("#brand-capability").textContent = brand?.packingStatus === "enabled_single_carton"
    ? "纯算法模拟，不使用已保存的固定箱规答案。"
    : brand?.packingMessage || "当前品牌只展示资料。";
  updateRunButton();
}

function productDirectoryForBrand() {
  return (state.catalog.sections.productDirectory || []).filter((item) => item.brandId === state.brandId);
}

function searchableProductRows() {
  return productDirectoryForBrand();
}

function directoryItemForProduct(code = "", fallbackName = "") {
  const normalizedCode = String(code || "").trim();
  const normalizedName = String(fallbackName || "").trim();
  const directory = state.catalog?.sections?.productDirectory || [];
  if (normalizedCode) {
    const byCode = directory.find((item) =>
      (item.merchantCodes || []).includes(normalizedCode) || item.simulationCode === normalizedCode
    );
    if (byCode) return byCode;
  }
  if (normalizedName) {
    const byName = directory.find((item) =>
      item.shortName === normalizedName
      || item.fullName === normalizedName
      || (item.aliases || []).includes(normalizedName)
    );
    if (byName) return byName;
  }
  return null;
}

function clearProductSearch() {
  state.selectedProduct = null;
  const input = $("#product-search-input");
  const results = $("#product-search-results");
  if (input) input.value = "";
  if (results) {
    results.innerHTML = "";
    results.hidden = true;
  }
  const selected = $("#selected-product-name");
  if (selected) {
    selected.textContent = "先搜索并选择商品";
    selected.title = "";
    selected.classList.remove("is-missing");
  }
  if ($("#add-product")) $("#add-product").disabled = true;
}

function renderProductSearchResults() {
  const input = $("#product-search-input");
  const container = $("#product-search-results");
  const query = input.value.trim().toLowerCase();
  container.innerHTML = "";
  const matches = searchableProductRows().filter((item) => {
    const searchable = [
      item.shortName,
      item.fullName,
      ...(item.aliases || []),
      ...(item.merchantCodes || []),
    ].join(" ").toLowerCase();
    return !query || searchable.includes(query);
  }).slice(0, 60);
  if (!matches.length) {
    const empty = document.createElement("div");
    empty.className = "search-empty";
    empty.textContent = "没有匹配商品";
    container.append(empty);
    container.hidden = false;
    return;
  }
  matches.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-result";
    const heading = document.createElement("div");
    heading.className = "search-result-heading";
    const title = document.createElement("strong");
    title.textContent = item.shortName;
    heading.append(title);
    if (item.missingDimensions) {
      const badge = document.createElement("em");
      badge.className = "inline-missing-badge";
      badge.textContent = "待补尺寸";
      heading.append(badge);
    } else if (item.packingBehavior === "ignored_zero_space") {
      const badge = document.createElement("em");
      badge.className = "inline-neutral-badge";
      badge.textContent = "不计体积";
      heading.append(badge);
    }
    const subtitle = document.createElement("span");
    subtitle.textContent = item.fullName || "商品全称待核对";
    button.append(heading, subtitle);
    button.addEventListener("click", () => {
      state.selectedProduct = item;
      input.value = item.shortName;
      container.hidden = true;
      const selected = $("#selected-product-name");
      selected.textContent = item.missingDimensions
        ? `${item.shortName} · 待补尺寸`
        : item.packingBehavior === "ignored_zero_space"
          ? `${item.shortName} · 不计体积`
          : item.shortName;
      selected.classList.toggle("is-missing", item.missingDimensions);
      selected.title = item.fullName || item.shortName;
      $("#add-product").disabled = false;
    });
    container.append(button);
  });
  container.hidden = false;
}

function displayNameForCode(code, fallbackName = "") {
  const directory = directoryItemForProduct(code, fallbackName);
  if (directory) return directory.shortName;
  const product = state.catalog.sections.products.find((item) => item.merchantCodes.includes(code));
  if (product) return product.displayName;
  const pending = state.catalog.sections.pending.find((item) => item.currentMerchantCode === code);
  return pending?.shortName || pending?.label || fallbackName || code;
}

function brandForCode(code, fallbackName = "") {
  const directory = directoryItemForProduct(code, fallbackName);
  if (directory) return directory.brandId;
  const product = state.catalog.sections.products.find((item) => item.merchantCodes.includes(code));
  if (product) return product.brandId;
  const pending = state.catalog.sections.pending.find((item) => item.currentMerchantCode === code);
  return pending?.brandId || "";
}

function addLine(code, quantity, extra = {}) {
  const identity = extra.productKey || code || extra.productName;
  const existing = state.lines.find((item) =>
    (item.productKey || item.merchantCode || item.productName) === identity
    && !item.sourceProductId
    && !extra.sourceProductId
  );
  if (existing) existing.quantity += quantity;
  else state.lines.push({
    merchantCode: code,
    productKey: extra.productKey || "",
    quantity,
    productName: extra.productName || displayNameForCode(code),
    missingDimensions: Boolean(extra.missingDimensions),
    packingBehavior: extra.packingBehavior || "normal",
    sourceProductId: extra.sourceProductId || "",
    platformOrderNumber: extra.platformOrderNumber || "",
  });
  resetResult();
  renderLines();
  renderCartonSelect();
}

function renderLines() {
  const container = $("#experiment-lines");
  container.innerHTML = "";
  container.classList.toggle("empty", !state.lines.length);
  if (!state.lines.length) {
    container.textContent = "还没有商品";
    updateRunButton();
    return;
  }
  state.lines.forEach((line, index) => {
    const row = document.createElement("div");
    row.className = "product-row";
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = line.productName || displayNameForCode(line.merchantCode);
    const qty = document.createElement("span");
    qty.textContent = ` × ${line.quantity}`;
    text.append(name, qty);
    if (line.missingDimensions) {
      const badge = document.createElement("em");
      badge.className = "inline-missing-badge";
      badge.textContent = "待补尺寸";
      text.append(badge);
    } else if (line.packingBehavior === "ignored_zero_space") {
      const badge = document.createElement("em");
      badge.className = "inline-neutral-badge";
      badge.textContent = "不计体积";
      text.append(badge);
    }
    const remove = document.createElement("button");
    remove.textContent = "移除";
    remove.addEventListener("click", () => {
      state.lines.splice(index, 1);
      resetResult();
      renderLines();
      renderCartonSelect();
    });
    row.append(text, remove);
    container.append(row);
  });
  updateRunButton();
}

function eligibleOriginalCartons() {
  const geometryLines = state.lines.filter((line) => line.packingBehavior !== "ignored_zero_space");
  if (!geometryLines.length) return [];
  const quantities = new Map();
  geometryLines.forEach((line) => {
    quantities.set(line.merchantCode, (quantities.get(line.merchantCode) || 0) + line.quantity);
  });
  if (quantities.size !== 1) return [];
  const [[merchantCode, quantity]] = [...quantities.entries()];
  return (state.catalog.sections.originalCartons || [])
    .filter((item) => item.brandId === state.brandId)
    .filter((item) => item.inventoryStatus !== "retired")
    .filter((item) => Array.isArray(item.dimensionsMm) && item.dimensionsMm.length === 3)
    .filter((item) => (item.allowedMerchantCodes || []).includes(merchantCode))
    .filter((item) => {
      const minimum = Number(item.minimumShippableQuantity || item.capacity || 0);
      const maximum = Number(item.capacity || 0);
      return minimum > 0 && maximum >= minimum && quantity >= minimum && quantity <= maximum;
    })
    .map((item) => ({ ...item, isOriginalCarton: true }));
}

function cartonOptionsForBrand() {
  const active = state.catalog.sections.cartons
    .filter((item) => item.brandId === state.brandId)
    .map((item) => ({ ...item, displayName: item.displayName || item.label || item.cartonId }));
  const pending = (state.catalog.sections.pendingCartons || [])
    .filter((item) => item.brandId === state.brandId)
    .map((item) => ({ ...item, displayName: item.displayName || item.label || item.cartonId }));
  const original = eligibleOriginalCartons()
    .map((item) => ({ ...item, displayName: item.displayName || item.label || item.cartonId }));
  const seen = new Set();
  return [...active, ...pending, ...original].filter((item) => {
    const key = item.cartonId || item.displayName;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function cartonSortKey(item) {
  const match = item.displayName.match(/([一二三四五六七八九十百两\d]+)盒/);
  if (!match) return [item.displayName, 999];
  return [item.displayName.replace(match[0], ""), chineseNumber(match[1])];
}

function chineseNumber(value) {
  if (/^\d+$/.test(value)) return Number(value);
  const map = { 一:1, 二:2, 两:2, 三:3, 四:4, 五:5, 六:6, 七:7, 八:8, 九:9, 十:10, 百:100 };
  if (value === "十") return 10;
  if (value.includes("十")) {
    const [a, b] = value.split("十");
    return (a ? map[a] : 1) * 10 + (b ? map[b] : 0);
  }
  return map[value] || 999;
}

function renderCartonSelect() {
  const select = $("#carton-select");
  select.innerHTML = "";
  const automatic = document.createElement("option");
  automatic.value = "";
  automatic.textContent = "系统自动选择";
  select.append(automatic);
  const cartons = [...cartonOptionsForBrand()].sort((a, b) => {
    const [aName, aQty] = cartonSortKey(a);
    const [bName, bQty] = cartonSortKey(b);
    return aName.localeCompare(bName, "zh-CN") || aQty - bQty;
  });
  cartons.forEach((carton) => {
    const option = document.createElement("option");
    option.value = carton.cartonId;
    option.textContent = carton.displayName;
    select.append(option);
  });
  if (state.cartonId && !cartons.some((carton) => carton.cartonId === state.cartonId)) {
    state.cartonId = "";
  }
  select.value = state.cartonId;
  select.onchange = () => {
    state.cartonId = select.value;
    resetResult();
  };
}

function setMode(mode) {
  state.mode = mode;
  state.selectedCase = null;
  state.lines = [];
  state.cartonId = "";
  state.selectedProduct = null;
  resetResult();
  clearProductSearch();
  const custom = mode === "custom";
  $("#custom-source").hidden = !custom;
  $("#history-source").hidden = custom;
  $("#mode-custom").classList.toggle("is-active", custom);
  $("#mode-history").classList.toggle("is-active", !custom);
  $("#history-answer-panel").hidden = true;
  renderLines();
  renderCartonSelect();
  if (!custom && !state.cases.length) loadCases();
}

async function loadCases() {
  const list = $("#case-list");
  list.innerHTML = '<div class="case-products">正在读取历史订单…</div>';
  try {
    const payload = await api("/api/cases");
    state.cases = payload.cases;
    renderCases();
  } catch (error) {
    list.innerHTML = "";
    const message = document.createElement("div");
    message.className = "case-products";
    message.textContent = `读取失败：${error.message}`;
    list.append(message);
  }
}

function renderCases() {
  const query = $("#case-search").value.trim().toLowerCase();
  const list = $("#case-list");
  list.innerHTML = "";
  const cases = state.cases.filter((item) => {
    const searchable = [
      item.systemOrderId,
      ...item.platformOrderNumbers,
      ...item.products.map((product) => product.displayName),
    ].join(" ").toLowerCase();
    return searchable.includes(query);
  });
  cases.slice(0, 80).forEach((item) => {
    const card = document.createElement("div");
    card.className = `case-item${state.selectedCase?.caseId === item.caseId ? " is-selected" : ""}`;
    const title = document.createElement("div");
    title.className = "case-title";
    const order = document.createElement("span");
    order.textContent = item.systemOrderId || item.platformOrderNumbers[0] || "历史订单";
    const packageCount = document.createElement("span");
    packageCount.textContent = `${item.packageCount} 包`;
    title.append(order, packageCount);
    const products = document.createElement("div");
    products.className = "case-products";
    products.textContent = item.products
      .map((product) => `${displayNameForCode(product.merchantCode, product.standardName || product.displayName || product.shortName)} ×${product.quantity}`)
      .join("、");
    card.append(title, products);
    card.addEventListener("click", () => selectCase(item.caseId));
    list.append(card);
  });
  if (!cases.length) {
    const empty = document.createElement("div");
    empty.className = "case-products";
    empty.textContent = "没有匹配的历史订单";
    list.append(empty);
  }
}

async function selectCase(caseId) {
  const payload = await api(`/api/cases/${encodeURIComponent(caseId)}`);
  state.selectedCase = payload.case;
  state.lines = payload.case.products.map((product) => {
    const directory = directoryItemForProduct(
      product.merchantCode,
      product.standardName || product.displayName || product.shortName,
    );
    return {
      merchantCode: directory?.simulationCode || product.merchantCode,
      productKey: directory?.productKey || "",
      quantity: product.quantity,
      sourceProductId: product.sourceProductId,
      productName: directory?.shortName || product.displayName || product.merchantCode,
      missingDimensions: directory ? directory.missingDimensions : !state.catalog.sections.products.some(
        (item) => item.merchantCodes.includes(product.merchantCode)
      ),
      packingBehavior: directory?.packingBehavior || "normal",
      platformOrderNumber: product.platformOrderNumber,
    };
  });
  const brands = new Set(
    payload.case.products
      .map((product) => brandForCode(
        product.merchantCode,
        product.standardName || product.displayName || product.shortName,
      ))
      .filter(Boolean)
  );
  state.brandId = brands.size === 1 ? [...brands][0] : "";
  state.cartonId = "";
  resetResult();
  renderBrandButtons();
  renderBrandCapability();
  renderCases();
  renderLines();
  renderCartonSelect();
  renderSavedAnswer();
}

function renderSavedAnswer() {
  const panel = $("#history-answer-panel");
  const container = $("#saved-packages");
  container.innerHTML = "";
  panel.hidden = !state.selectedCase;
  if (!state.selectedCase) return;
  state.selectedCase.savedPackages.forEach((pkg, index) => {
    const card = document.createElement("div");
    card.className = "saved-package";
    const title = document.createElement("h4");
    title.textContent = `第 ${index + 1} 包 · ${pkg.totalQuantity} 件`;
    card.append(title);
    pkg.items.forEach((item) => {
      const line = document.createElement("p");
      const source = state.selectedCase.products.find(
        (product) => product.sourceProductId === item.sourceProductId
      );
      const fallbackName = source?.standardName || source?.displayName || source?.shortName || item.productName;
      line.textContent = `${displayNameForCode(item.merchantCode, fallbackName)} × ${item.quantity}`;
      card.append(line);
    });
    container.append(card);
  });
}

function resetResult() {
  state.result = null;
  $("#result-empty").hidden = false;
  $("#result-content").hidden = true;
  $("#canvas-message").hidden = true;
  $("#result-badge").className = "result-badge idle";
  $("#result-badge").textContent = "等待计算";
  updateRunButton();
  requestAnimationFrame(drawPacking);
}

function updateRunButton() {
  const brand = brandInfo();
  const hasIncompleteProduct = state.lines.some((line) => line.missingDimensions || !line.merchantCode);
  $("#run-assessment").disabled = !(
    state.lines.length
    && !hasIncompleteProduct
    && brand?.packingStatus === "enabled_single_carton"
  );
}

async function runAssessment() {
  const button = $("#run-assessment");
  const error = $("#run-error");
  error.hidden = true;
  button.disabled = true;
  button.textContent = "正在模拟…";
  try {
    state.result = await api("/api/assess", {
      method: "POST",
      body: JSON.stringify({
        brandId: state.brandId,
        cartonId: state.cartonId || null,
        lines: state.lines,
        maxSearchNodes: 100000,
      }),
    });
    renderResult();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.textContent = "开始模拟";
    updateRunButton();
  }
}

function renderResult() {
  const result = state.result;
  if (!result) return resetResult();
  $("#result-empty").hidden = true;
  $("#result-content").hidden = false;

  const selection = result.selection || {};
  const selectedName = selection.selectedCartonName;
  const geometry = result.geometry;
  const business = result.business;
  const evidence = result.evidence;

  $("#selected-carton-name").textContent = selectedName || "暂时没有选出纸箱";
  $("#answer-note").textContent = selection.message || "纯算法模拟结果";

  const badge = $("#result-badge");
  if (selectedName && geometry.status === "fits_inner_geometry" && business.status === "experiment_allowed") {
    badge.className = "result-badge good";
    badge.textContent = "找到摆法";
  } else if (business.status === "brand_mismatch") {
    badge.className = "result-badge bad";
    badge.textContent = "输入不适用";
  } else {
    badge.className = "result-badge warn";
    badge.textContent = labels[geometry.status] || "需要确认";
  }

  $("#business-status").textContent = labels[business.status] || business.status;
  $("#business-detail").textContent = (business.reasons || []).join("；") || "—";
  $("#geometry-status").textContent = labels[geometry.status] || geometry.status;
  $("#geometry-detail").textContent = geometry.message || geometry.reason || "—";
  $("#evidence-status").textContent = labels[evidence.level] || evidence.level;
  $("#evidence-detail").textContent = evidence.summary || "—";

  drawPacking();
}

function initControls() {
  $("#mode-custom").addEventListener("click", () => setMode("custom"));
  $("#mode-history").addEventListener("click", () => setMode("history"));
  $("#case-search").addEventListener("input", renderCases);

  $("#product-search-input").addEventListener("input", () => {
    state.selectedProduct = null;
    $("#add-product").disabled = true;
    $("#selected-product-name").textContent = "先搜索并选择商品";
    $("#selected-product-name").classList.remove("is-missing");
    renderProductSearchResults();
  });
  $("#product-search-input").addEventListener("focus", renderProductSearchResults);

  $("#add-product").addEventListener("click", () => {
    const item = state.selectedProduct;
    const code = item?.simulationCode || item?.merchantCodes?.[0] || "";
    const quantity = Number($("#quantity-input").value);
    if (!item || !Number.isInteger(quantity) || quantity <= 0) return;
    addLine(code, quantity, {
      productKey: item.productKey,
      productName: item.shortName,
      missingDimensions: item.missingDimensions,
      packingBehavior: item.packingBehavior,
    });
    clearProductSearch();
  });

  $("#clear-lines").addEventListener("click", () => {
    state.lines = [];
    state.selectedCase = null;
    resetResult();
    renderLines();
    renderCartonSelect();
    renderSavedAnswer();
  });

  $("#load-example").addEventListener("click", () => {
    setMode("custom");
    state.brandId = "kgos";
    state.lines = [{ merchantCode: "6977987940138", quantity: 3, productName: displayNameForCode("6977987940138") || "美式咖啡" }];
    state.cartonId = "";
    renderBrandButtons();
    renderBrandCapability();
    renderCartonSelect();
    resetResult();
    renderLines();
  });

  $("#run-assessment").addEventListener("click", runAssessment);
  $$(".view-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      $$(".view-button").forEach((item) => item.classList.toggle("is-active", item === button));
      drawPacking();
    });
  });
  $("#layer-slider").addEventListener("input", drawPacking);
  window.addEventListener("resize", () => requestAnimationFrame(drawPacking));

  Array.from(document.querySelectorAll(".catalog-tab")).forEach((button) => {
    button.addEventListener("click", () => {
      state.catalogSection = button.dataset.section;
      Array.from(document.querySelectorAll(".catalog-tab")).forEach((item) => item.classList.toggle("is-active", item === button));
      renderCatalog();
    });
  });
  $("#catalog-search").addEventListener("input", renderCatalog);

  document.addEventListener("click", (event) => {
    const searchBlock = $(".product-search-block");
    if (searchBlock && !searchBlock.contains(event.target)) $("#product-search-results").hidden = true;
  });
}

function tagged(items, type) {
  return (items || []).map((item) => ({ ...item, _recordType: type }));
}

function productForSpecId(productSpecId) {
  return state.catalog.sections.products.find((item) => item.productSpecId === productSpecId);
}

function productForCodes(codes = []) {
  return state.catalog.sections.products.find((item) => codes.some((code) => item.merchantCodes.includes(code)));
}

function productNameForRule(item) {
  const direct = productForSpecId(item.productSpecId || item.confirmedArrangement?.productSpecId);
  if (direct) return direct.displayName;
  const codes = item.allowedMerchantCodes || (item.currentMerchantCode ? [item.currentMerchantCode] : []);
  const directory = (state.catalog.sections.productDirectory || []).find((entry) => (entry.merchantCodes || []).some((code) => codes.includes(code)));
  if (directory) return directory.shortName;
  const byCode = productForCodes(codes);
  if (byCode) return byCode.displayName;
  return "其他";
}

function brandForCatalogItem(item) {
  if (item.brandId) return item.brandId;
  if (item._recordType === "单品尺寸") return item.brandId || "other";
  const direct = productForSpecId(item.productSpecId || item.confirmedArrangement?.productSpecId);
  if (direct) return direct.brandId;
  const codes = item.allowedMerchantCodes || item.merchantCodes || (item.currentMerchantCode ? [item.currentMerchantCode] : []);
  const directory = (state.catalog.sections.productDirectory || []).find((entry) => (entry.merchantCodes || []).some((code) => codes.includes(code)));
  return directory?.brandId || productForCodes(codes)?.brandId || "other";
}

function catalogItems(section) {
  const sections = state.catalog.sections;
  if (section === "cartons") {
    return [
      ...tagged(sections.cartons, "普通纸箱"),
      ...tagged(sections.originalCartons, "产品原箱"),
      ...tagged(sections.pendingCartons, "普通纸箱"),
    ];
  }
  if (section === "products") {
    return tagged(sections.productDirectory || [], "单品尺寸");
  }
  if (section === "businessRules") {
    return [
      ...tagged(sections.fixedPackingRules, "固定装箱"),
      ...tagged(sections.confirmedCapacities, "已确认箱量"),
      ...tagged(sections.quantityRules, "每箱数量"),
      ...tagged(sections.singlePackageExclusions, "拆箱规则"),
      ...tagged(sections.geometryExclusions, "尺寸限制"),
      ...tagged(sections.fitChecks, "已验证摆法"),
    ];
  }
  return [];
}

function catalogTitle(item) {
  if (state.catalogSection === "products") return item.shortName || "未命名单品";
  return item.displayName || item.label || item.ruleId || item.cartonId || "未命名资料";
}

function catalogSubtitle(item) {
  if (state.catalogSection === "products") return item.fullName || "商品全称待核对";
  if (state.catalogSection === "businessRules") return productNameForRule(item);
  return "";
}

function visibleFacts(item) {
  if (state.catalogSection === "cartons") {
    return item.dimensionsMm ? [`${item.dimensionsMm.join(" × ")} mm`] : ["尺寸待补"];
  }
  if (state.catalogSection === "products") {
    const rows = [];
    if (item.mainMerchantCode) {
      const spec = item.specMerchantCodes?.length ? `；规格编码：${item.specMerchantCodes.join(" / ")}` : "";
      rows.push(`编码：${item.mainMerchantCode}${spec}`);
    } else if (item.merchantCodes?.length) {
      rows.push(`编码：${item.merchantCodes.join(" / ")}`);
    } else {
      rows.push("编码：待核对");
    }
    if (item.packingBehavior === "ignored_zero_space") rows.push("尺寸：不计体积");
    else rows.push(item.dimensionsMm ? `尺寸：${item.dimensionsMm.join(" × ")} mm` : "尺寸：待补");
    return rows;
  }
  const rows = [];
  if (item.cartonId) rows.push(`纸箱：${cartonName(item.cartonId) || item.cartonId}`);
  if (item.capacity) rows.push(`数量：${item.capacity}`);
  if (item.minimumQuantity || item.maximumQuantity) rows.push(`每箱：${item.minimumQuantity || 1}–${item.maximumQuantity || "?"}`);
  if (item.totalQuantity) rows.push(`数量：${item.totalQuantity}`);
  return rows.length ? rows : ["详情待整理"];
}

function cartonName(cartonId) {
  const active = state.catalog.sections.cartons.find((item) => item.cartonId === cartonId);
  if (active) return active.displayName;
  const original = state.catalog.sections.originalCartons.find((item) => item.cartonId === cartonId);
  if (original) return original.displayName;
  const pending = state.catalog.sections.pendingCartons.find((item) => item.cartonId === cartonId);
  return pending?.displayName || pending?.label || "";
}

function hasMissingDimensions(item) {
  if (state.catalogSection === "products") return Boolean(item.missingDimensions);
  if (state.catalogSection === "cartons") return !Array.isArray(item.dimensionsMm);
  return false;
}

function cartonProductGroup(item) {
  if (item._recordType === "产品原箱") {
    const direct = productForSpecId(item.confirmedArrangement?.productSpecId);
    if (direct) return direct.displayName;
    const directory = (state.catalog.sections.productDirectory || []).find((entry) => (entry.merchantCodes || []).some((code) => (item.allowedMerchantCodes || []).includes(code)));
    if (directory) return directory.shortName;
  }
  const title = catalogTitle(item);
  return title
    .replace(/^悦希/, "")
    .replace(/[一二三四五六七八九十百两\d]+盒装/g, "")
    .replace(/原箱[一二三四五六七八九十百两\d]+盒/g, "")
    .replace(/原箱[一二三四五六七八九十百两\d]+包/g, "")
    .replace(/两套装/g, "")
    .trim();
}

function cartonQuantity(item) {
  if (Number.isFinite(item.capacity)) return item.capacity;
  const capacity = state.catalog.sections.confirmedCapacities.find((entry) => entry.cartonId === item.cartonId);
  if (capacity?.capacity) return capacity.capacity;
  const match = catalogTitle(item).match(/([一二三四五六七八九十百两\d]+)盒/);
  return match ? chineseNumber(match[1]) : 99999;
}

function brandLabel(brandId) {
  return state.catalog.brands.find((item) => item.brandId === brandId)?.displayName || (brandId === "other" ? "其他" : brandId.toUpperCase());
}

function sortCatalogItems(section, items) {
  return [...items].sort((a, b) => {
    const brandCompare = brandLabel(brandForCatalogItem(a)).localeCompare(brandLabel(brandForCatalogItem(b)), "zh-CN");
    if (brandCompare) return brandCompare;
    if (section === "cartons") {
      const groupCompare = cartonProductGroup(a).localeCompare(cartonProductGroup(b), "zh-CN");
      if (groupCompare) return groupCompare;
      return cartonQuantity(a) - cartonQuantity(b) || catalogTitle(a).localeCompare(catalogTitle(b), "zh-CN", { numeric: true });
    }
    if (section === "products") {
      return catalogTitle(a).localeCompare(catalogTitle(b), "zh-CN", { numeric: true });
    }
    const productCompare = productNameForRule(a).localeCompare(productNameForRule(b), "zh-CN");
    return productCompare || catalogTitle(a).localeCompare(catalogTitle(b), "zh-CN", { numeric: true });
  });
}

function buildCatalogRow(item) {
  const template = $("#catalog-row-template");
  const row = template.content.firstElementChild.cloneNode(true);
  if (state.catalogSection === "products") row.classList.add("is-product");
  row.querySelector(".catalog-title").textContent = catalogTitle(item);
  row.querySelector(".catalog-subtitle").textContent = catalogSubtitle(item);

  const facts = row.querySelector(".catalog-facts");
  visibleFacts(item).forEach((text) => {
    const line = document.createElement("div");
    line.textContent = text;
    facts.append(line);
  });

  const tags = row.querySelector(".catalog-tags");
  if (hasMissingDimensions(item)) {
    const tag = document.createElement("span");
    tag.className = "catalog-tag missing";
    tag.textContent = "待补尺寸";
    tags.append(tag);
  }
  if (item._recordType === "产品原箱") {
    const tag = document.createElement("span");
    tag.className = "catalog-tag original";
    tag.textContent = "产品原箱";
    tags.append(tag);
  }
  if (state.catalogSection === "products" && item.missingCode) {
    const tag = document.createElement("span");
    tag.className = "catalog-tag review";
    tag.textContent = "编码待核对";
    tags.append(tag);
  }
  if (state.catalogSection === "products" && item.packingBehavior === "ignored_zero_space") {
    const tag = document.createElement("span");
    tag.className = "catalog-tag accessory";
    tag.textContent = "不计体积";
    tags.append(tag);
  }

  row.querySelector(".catalog-detail-button").addEventListener("click", () => toggleCatalogDetail(row, item));
  return row;
}

function renderCatalog() {
  if (!state.catalog) return;
  const query = $("#catalog-search").value.trim().toLowerCase();
  const items = sortCatalogItems(
    state.catalogSection,
    catalogItems(state.catalogSection).filter((item) => JSON.stringify(item).toLowerCase().includes(query)),
  );
  const container = $("#catalog-content");
  container.innerHTML = "";

  if (["cartons", "products"].includes(state.catalogSection)) {
    const columns = document.createElement("div");
    columns.className = "catalog-brand-columns";
    ["kgos", "yuexi"].forEach((brandId) => {
      const column = document.createElement("section");
      column.className = "catalog-brand-column";
      const heading = document.createElement("div");
      heading.className = "catalog-brand-heading";
      heading.textContent = brandLabel(brandId);
      column.append(heading);
      const brandItems = items.filter((item) => brandForCatalogItem(item) === brandId);
      brandItems.forEach((item) => column.append(buildCatalogRow(item)));
      if (!brandItems.length) {
        const empty = document.createElement("div");
        empty.className = "catalog-column-empty";
        empty.textContent = query ? "没有匹配资料" : "暂无资料";
        column.append(empty);
      }
      columns.append(column);
    });
    container.append(columns);
    return;
  }

  let currentBrand = null;
  items.forEach((item) => {
    const brandId = brandForCatalogItem(item);
    if (brandId !== currentBrand) {
      currentBrand = brandId;
      const heading = document.createElement("div");
      heading.className = "catalog-brand-heading";
      heading.textContent = brandLabel(brandId);
      container.append(heading);
    }
    container.append(buildCatalogRow(item));
  });
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "catalog-empty";
    empty.textContent = "没有匹配资料";
    container.append(empty);
  }
}

function toggleCatalogDetail(row, item) {
  const button = row.querySelector(".catalog-detail-button");
  const detail = row.querySelector(".catalog-inline-detail");
  const chevron = row.querySelector(".detail-chevron");
  const nextOpen = detail.hidden;
  detail.hidden = !nextOpen;
  button.setAttribute("aria-expanded", String(nextOpen));
  chevron.textContent = nextOpen ? "▴" : "▾";
  if (nextOpen) {
    detail.textContent = JSON.stringify(
      item,
      (key, value) => key.startsWith("_") ? undefined : value,
      2,
    );
  }
}

function colorFor(value) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0;
  return COLORS[Math.abs(hash) % COLORS.length];
}

function resizeCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width * ratio));
  const height = Math.max(1, Math.round(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

function drawPacking() {
  const canvas = $("#packing-canvas");
  if (!canvas) return;
  const { ctx, width, height } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  const geometry = state.result?.geometry;
  const placements = geometry?.placements || [];
  const container = geometry?.containerMm;
  const message = $("#canvas-message");
  const hasLayout = Boolean(container && placements.length);
  if (!state.result) {
    message.hidden = true;
    renderLegend([]);
    return;
  }
  message.hidden = hasLayout;
  if (!hasLayout) {
    message.textContent = geometry?.status === "unknown"
      ? "这次搜索暂时没有找到摆法，但这不代表现实里装不下。"
      : geometry?.message || "当前没有可绘制的摆放结果。";
    renderLegend([]);
    return;
  }
  const layer = Number($("#layer-slider").value) / 100;
  const visible = placements.filter((item) => item.positionMm[2] < container[2] * layer + 0.001);
  if (state.view === "top") drawTop(ctx, width, height, container, visible);
  else if (state.view === "front") drawFront(ctx, width, height, container, visible);
  else drawIso(ctx, width, height, container, visible);
  renderLegend(placements);
}

function drawTop(ctx, width, height, container, placements) {
  const margin = 38;
  const scale = Math.min((width - margin * 2) / container[0], (height - margin * 2) / container[1]);
  const ox = (width - container[0] * scale) / 2;
  const oy = (height - container[1] * scale) / 2;
  ctx.fillStyle = "#fff";
  ctx.fillRect(ox, oy, container[0] * scale, container[1] * scale);
  ctx.strokeStyle = "#718096";
  ctx.lineWidth = 1.4;
  ctx.strokeRect(ox, oy, container[0] * scale, container[1] * scale);
  [...placements].sort((a, b) => a.positionMm[2] - b.positionMm[2]).forEach((item) => {
    const [x, y] = item.positionMm;
    const [l, w] = item.dimensionsMm;
    ctx.globalAlpha = .72;
    ctx.fillStyle = colorFor(item.productSpecId || item.merchantCode || item.instanceId);
    ctx.fillRect(ox + x * scale, oy + y * scale, l * scale, w * scale);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "rgba(32,41,56,.45)";
    ctx.strokeRect(ox + x * scale, oy + y * scale, l * scale, w * scale);
  });
}

function drawFront(ctx, width, height, container, placements) {
  const margin = 38;
  const [length, , cartonHeight] = container;
  const scale = Math.min(
    (width - margin * 2) / length,
    (height - margin * 2) / cartonHeight,
  );
  const ox = (width - length * scale) / 2;
  const oy = (height - cartonHeight * scale) / 2;
  ctx.fillStyle = "#fff";
  ctx.fillRect(ox, oy, length * scale, cartonHeight * scale);
  ctx.strokeStyle = "#718096";
  ctx.lineWidth = 1.4;
  ctx.strokeRect(ox, oy, length * scale, cartonHeight * scale);
  [...placements].sort((a, b) => b.positionMm[1] - a.positionMm[1]).forEach((item) => {
    const [x, , z] = item.positionMm;
    const [l, , h] = item.dimensionsMm;
    const top = oy + (cartonHeight - z - h) * scale;
    ctx.globalAlpha = .72;
    ctx.fillStyle = colorFor(item.productSpecId || item.merchantCode || item.instanceId);
    ctx.fillRect(ox + x * scale, top, l * scale, h * scale);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "rgba(32,41,56,.45)";
    ctx.strokeRect(ox + x * scale, top, l * scale, h * scale);
  });
}

function isoPoint(x, y, z, scale, ox, oy) {
  return [ox + (x - y) * .866 * scale, oy + (x + y) * .5 * scale - z * scale];
}

function boxCorners(position, dimensions) {
  const [x, y, z] = position;
  const [l, w, h] = dimensions;
  return {
    a:[x,y,z], b:[x+l,y,z], c:[x+l,y+w,z], d:[x,y+w,z],
    e:[x,y,z+h], f:[x+l,y,z+h], g:[x+l,y+w,z+h], h:[x,y+w,z+h],
  };
}

function polygon(ctx, points, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(...points[0]);
  points.slice(1).forEach((point) => ctx.lineTo(...point));
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
}

function withAlpha(hex, alpha) {
  const value = hex.replace("#", "");
  return `rgba(${parseInt(value.slice(0,2),16)},${parseInt(value.slice(2,4),16)},${parseInt(value.slice(4,6),16)},${alpha})`;
}

function drawIso(ctx, width, height, container, placements) {
  const [l, w, h] = container;
  const scale = Math.min((width - 78) / ((l + w) * .866), (height - 60) / ((l + w) * .5 + h));
  const ox = width / 2 - ((l - w) * .866 * scale) / 2;
  const oy = height - 30 - ((l + w) * .5 * scale);
  drawWireBox(ctx, [0,0,0], container, scale, ox, oy);
  [...placements]
    .sort((a,b) => (a.positionMm[0] + a.positionMm[1] + a.positionMm[2]) - (b.positionMm[0] + b.positionMm[1] + b.positionMm[2]))
    .forEach((item) => drawSolidBox(ctx, item.positionMm, item.dimensionsMm, scale, ox, oy, colorFor(item.productSpecId || item.merchantCode || item.instanceId)));
}

function drawSolidBox(ctx, position, dimensions, scale, ox, oy, color) {
  const c = boxCorners(position, dimensions);
  const p = Object.fromEntries(Object.entries(c).map(([key, point]) => [key, isoPoint(...point, scale, ox, oy)]));
  const stroke = "rgba(32,41,56,.42)";
  polygon(ctx, [p.e,p.f,p.g,p.h], withAlpha(color,.82), stroke);
  polygon(ctx, [p.b,p.c,p.g,p.f], withAlpha(color,.62), stroke);
  polygon(ctx, [p.d,p.c,p.g,p.h], withAlpha(color,.50), stroke);
}

function drawWireBox(ctx, position, dimensions, scale, ox, oy) {
  const c = boxCorners(position, dimensions);
  const p = Object.fromEntries(Object.entries(c).map(([key, point]) => [key, isoPoint(...point, scale, ox, oy)]));
  const edges = [["a","b"],["b","c"],["c","d"],["d","a"],["e","f"],["f","g"],["g","h"],["h","e"],["a","e"],["b","f"],["c","g"],["d","h"]];
  ctx.strokeStyle = "rgba(74,91,116,.65)";
  ctx.lineWidth = 1.1;
  edges.forEach(([a,b]) => { ctx.beginPath(); ctx.moveTo(...p[a]); ctx.lineTo(...p[b]); ctx.stroke(); });
}

function renderLegend(placements) {
  const container = $("#placement-legend");
  container.innerHTML = "";
  const grouped = new Map();
  placements.forEach((item) => {
    const key = item.productSpecId || item.merchantCode || item.displayName;
    if (!grouped.has(key)) grouped.set(key, { item, count: 0 });
    grouped.get(key).count += 1;
  });
  grouped.forEach(({ item, count }, key) => {
    const node = document.createElement("div");
    node.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = colorFor(key);
    const text = document.createElement("span");
    text.textContent = `${displayNameForCode(item.merchantCode) || item.displayName} × ${count}`;
    node.append(swatch, text);
    container.append(node);
  });
}

async function bootstrap() {
  initNavigation();
  initControls();
  try {
    await loadCatalog();
    renderLines();
    drawPacking();
  } catch (error) {
    document.body.innerHTML = `<main style="padding:32px;font-family:sans-serif"><h1>装箱实验无法启动</h1><p></p></main>`;
    document.querySelector("p").textContent = error.message;
  }
}

bootstrap();
