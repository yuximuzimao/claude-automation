'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { retainSimulationLines } = require('../../lib/server/simulation-retention');

function line(index, queueItemId = `q-${index}`) {
  return JSON.stringify({ id: `sim-${index}`, queueItemId });
}

test('保留最新500条时额外保护未归档工单的旧推理明细', () => {
  const lines = Array.from({ length: 600 }, (_, index) => line(index));
  const result = retainSimulationLines(lines, new Set(['q-10']), 500);

  assert.equal(result.lines.length, 501);
  assert.equal(result.removedCount, 99);
  assert.equal(result.protectedOlderCount, 1);
  assert.equal(JSON.parse(result.lines[0]).id, 'sim-10');
  assert.equal(JSON.parse(result.lines.at(-1)).id, 'sim-599');
});

test('未归档明细已在最新500条时不重复保留', () => {
  const lines = Array.from({ length: 600 }, (_, index) => line(index));
  const result = retainSimulationLines(lines, new Set(['q-550']), 500);

  assert.equal(result.lines.length, 500);
  assert.equal(result.protectedOlderCount, 0);
  assert.equal(result.removedCount, 100);
});

test('无法解析的旧行保留供人工排查，不在清理时静默删除', () => {
  const lines = ['{broken-json}', ...Array.from({ length: 500 }, (_, index) => line(index))];
  const result = retainSimulationLines(lines, new Set(), 500);

  assert.equal(result.lines.length, 501);
  assert.equal(result.malformedOlderCount, 1);
  assert.equal(result.removedCount, 0);
});
