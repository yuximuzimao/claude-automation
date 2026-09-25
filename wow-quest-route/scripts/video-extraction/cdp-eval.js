const wsUrl = process.argv[2];
const expression = Buffer.from(process.argv[3] || '', 'base64').toString('utf8');
if (!wsUrl || !expression) throw new Error('usage: node cdp-eval.js <wsUrl> <base64-expression>');
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
    await call('Runtime.enable');
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    console.log(JSON.stringify(result.result.value));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
  }
};
setTimeout(() => process.exit(2), 20000);
