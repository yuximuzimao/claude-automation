function extractInitialPhoneFromStorageState(storageState) {
  const origin = (storageState && storageState.origins || [])
    .find(item => item.origin === 'https://scrm.jlsupp.com');
  const supplierInfoEntry = (origin && origin.localStorage || [])
    .find(item => item.name === 'supplierInfo');
  if (!supplierInfoEntry) return null;

  try {
    const supplierInfo = JSON.parse(supplierInfoEntry.value);
    const phone = Array.isArray(supplierInfo.supplierMobileList)
      ? supplierInfo.supplierMobileList[0]
      : null;
    const normalized = phone == null ? '' : String(phone).trim();
    return /^\d{11}$/.test(normalized) ? normalized : null;
  } catch (error) {
    return null;
  }
}

function buildSavedAccountConfig(existing, fileName, num, { initialPhone = null } = {}) {
  const saved = {
    ...(existing || {}),
    file: fileName,
    name: existing && existing.name ? existing.name : `账号${num}`,
    note: existing && existing.note ? existing.note : '',
  };
  if (!saved.phone && initialPhone) saved.phone = initialPhone;
  return saved;
}

module.exports = {
  buildSavedAccountConfig,
  extractInitialPhoneFromStorageState,
};
