'use strict';
/**
 * WHAT: Server-Sent Events 实时推送
 * WHERE: server.js 初始化 SSE 端点，pipeline.js 调用 broadcast() 推送状态
 * WHY: 前端 Web 面板需要实时看到工单处理进度，轮询开销大且延迟高
 * ENTRY: server.js: app.use('/api/events', sse.router)
 */
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
