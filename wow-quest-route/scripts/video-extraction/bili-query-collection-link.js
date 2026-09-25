const pageWs = process.argv[2];
const titleText = process.argv[3];
if (!pageWs || !titleText) throw new Error('usage: node bili-query-collection-link.js <pageWs> <titleText>');

const ws = new WebSocket(pageWs);
let id = 0;
const pending = new Map();
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (!msg.id || !pending.has(msg.id)) return;
  const handler = pending.get(msg.id);
  pending.delete(msg.id);
  if (msg.error) handler.reject(new Error(JSON.stringify(msg.error)));
  else handler.resolve(msg.result);
};
ws.onopen = async () => {
  try {
    await call('Runtime.enable');
    const expression = `(() => {
      const wanted = ${JSON.stringify(titleText)};
      const links = [...document.querySelectorAll('a[href]')]
        .map(a => ({ text: (a.textContent || '').replace(/\\s+/g, ' ').trim(), href: a.href }))
        .filter(x => x.text.includes(wanted));
      return links;
    })()`;
    const result = await call('Runtime.evaluate', { expression, returnByValue: true });
    console.log(JSON.stringify(result.result.value || []));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
  }
};
setTimeout(() => process.exit(2), 15000);
