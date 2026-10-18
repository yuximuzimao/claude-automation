const fs = require('fs');

function readSessionState(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function saveSessionState(file, num, now = Date.now()) {
  fs.writeFileSync(file, JSON.stringify({ accountNum: Number(num), at: now }));
}

function clearSessionState(file) {
  try {
    fs.unlinkSync(file);
  } catch (error) {
    if (!error || error.code !== 'ENOENT') throw error;
  }
}

function isSameFreshSession(file, num, ttlMs, now = Date.now()) {
  const state = readSessionState(file);
  return !!(state && state.accountNum === Number(num) && (now - state.at) < ttlMs);
}

module.exports = { readSessionState, saveSessionState, clearSessionState, isSameFreshSession };
