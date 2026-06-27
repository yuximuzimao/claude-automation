'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
  createAutoExecutionJournal,
  isUnfinishedIntent,
} = require('../../lib/server/auto-execution-journal');

test('auto_executing intent持久化后重复reserve被阻断，成功后更新executed', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-journal-'));
  const filePath = path.join(dir, 'journal.json');
  const journal = createAutoExecutionJournal({ filePath });
  journal.reserve('100001781188621717210', { accountNote: '顺链' });
  assert.throws(() => journal.reserve('100001781188621717210', {}), /已有自动执行记录/);
  journal.markExecuted('100001781188621717210');
  assert.equal(journal.read()['100001781188621717210'].status, 'auto_executed');
});

test('未完成intent可被只读识别，markExecuted后不再视为残留', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-journal-unfinished-'));
  const filePath = path.join(dir, 'journal.json');
  const journal = createAutoExecutionJournal({ filePath });
  journal.reserve('100001781188621717210', { accountNote: '顺链' });

  const unfinished = journal.getUnfinishedIntent('100001781188621717210');
  assert.equal(unfinished.status, 'auto_executing');
  assert.equal(isUnfinishedIntent(unfinished), true);

  journal.markExecuted('100001781188621717210');
  assert.equal(journal.getUnfinishedIntent('100001781188621717210'), null);
  assert.equal(isUnfinishedIntent(journal.read()['100001781188621717210']), false);
});

test('原子写失败时reserve抛错且不得产生可见intent', () => {
  const journal = createAutoExecutionJournal({
    filePath: '/tmp/not-used.json',
    writeAtomic: () => { throw new Error('fsync失败'); },
  });
  assert.throws(() => journal.reserve('100001781188621717210', {}), /fsync失败/);
  assert.deepEqual(journal.read(), {});
});

test('日志JSON损坏时read和reserve均抛错，不得覆盖原文件', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-journal-bad-'));
  const filePath = path.join(dir, 'journal.json');
  fs.writeFileSync(filePath, '{broken');
  const journal = createAutoExecutionJournal({ filePath });
  assert.throws(() => journal.read(), /JSON|Unexpected/);
  assert.throws(() => journal.getUnfinishedIntent('100001781188621717210'), /JSON|Unexpected/);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /JSON|Unexpected/);
  assert.equal(fs.readFileSync(filePath, 'utf8'), '{broken');
});

test('日志读取EIO时抛错，不得视为空日志', () => {
  const error = Object.assign(new Error('disk I/O error'), { code: 'EIO' });
  const journal = createAutoExecutionJournal({ filePath: '/tmp/not-used-journal.json', readFile: () => { throw error; } });
  assert.throws(() => journal.read(), /disk I\/O error/);
  assert.throws(() => journal.getUnfinishedIntent('100001781188621717210'), /disk I\/O error/);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /disk I\/O error/);
});
