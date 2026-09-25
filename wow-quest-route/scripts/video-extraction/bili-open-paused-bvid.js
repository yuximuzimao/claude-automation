const browserWs = process.argv[2];
const bvid = process.argv[3];
if (!browserWs || !/^BV[0-9A-Za-z]+$/.test(bvid || '')) {
  throw new Error('usage: node bili-open-paused-bvid.js <browserWs> <bvid>');
}
const url = `https://www.bilibili.com/video/${bvid}`;
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
  const handler = pending.get(msg.id);
  pending.delete(msg.id);
  if (msg.error) handler.reject(new Error(JSON.stringify(msg.error)));
  else handler.resolve(msg.result);
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
ws.onopen = async () => {
  try {
    const created = await call('Target.createTarget', { url: 'about:blank' });
    const attached = await call('Target.attachToTarget', { targetId: created.targetId, flatten: true });
    const sessionId = attached.sessionId;
    await call('Page.enable', {}, sessionId);
    await call('Runtime.enable', {}, sessionId);
    const suppressAutoplay = `(() => {
      const pauseAll = () => document.querySelectorAll('video,audio').forEach(media => {
        try { media.pause(); } catch (error) {}
      });
      const nativePlay = HTMLMediaElement.prototype.play;
      HTMLMediaElement.prototype.play = function() {
        try { this.pause(); } catch (error) {}
        return Promise.resolve();
      };
      new MutationObserver(pauseAll).observe(document.documentElement || document, { childList: true, subtree: true });
      setInterval(pauseAll, 200);
      window.__CHATGPT_NATIVE_PLAY__ = nativePlay;
    })();`;
    await call('Page.addScriptToEvaluateOnNewDocument', { source: suppressAutoplay }, sessionId);
    await call('Page.navigate', { url }, sessionId);
    let state = null;
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await sleep(500);
      const result = await call('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          if (video) video.pause();
          return {
            title: document.title,
            url: location.href,
            hasVideo: Boolean(video),
            paused: video?.paused,
            currentTime: video?.currentTime,
            duration: video?.duration,
            readyState: video?.readyState,
            networkState: video?.networkState
          };
        })()`,
        returnByValue: true
      }, sessionId);
      state = result.result.value;
      if (state.hasVideo && Number.isFinite(state.duration) && state.duration > 0 && state.paused && state.readyState >= 1) break;
    }
    console.log(JSON.stringify({ targetId: created.targetId, sessionId, state }));
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    ws.close();
  }
};
setTimeout(() => process.exit(2), 60000);
