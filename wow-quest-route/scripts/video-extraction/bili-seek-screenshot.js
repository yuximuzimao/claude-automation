const fs = require('fs');

const wsUrl = process.argv[2];
const seconds = Number(process.argv[3]);
const output = process.argv[4];
if (!wsUrl || !Number.isFinite(seconds) || !output) {
  throw new Error('usage: node bili-seek-screenshot.js <wsUrl> <seconds> <output>');
}

const ws = new WebSocket(wsUrl);
let nextId = 0;
const pending = new Map();
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(JSON.stringify(message.error)));
  else resolve(message.result);
};
ws.onopen = async () => {
  try {
    await call('Page.enable');
    await call('Runtime.enable');
    await new Promise((resolve) => setTimeout(resolve, 5000));
    const result = await call('Runtime.evaluate', {
      expression: `(() => { const v = document.querySelector('video'); if (!v) return {ok:false}; v.pause(); v.currentTime=${seconds}; return {ok:true,duration:v.duration,currentTime:v.currentTime,readyState:v.readyState}; })()`,
      returnByValue: true,
    });
    await new Promise((resolve) => setTimeout(resolve, 2500));
    const state = await call('Runtime.evaluate', {
      expression: `(() => { const v=document.querySelector('video'); return {title:document.title,currentTime:v?.currentTime,duration:v?.duration,readyState:v?.readyState,videoWidth:v?.videoWidth,videoHeight:v?.videoHeight}; })()`,
      returnByValue: true,
    });
    const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    fs.writeFileSync(output, Buffer.from(screenshot.data, 'base64'));
    console.log(JSON.stringify({ seekResult: result.result.value, state: state.result.value, output }));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
  }
};
setTimeout(() => process.exit(2), 20000);
