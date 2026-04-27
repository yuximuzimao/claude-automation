'use strict';

function ok(data) {
  return { success: true, data };
}

function fail(error) {
  const msg = error instanceof Error ? error.message : String(error);
  return { success: false, error: msg };
}

module.exports = { ok, fail };
