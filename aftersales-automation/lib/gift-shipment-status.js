'use strict';

const DEFINITELY_UNSHIPPED_STATUSES = new Set(['待审核', '待打印快递单', '待发货']);

function getGiftErpRows(collectedData) {
  const cd = collectedData || {};
  if (Array.isArray(cd.giftErpSearches) && cd.giftErpSearches.length > 0) {
    return cd.giftErpSearches.flatMap(search =>
      (search && search.rows && Array.isArray(search.rows.rows)) ? search.rows.rows : []
    );
  }
  return (cd.giftErpSearch && cd.giftErpSearch.rows && Array.isArray(cd.giftErpSearch.rows.rows))
    ? cd.giftErpSearch.rows.rows
    : [];
}

function getGiftShipmentState(collectedData) {
  const cd = collectedData || {};
  const rows = getGiftErpRows(cd);
  const giftIds = ((cd.ticket && cd.ticket.gifts) || [])
    .map(gift => String(gift && gift.id || '').trim())
    .filter(Boolean);
  const searches = Array.isArray(cd.giftErpSearches) ? cd.giftErpSearches : [];
  const hasCompleteGiftSearches = giftIds.length > 0 && (
    searches.length > 0
      ? giftIds.every(giftId => searches.some(search =>
          String(search && search.subOrderId || '').trim() === giftId
          && search.rows
          && Array.isArray(search.rows.rows)
          && search.rows.rows.length > 0
        ))
      : giftIds.length === 1
        && cd.giftErpSearch
        && cd.giftErpSearch.rows
        && Array.isArray(cd.giftErpSearch.rows.rows)
        && cd.giftErpSearch.rows.rows.length > 0
  );
  const statuses = [...new Set(rows.map(row => String(row && row.status || '').trim()).filter(Boolean))];
  const hasTracking = rows.some(row => {
    if (!row) return false;
    if (row.tracking) return true;
    return Array.isArray(row.trackings) && row.trackings.some(Boolean);
  });
  const definitelyUnshipped = hasCompleteGiftSearches
    && !hasTracking
    && rows.every(row => DEFINITELY_UNSHIPPED_STATUSES.has(String(row && row.status || '').trim()));

  return {
    rows,
    statuses,
    hasTracking,
    hasCompleteGiftSearches,
    definitelyUnshipped,
  };
}

module.exports = {
  DEFINITELY_UNSHIPPED_STATUSES,
  getGiftErpRows,
  getGiftShipmentState,
};
