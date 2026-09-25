const browserWs = process.argv[2];
const url = process.argv[3];
if (!browserWs || !url) throw new Error('usage: node bili-open-paused.js <browserWs> <url>');
const ws = new WebSocket(browserWs);
let id = 0;
const pending = new Map();
function call(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    const msg = { id: mid, method, params };
    if (sessionId) msg.sessionId = sessionId;
    ws.send(JSON.stringify(msg));
  });
}
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (!msg.id || !pending.has(msg.id)) return;
  const p = pending.get(msg.id); pending.delete(msg.id);
  if (msg.error) p.reject(new Error(JSON.stringify(msg.error))); else p.resolve(msg.result);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
ws.onopen = async () => {
  try {
    const created = await call('Target.createTarget', { url: 'about:blank' });
    const attached = await call('Target.attachToTarget', { targetId: created.targetId, flatten: true });
    const sid = attached.sessionId;
    await call('Page.enable', {}, sid);
    await call('Runtime.enable', {}, sid);
    const suppressAutoplay = `(() => {
      const pauseAll = () => document.querySelectorAll('video,audio').forEach(m => { try { m.pause(); } catch (err) {} });
      const nativePlay = HTMLMediaElement.prototype.play;
      HTMLMediaElement.prototype.play = function(){ try { this.pause(); } catch (err) {} return Promise.resolve(); };
      new MutationObserver(pauseAll).observe(document.documentElement || document, { childList: true, subtree: true });
      setInterval(pauseAll, 200);
      window.__CHATGPT_NATIVE_PLAY__ = nativePlay;
    })();`;
    await call('Page.addScriptToEvaluateOnNewDocument', { source: suppressAutoplay }, sid);
    await call('Page.navigate', { url }, sid);
    let state = null;
    for (let i = 0; i < 60; i++) {
      await sleep(500);
      const r = await call('Runtime.evaluate', { expression: `(() => { const v=document.querySelector('video'); if(v) v.pause(); return {title:document.title,url:location.href,hasVideo:!!v,paused:v?.paused,currentTime:v?.currentTime,duration:v?.duration,readyState:v?.readyState}; })()`, returnByValue: true }, sid);
      state = r.result.value;
      if (state.hasVideo && Number.isFinite(state.duration) && state.duration > 0 && state.paused) break;
    }
    console.log(JSON.stringify({ targetId: created.targetId, sessionId: sid, state }));
  } catch (e) { console.error(e.stack || String(e)); process.exitCode = 1; }
  finally { ws.close(); }
};
setTimeout(() => process.exit(2), 45000);
