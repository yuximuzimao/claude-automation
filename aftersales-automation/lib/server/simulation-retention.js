'use strict';

function retainSimulationLines(lines, activeQueueItemIds, maxRecent = 500) {
  const normalizedLines = (lines || []).filter(line => String(line || '').trim());
  const activeIds = activeQueueItemIds instanceof Set
    ? activeQueueItemIds
    : new Set(activeQueueItemIds || []);
  const recentStart = Math.max(0, normalizedLines.length - maxRecent);
  let protectedOlderCount = 0;
  let malformedOlderCount = 0;

  const keptLines = normalizedLines.filter((line, index) => {
    if (index >= recentStart) return true;
    try {
      const simulation = JSON.parse(line);
      const isActive = activeIds.has(String(simulation && simulation.queueItemId || ''));
      if (isActive) protectedOlderCount += 1;
      return isActive;
    } catch {
      // 清理不能把无法解析的数据当成可安全删除，保留供人工排查。
      malformedOlderCount += 1;
      return true;
    }
  });

  return {
    lines: keptLines,
    removedCount: normalizedLines.length - keptLines.length,
    protectedOlderCount,
    malformedOlderCount,
  };
}

module.exports = { retainSimulationLines };
