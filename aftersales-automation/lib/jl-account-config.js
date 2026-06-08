function buildSavedAccountConfig(existing, fileName, num) {
  return {
    ...(existing || {}),
    file: fileName,
    name: existing && existing.name ? existing.name : `账号${num}`,
    note: existing && existing.note ? existing.note : '',
  };
}

module.exports = { buildSavedAccountConfig };
