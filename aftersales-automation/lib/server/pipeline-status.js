'use strict';

function getSkipCompletionStatus(queueItem) {
  return queueItem && queueItem.source === 'scan' ? 'auto_executed' : 'done';
}

module.exports = { getSkipCompletionStatus };
