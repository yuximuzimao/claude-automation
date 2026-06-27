'use strict';

function getSkipCompletionStatus(queueItem) {
  const source = queueItem && queueItem.source;
  return source === 'scan' || source === 'fixed_batch' ? 'auto_executed' : 'done';
}

module.exports = { getSkipCompletionStatus };
