const LATEST_KEY = "latest";

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function htmlResponse(body) {
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

async function readJson(request) {
  const text = await request.text();
  if (!text.trim()) {
    return {};
  }

  try {
    const body = JSON.parse(text);
    return body && typeof body === "object" && !Array.isArray(body) ? body : {};
  } catch {
    return null;
  }
}

function tokenFromRequest(request, body) {
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (match) {
    return match[1].trim();
  }

  return typeof body?.token === "string" ? body.token : "";
}

function isAuthorized(request, body, env) {
  return Boolean(env.SECRET) && tokenFromRequest(request, body) === env.SECRET;
}

function mailboxStub(env) {
  const id = env.VOICE_DO.idFromName("default");
  return env.VOICE_DO.get(id);
}

async function forwardToMailbox(env, path, body) {
  return mailboxStub(env).fetch(
    new Request(`https://voice-mailbox.internal${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

async function handlePush(request, env) {
  if (request.method !== "POST") {
    return jsonResponse({ ok: false, error: "method_not_allowed" }, 405);
  }

  const body = await readJson(request);
  if (body === null) {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }

  if (!isAuthorized(request, body, env)) {
    return jsonResponse({ ok: false, error: "unauthorized" }, 401);
  }

  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!text) {
    return jsonResponse({ ok: false, error: "text_required" }, 400);
  }

  return forwardToMailbox(env, "/push", { text });
}

async function handleLatest(request, env) {
  if (request.method !== "POST") {
    return jsonResponse({ ok: false, error: "method_not_allowed" }, 405);
  }

  const body = await readJson(request);
  if (body === null) {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }

  if (!isAuthorized(request, body, env)) {
    return jsonResponse({ ok: false, error: "unauthorized" }, 401);
  }

  return forwardToMailbox(env, "/latest", {});
}

const mobilePage = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>手机语音粘贴</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f7f4;
      color: #1f2328;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100svh;
      padding: max(18px, env(safe-area-inset-top)) 16px max(22px, env(safe-area-inset-bottom));
      display: flex;
      align-items: stretch;
      justify-content: center;
    }
    main {
      width: min(100%, 560px);
      display: grid;
      grid-template-rows: auto 1fr auto auto;
      gap: 12px;
    }
    h1 {
      margin: 0 0 4px;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    input, textarea, button {
      width: 100%;
      border-radius: 8px;
      font: inherit;
    }
    input, textarea {
      border: 1px solid #cfd6dd;
      background: #ffffff;
      color: #1f2328;
      padding: 13px 14px;
      outline: none;
    }
    textarea {
      min-height: 46svh;
      resize: vertical;
      line-height: 1.45;
      font-size: 20px;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 92px;
      gap: 10px;
    }
    button {
      border: 0;
      padding: 14px 12px;
      min-height: 50px;
      font-weight: 700;
      color: white;
      background: #1f6feb;
    }
    button.secondary {
      color: #1f2328;
      background: #e9edf2;
    }
    #status {
      min-height: 24px;
      font-size: 15px;
      color: #59636e;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        background: #111315;
        color: #f0f3f6;
      }
      input, textarea {
        background: #1b1f23;
        border-color: #3b444d;
        color: #f0f3f6;
      }
      button.secondary {
        color: #f0f3f6;
        background: #30363d;
      }
      #status {
        color: #a9b4bf;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>手机语音粘贴</h1>
      <input id="token" type="password" autocomplete="current-password" placeholder="Token">
    </header>
    <textarea id="text" placeholder="在这里用豆包输入法语音输入"></textarea>
    <div class="actions">
      <button id="send" type="button">发送</button>
      <button class="secondary" id="clear" type="button">清空</button>
    </div>
    <div id="status" role="status" aria-live="polite"></div>
  </main>
  <script>
    const tokenInput = document.querySelector("#token");
    const textInput = document.querySelector("#text");
    const statusEl = document.querySelector("#status");
    const savedToken = localStorage.getItem("phoneVoicePasteToken") || "";

    tokenInput.value = savedToken;
    if (savedToken) {
      textInput.focus();
    } else {
      tokenInput.focus();
    }

    function setStatus(message) {
      statusEl.textContent = message;
    }

    tokenInput.addEventListener("change", () => {
      localStorage.setItem("phoneVoicePasteToken", tokenInput.value.trim());
    });

    document.querySelector("#clear").addEventListener("click", () => {
      textInput.value = "";
      textInput.focus();
      setStatus("");
    });

    document.querySelector("#send").addEventListener("click", async () => {
      const token = tokenInput.value.trim();
      const text = textInput.value.trim();
      localStorage.setItem("phoneVoicePasteToken", token);

      if (!token) {
        setStatus("请输入 token");
        tokenInput.focus();
        return;
      }
      if (!text) {
        setStatus("请输入文本");
        textInput.focus();
        return;
      }

      setStatus("发送中...");
      try {
        const response = await fetch("/push", {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "authorization": "Bearer " + token,
          },
          body: JSON.stringify({ text }),
        });
        const data = await response.json();
        if (response.ok && data.ok) {
          setStatus("已发送");
        } else {
          setStatus(data.error || "发送失败");
        }
      } catch {
        setStatus("网络错误");
      }
    });
  </script>
</body>
</html>`;

export class VoiceMailbox {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const url = new URL(request.url);

    if (request.method !== "POST") {
      return jsonResponse({ ok: false, error: "method_not_allowed" }, 405);
    }

    if (url.pathname === "/push") {
      const body = await readJson(request);
      if (body === null || typeof body.text !== "string" || !body.text.trim()) {
        return jsonResponse({ ok: false, error: "text_required" }, 400);
      }

      const latest = {
        text: body.text.trim(),
        createdAt: new Date().toISOString(),
      };
      await this.state.storage.put(LATEST_KEY, latest);
      return jsonResponse({ ok: true, createdAt: latest.createdAt });
    }

    if (url.pathname === "/latest") {
      const latest = await this.state.storage.get(LATEST_KEY);
      if (!latest) {
        return jsonResponse({ ok: true, text: null, reason: "empty" });
      }

      return jsonResponse({
        ok: true,
        text: latest.text,
        createdAt: latest.createdAt,
      });
    }

    return jsonResponse({ ok: false, error: "not_found" }, 404);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/" && request.method === "GET") {
      return htmlResponse(mobilePage);
    }

    if (url.pathname === "/push") {
      return handlePush(request, env);
    }

    if (url.pathname === "/latest") {
      return handleLatest(request, env);
    }

    return jsonResponse({ ok: false, error: "not_found" }, 404);
  },
};
