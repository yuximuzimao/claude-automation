'use strict';

const AUTH_COOKIE_NAMES = new Set([
  'JSESSIONID',
  'ssxmod_itna',
  'ssxmod_itna2',
  '_us',
]);

const IDENTITY_LOCAL_STORAGE_NAMES = new Set([
  '__supplierId__',
  '__subBizType__',
  'currentSubBizType',
  'supplierInfo',
  'aifocus-cookie',
]);

function filterAuthCookies(cookies) {
  return (cookies || []).filter(cookie => AUTH_COOKIE_NAMES.has(cookie.name));
}

function filterIdentityLocalStorage(items) {
  return (items || []).filter(item => IDENTITY_LOCAL_STORAGE_NAMES.has(item.name));
}

module.exports = {
  AUTH_COOKIE_NAMES,
  IDENTITY_LOCAL_STORAGE_NAMES,
  filterAuthCookies,
  filterIdentityLocalStorage,
};
