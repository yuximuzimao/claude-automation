const fs = require('fs');
const path = require('path');

const wsUrl = process.argv[2];
const times = (process.argv[3] || '').split(',').filter(Boolean).map(Number);
const outDir = process.argv[4];
if (!wsUrl || !times.length || !outDir) throw new Error('usage: node bili-batch-screenshots.js <wsUrl> <comma-times> <outDir>');
fs.mkdirSync(outDir, { recursive: true });

const ws = new WebSocket(wsUrl);
let id = 0;
const pending = new Map();
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}
ws.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (!msg.id || !pending.has(msg.id)) return;
  const p = pending.get(msg.id);
  pending.delete(msg.id);
  if (msg.error) p.reject(new Error(JSON.stringify(msg.error)));
  else p.resolve(msg.result);
};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function seekPaused(seconds) {
  await call('Runtime.evaluate', {
    expression: `(() => { const v=document.querySelector('video'); if(!v) return {ok:false}; v.pause(); v.currentTime=${seconds}; return {ok:true,currentTime:v.currentTime,duration:v.duration,paused:v.paused,readyState:v.readyState}; })()`,
    returnByValue: true,
  });
  let state = null;
  for (let i = 0; i < 30; i++) {
    await sleep(150);
    const result = await call('Runtime.evaluate', {
      expression: `(() => { const v=document.querySelector('video'); if(!v) return {ok:false}; v.pause(); return {ok:true,currentTime:v.currentTime,duration:v.duration,paused:v.paused,readyState:v.readyState}; })()`,
      returnByValue: true,
    });
    state = result.result.value;
    if (state.ok && state.paused && Math.abs(state.currentTime - seconds) < 1.5 && state.readyState >= 2) break;
  }
  return state;
}

ws.onopen = async () => {
  const manifest = [];
  try {
    await call('Page.enable');
    await call('Runtime.enable');
    for (const seconds of times) {
      const state = await seekPaused(seconds);
      const shot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      const name = `${String(Math.round(seconds)).padStart(5, '0')}.png`;
      const file = path.join(outDir, name);
      fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
      manifest.push({ requested: seconds, file, ...state });
    }
    fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
    console.log(JSON.stringify({ count: manifest.length, outDir, first: manifest[0], last: manifest.at(-1) }));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
    clearTimeout(watchdog);
  }
};
const watchdog = setTimeout(() => process.exit(2), 180000);
