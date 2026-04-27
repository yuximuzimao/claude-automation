'use strict';

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '../../data');
const WATCH_FILES = ['queue.json', 'simulations.jsonl', 'feedback.jsonl', 'cases.jsonl'];

const clients = new Set();

function addClient(res) {
  clients.add(res);
  res.on('close', () => clients.delete(res));
}

function broadcast(event, data) {
  const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  clients.forEach(res => {
    try { res.write(msg); } catch {}
  });
}

// 监听 data/ 目录的文件变更，推送对应 SSE 事件
const EVENT_MAP = {
  'queue.json': 'queue-update',
  'simulations.jsonl': 'simulation-update',
  'feedback.jsonl': 'feedback-new',
  'cases.jsonl': 'cases-update',
};

WATCH_FILES.forEach(file => {
  const filePath = path.join(DATA_DIR, file);
  fs.watchFile(filePath, { interval: 500 }, (curr, prev) => {
    if (curr.mtime > prev.mtime) {
      broadcast(EVENT_MAP[file], { file, ts: curr.mtime.toISOString() });
    }
  });
});

module.exports = { addClient, broadcast };
