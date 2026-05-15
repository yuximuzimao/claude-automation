const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8899;
const DATA_FILE = path.join(__dirname, 'data', 'collections.json');
const SPRITES_FILE = path.join(__dirname, 'data', 'sprites.json');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.css': 'text/css',
  '.js': 'text/javascript',
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // API: 保存数据
  if (req.method === 'POST' && url.pathname === '/api/save') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const parsed = JSON.parse(body);
        fs.writeFileSync(DATA_FILE, JSON.stringify(parsed, null, 2), 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: 读数据
  if (req.method === 'GET' && url.pathname === '/api/data') {
    try {
      const content = fs.readFileSync(DATA_FILE, 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
      res.end(content);
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // API: 读精灵数据（合并进度）
  if (req.method === 'GET' && url.pathname === '/api/sprites') {
    try {
      const sprites = JSON.parse(fs.readFileSync(SPRITES_FILE, 'utf8'));
      const coll = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
      const progress = coll.sprite_progress || {};
      // 合并进度到精灵数据
      const merged = sprites.map(sp => {
        const spProgress = progress[String(sp.id)] || {};
        const forms = sp.forms.map((f, fi) => {
          const fp = (spProgress.forms || {})[String(fi)] || {};
          const tasks = f.tasks.map((t, ti) => ({
            ...t,
            done: fp.tasks ? !!fp.tasks[String(ti)] : false
          }));
          return { ...f, collected: !!fp.collected, tasks };
        });
        return { ...sp, collected: !!spProgress.collected, forms };
      });
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
      res.end(JSON.stringify(merged));
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // 静态文件
  let filePath = path.join(__dirname, url.pathname === '/' ? 'index.html' : url.pathname);
  if (!filePath.startsWith(__dirname)) { res.writeHead(403); res.end(); return; }

  fs.readFile(filePath, (err, content) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(content);
  });
});

server.listen(PORT, () => {
  console.log(`洛克王国收集助手运行在 http://localhost:${PORT}`);
});
