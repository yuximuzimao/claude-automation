const wsUrl = process.argv[2];
const targetIds = process.argv.slice(3);
if (!wsUrl || !targetIds.length) throw new Error('usage: node cdp-close-targets.js <browserWs> <targetId...>');
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
ws.onopen = async () => {
  try {
    const results = [];
    for (const targetId of targetIds) {
      results.push({ targetId, ...(await call('Target.closeTarget', { targetId })) });
    }
    console.log(JSON.stringify(results));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
  }
};
setTimeout(() => process.exit(2), 15000);
