const pageWs = process.argv[2];
const wanted = process.argv[3];
if (!pageWs || !wanted) throw new Error('usage: node bili-query-season-state.js <pageWs> <titleText>');

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
      const wanted = ${JSON.stringify(wanted)};
      const state = window.__INITIAL_STATE__ || {};
      const season = state.videoData?.ugc_season || state.ugc_season || {};
      const episodes = (season.sections || []).flatMap(section => section.episodes || []);
      return episodes.filter(ep => String(ep.title || ep.long_title || '').includes(wanted)).map(ep => ({
        title: ep.title,
        long_title: ep.long_title,
        bvid: ep.bvid,
        aid: ep.aid,
        duration: ep.duration,
        arc: ep.arc ? { title: ep.arc.title, duration: ep.arc.duration, bvid: ep.arc.bvid } : undefined
      }));
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
