import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { timingSafeEqual as nodeTimingSafeEqual, webcrypto } from "node:crypto";
import test from "node:test";

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, "crypto", { value: webcrypto });
}

// Cloudflare extends SubtleCrypto with timingSafeEqual. Node does not, so the
// harness supplies Node's native constant-time comparator for fixed-size hashes.
if (typeof globalThis.crypto.subtle.timingSafeEqual !== "function") {
  Object.defineProperty(globalThis.crypto.subtle, "timingSafeEqual", {
    value(left, right) {
      const leftBytes = ArrayBuffer.isView(left)
        ? new Uint8Array(left.buffer, left.byteOffset, left.byteLength)
        : new Uint8Array(left);
      const rightBytes = ArrayBuffer.isView(right)
        ? new Uint8Array(right.buffer, right.byteOffset, right.byteLength)
        : new Uint8Array(right);
      return nodeTimingSafeEqual(leftBytes, rightBytes);
    },
  });
}

const workerPath = new URL("../r2-upload.js", import.meta.url);
const workerSource = await readFile(workerPath, "utf8");
const workerModuleUrl = `data:text/javascript;base64,${Buffer.from(workerSource).toString("base64")}`;
const { default: worker } = await import(workerModuleUrl);

class FakeBucket {
  constructor() {
    this.puts = [];
    this.deletes = [];
  }

  async put(key, body, options) {
    const call = { key, body, options, bytes: null };
    this.puts.push(call);
    call.bytes = new Uint8Array(await new Response(body).arrayBuffer());
  }

  async delete(key) {
    this.deletes.push(key);
  }
}

function makeEnv(overrides = {}) {
  return {
    MY_BUCKET: new FakeBucket(),
    UPLOAD_TOKEN: "test-secret",
    PUBLIC_BASE_URL: "https://cdn.example.test/base/",
    ...overrides,
  };
}

async function invoke({
  path,
  method = "GET",
  token = "test-secret",
  headers = {},
  body,
  env = makeEnv(),
}) {
  const requestHeaders = new Headers(headers);
  if (token !== null) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }
  const request = new Request(`https://worker.example.test${path}`, {
    method,
    headers: requestHeaders,
    body,
  });
  const requestBody = request.body;
  const logs = [];
  const originalLog = console.log;
  const originalError = console.error;
  console.log = (entry) => logs.push({ level: "log", entry });
  console.error = (entry) => logs.push({ level: "error", entry });
  try {
    const response = await worker.fetch(request, env, {});
    const rawPayload = await response.text();
    let payload = {};
    try {
      payload = JSON.parse(rawPayload);
    } catch {
      // Assertions below report the missing structured response during RED.
    }
    return { response, payload, rawPayload, env, logs, requestBody };
  } finally {
    console.log = originalLog;
    console.error = originalError;
  }
}

test("returns 503 when the configured upload token is missing", async () => {
  const { response, payload } = await invoke({
    path: "/health",
    env: makeEnv({ UPLOAD_TOKEN: "" }),
  });

  assert.equal(response.status, 503);
  assert.equal(payload.ok, false);
  assert.equal(payload.error, "service_not_configured");
});

test("rejects a missing bearer token", async () => {
  const { response, payload } = await invoke({ path: "/health", token: null });

  assert.equal(response.status, 401);
  assert.equal(payload.ok, false);
  assert.equal(payload.error, "unauthorized");
});

test("rejects an incorrect bearer token", async () => {
  const { response, payload } = await invoke({
    path: "/health",
    token: "incorrect-secret",
  });

  assert.equal(response.status, 401);
  assert.equal(payload.ok, false);
  assert.equal(payload.error, "unauthorized");
});

test("accepts the configured bearer token for health checks", async () => {
  const { response, payload } = await invoke({ path: "/health" });

  assert.equal(response.status, 200);
  assert.deepEqual(payload, { ok: true, service: "r2" });
});

test("rejects unsupported upload MIME types", async () => {
  const { response, payload, env } = await invoke({
    path: "/upload?category=portrait&date=2026-07-16&filename=photo.gif",
    method: "POST",
    headers: { "Content-Type": "image/gif" },
    body: new Uint8Array([1, 2, 3]),
  });

  assert.equal(response.status, 415);
  assert.equal(payload.error, "unsupported_media_type");
  assert.equal(env.MY_BUCKET.puts.length, 0);
});

