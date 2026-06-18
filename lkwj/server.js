const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8899;
const DATA_FILE = path.join(__dirname, 'data', 'collections.json');
const PETS_FILE = path.join(__dirname, 'data', 'pets.json');
const TASKS_FILE = path.join(__dirname, 'data', 'tasks.json');
const CHAINS_FILE = path.join(__dirname, 'data', 'evolution-chains.json');
const FURNITURE_FILE = path.join(__dirname, 'data', 'furniture.json');
const TITLES_FILE = path.join(__dirname, 'data', 'titles.json');
const DUNGEONS_FILE = path.join(__dirname, 'data', 'dungeons.json');
const CLOTHING_FILE = path.join(__dirname, 'data', 'clothing.json');
const WALLET_FILE = path.join(__dirname, 'data', 'wallet.json');
const ANNOTATIONS_FILE = path.join(__dirname, 'data', 'annotations.json');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.css': 'text/css',
  '.js': 'text/javascript',
};

function readJSON(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function serveJSON(res, data) {
  res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
  res.end(JSON.stringify(data));
}

function serveError(res, code, msg) {
  res.writeHead(code);
  res.end(JSON.stringify({ error: msg }));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // API: Save collections
  if (req.method === 'POST' && url.pathname === '/api/save') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const parsed = JSON.parse(body);
        fs.writeFileSync(DATA_FILE, JSON.stringify(parsed, null, 2), 'utf8');
        serveJSON(res, { ok: true });
      } catch (e) {
        serveError(res, 400, e.message);
      }
    });
    return;
  }

  // API: Raw collections data
  if (req.method === 'GET' && url.pathname === '/api/data') {
    try {
      const content = fs.readFileSync(DATA_FILE, 'utf8');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
      res.end(content);
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Pets
  if (req.method === 'GET' && url.pathname === '/api/pets') {
    try {
      serveJSON(res, readJSON(PETS_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Tasks
  if (req.method === 'GET' && url.pathname === '/api/tasks') {
    try {
      serveJSON(res, readJSON(TASKS_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Evolution chains
  if (req.method === 'GET' && url.pathname === '/api/evolution-chains') {
    try {
      serveJSON(res, readJSON(CHAINS_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Furniture
  if (req.method === 'GET' && url.pathname === '/api/furniture') {
    try {
      serveJSON(res, readJSON(FURNITURE_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Titles
  if (req.method === 'GET' && url.pathname === '/api/titles') {
    try {
      serveJSON(res, readJSON(TITLES_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Dungeons
  if (req.method === 'GET' && url.pathname === '/api/dungeons') {
    try {
      serveJSON(res, readJSON(DUNGEONS_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Clothing
  if (req.method === 'GET' && url.pathname === '/api/clothing') {
    try {
      serveJSON(res, readJSON(CLOTHING_FILE));
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Merged game data (pets + tasks + chains + furniture + titles + dungeons + clothing + progress)
  if (req.method === 'GET' && url.pathname === '/api/game-data') {
    try {
      const pets = readJSON(PETS_FILE);
      const tasks = readJSON(TASKS_FILE);
      const chains = readJSON(CHAINS_FILE);
      const furniture = readJSON(FURNITURE_FILE);
      const titles = readJSON(TITLES_FILE);
      const dungeons = readJSON(DUNGEONS_FILE);
      const clothing = readJSON(CLOTHING_FILE);
      const collections = readJSON(DATA_FILE);

      serveJSON(res, {
        pets,
        tasks,
        evolutionChains: chains,
        furniture,
        titles,
        dungeons,
        clothing,
        sprite_progress: collections.sprite_progress || {},
        shiny_progress: collections.shiny_progress || {},
        furniture_progress: collections.furniture_progress || {},
        title_progress: collections.title_progress || {},
        dungeon_progress: collections.dungeon_progress || {},
        clothing_progress: collections.clothing_progress || {},
        categories: collections.categories || {},
        meta: collections.meta || {},
      });
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Wallet GET
  if (req.method === 'GET' && url.pathname === '/api/wallet') {
    try {
      if (fs.existsSync(WALLET_FILE)) {
        const content = fs.readFileSync(WALLET_FILE, 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
        res.end(content);
      } else {
        serveJSON(res, { currencies: {}, income_sources: [] });
      }
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Annotations GET
  if (req.method === 'GET' && url.pathname === '/api/annotations') {
    try {
      if (fs.existsSync(ANNOTATIONS_FILE)) {
        const content = fs.readFileSync(ANNOTATIONS_FILE, 'utf8');
        res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' });
        res.end(content);
      } else {
        serveJSON(res, { meta: {}, ops: [] });
      }
    } catch (e) {
      serveError(res, 500, e.message);
    }
    return;
  }

  // API: Annotations POST
  if (req.method === 'POST' && url.pathname === '/api/annotations') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        JSON.parse(body);
        fs.writeFileSync(ANNOTATIONS_FILE, body, 'utf8');
        serveJSON(res, { ok: true });
      } catch (e) {
        serveError(res, 400, e.message);
      }
    });
    return;
  }

  // API: Wallet POST
  if (req.method === 'POST' && url.pathname === '/api/wallet') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        JSON.parse(body);
        fs.writeFileSync(WALLET_FILE, body, 'utf8');
        serveJSON(res, { ok: true });
      } catch (e) {
        serveError(res, 400, e.message);
      }
    });
    return;
  }

  // Static files
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
