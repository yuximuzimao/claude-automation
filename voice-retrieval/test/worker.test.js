import assert from "node:assert/strict";
import test from "node:test";
import worker, { VoiceMailbox } from "../src/index.js";

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  async get(key) {
    return this.values.get(key);
  }

  async put(key, value) {
    this.values.set(key, value);
  }
}

class MemoryDurableObjectNamespace {
  constructor() {
    this.instances = new Map();
  }

  idFromName(name) {
    return name;
  }

  get(id) {
    if (!this.instances.has(id)) {
      const storage = new MemoryStorage();
      const instance = new VoiceMailbox({ storage }, {});
      this.instances.set(id, instance);
    }

    return this.instances.get(id);
  }
}

function makeEnv(secret = "test-secret") {
  return {
    SECRET: secret,
    VOICE_DO: new MemoryDurableObjectNamespace(),
  };
}

async function request(env, path, options = {}) {
  const url = `https://voice.example${path}`;
  return worker.fetch(new Request(url, options), env, {});
}

async function json(response) {
  return response.json();
}

test("GET / returns the mobile page", async () => {
  const response = await request(makeEnv(), "/", { method: "GET" });

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/html/);
  assert.match(await response.text(), /手机语音粘贴/);
});

test("POST /push rejects unauthorized requests without storing text", async () => {
  const env = makeEnv();
  const response = await request(env, "/push", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text: "secret text" }),
  });

  assert.equal(response.status, 401);
  assert.deepEqual(await json(response), { ok: false, error: "unauthorized" });

  const latest = await request(env, "/latest", {
    method: "POST",
    headers: {
      authorization: "Bearer test-secret",
      "content-type": "application/json",
    },
    body: "{}",
  });
  assert.deepEqual(await json(latest), { ok: true, text: null, reason: "empty" });
});

test("POST /push rejects blank text", async () => {
  const response = await request(makeEnv(), "/push", {
    method: "POST",
    headers: {
      authorization: "Bearer test-secret",
      "content-type": "application/json",
    },
    body: JSON.stringify({ text: " \n\t " }),
  });

  assert.equal(response.status, 400);
  assert.deepEqual(await json(response), { ok: false, error: "text_required" });
});

test("POST /push stores latest text and POST /latest reads it from the same object", async () => {
  const env = makeEnv();
  const pushed = await request(env, "/push", {
    method: "POST",
    headers: {
      authorization: "Bearer test-secret",
      "content-type": "application/json",
    },
    body: JSON.stringify({ text: "你好，马上粘贴" }),
  });

  assert.equal(pushed.status, 200);
  const pushBody = await json(pushed);
  assert.equal(pushBody.ok, true);
  assert.match(pushBody.createdAt, /^\d{4}-\d{2}-\d{2}T/);

  const latest = await request(env, "/latest", {
    method: "POST",
    headers: {
      authorization: "Bearer test-secret",
      "content-type": "application/json",
    },
    body: "{}",
  });

  assert.equal(latest.status, 200);
  assert.deepEqual(await json(latest), {
    ok: true,
    text: "你好，马上粘贴",
    createdAt: pushBody.createdAt,
  });
});

test("POST /latest accepts token from JSON body when Authorization is absent", async () => {
  const env = makeEnv();
  await request(env, "/push", {
    method: "POST",
    headers: {
      authorization: "Bearer test-secret",
      "content-type": "application/json",
    },
    body: JSON.stringify({ text: "body token works" }),
  });

  const response = await request(env, "/latest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: "test-secret" }),
  });

  assert.equal(response.status, 200);
  assert.equal((await json(response)).text, "body token works");
});

test("GET /latest is rejected because latest must be POST-only", async () => {
  const response = await request(makeEnv(), "/latest", {
    method: "GET",
    headers: { authorization: "Bearer test-secret" },
  });

  assert.equal(response.status, 405);
  assert.deepEqual(await json(response), { ok: false, error: "method_not_allowed" });
});

test("unknown routes return JSON errors", async () => {
  const response = await request(makeEnv(), "/missing", { method: "GET" });

  assert.equal(response.status, 404);
  assert.deepEqual(await json(response), { ok: false, error: "not_found" });
});