test("rejects uploads with no request body", async () => {
  const { response, payload, env } = await invoke({
    path: "/upload?category=portrait&date=2026-07-16&filename=photo.jpg",
    method: "POST",
    headers: { "Content-Type": "image/jpeg" },
  });

  assert.equal(response.status, 400);
  assert.equal(payload.error, "missing_body");
  assert.equal(env.MY_BUCKET.puts.length, 0);
});

test("rejects upload categories outside the allowlist", async () => {
  const { response, payload, env } = await invoke({
    path: "/upload?category=portraits&date=2026-07-16&filename=photo.jpg",
    method: "POST",
    headers: { "Content-Type": "image/jpeg" },
    body: new Uint8Array([1]),
  });

  assert.equal(response.status, 400);
  assert.equal(payload.error, "invalid_category");
  assert.equal(env.MY_BUCKET.puts.length, 0);
});

test("rejects upload dates that are not real YYYY-MM-DD dates", async () => {
  const { response, payload, env } = await invoke({
    path: "/upload?category=street&date=2026-02-30&filename=photo.png",
    method: "POST",
    headers: { "Content-Type": "image/png" },
    body: new Uint8Array([1]),
  });

  assert.equal(response.status, 400);
  assert.equal(payload.error, "invalid_date");
  assert.equal(env.MY_BUCKET.puts.length, 0);
});

test("rejects declared uploads larger than 15 MiB", async () => {
  const { response, payload, env } = await invoke({
    path: "/upload?category=official&date=2026-07-16&filename=photo.webp",
    method: "POST",
    headers: {
      "Content-Type": "image/webp",
      "Content-Length": String(15 * 1024 * 1024 + 1),
    },
    body: new Uint8Array([1]),
  });

  assert.equal(response.status, 413);
  assert.equal(payload.error, "payload_too_large");
  assert.equal(env.MY_BUCKET.puts.length, 0);
});

test("streams an accepted image into R2 and returns its public URL", async () => {
  const bytes = new Uint8Array([10, 20, 30, 40]);
  const { response, payload, env, requestBody } = await invoke({
    path: "/upload?category=performance&date=2026-07-16&filename=ignored-name.jpg",
    method: "POST",
    headers: { "Content-Type": "image/jpeg" },
    body: bytes,
  });

  assert.equal(response.status, 200);
  assert.equal(payload.ok, true);
  assert.match(
    payload.key,
    /^images\/performance\/2026-07-16\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.jpg$/,
  );
  assert.equal(payload.url, `https://cdn.example.test/base/${payload.key}`);
  assert.equal(env.MY_BUCKET.puts.length, 1);
  const put = env.MY_BUCKET.puts[0];
  assert.equal(put.key, payload.key);
  assert.equal(put.body, requestBody);
  assert.ok(put.body instanceof ReadableStream);
  assert.deepEqual(put.bytes, bytes);
  assert.deepEqual(put.options, {
    httpMetadata: { contentType: "image/jpeg" },
  });
});

test("rejects deletion keys outside the images prefix", async () => {
  const env = makeEnv();
  const { response, payload } = await invoke({
    path: "/delete",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: "private/photo.jpg" }),
    env,
  });

  assert.equal(response.status, 400);
  assert.equal(payload.error, "invalid_key");
  assert.deepEqual(env.MY_BUCKET.deletes, []);
});

test("deletes an images object idempotently", async () => {
  const env = makeEnv();
  const key = "images/portrait/2026-07-16/photo.jpg";
  const { response, payload } = await invoke({
    path: "/delete",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
    env,
  });

  assert.equal(response.status, 200);
  assert.deepEqual(payload, { ok: true, key });
  assert.deepEqual(env.MY_BUCKET.deletes, [key]);
});

test("emits structured request logs without credentials", async () => {
  const { logs } = await invoke({ path: "/health" });

  assert.equal(logs.length, 1);
  const entry = JSON.parse(logs[0].entry);
  assert.equal(entry.operation, "health");
  assert.equal(entry.status, 200);
  assert.equal(entry.key, null);
  assert.equal(entry.errorCode, null);
  assert.equal(typeof entry.requestId, "string");
  assert.ok(entry.requestId.length > 0);
  assert.doesNotMatch(logs[0].entry, /test-secret|authorization|bearer/i);
});
