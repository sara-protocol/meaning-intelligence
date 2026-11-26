import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { createHandler, onRequest } from "../functions/api/mcp.js";

const ENDPOINT = "https://meaning.example/api/mcp";
const MAX_BODY_BYTES = 32768;

// Generated only in test memory; no credential is printed, persisted, or committed.
function ephemeralToken() {
  return `Aa1!${randomBytes(24).toString("base64url")}`;
}

function rpc(method, params, id = 1) {
  return { jsonrpc: "2.0", id, method, ...(params === undefined ? {} : { params }) };
}

async function send(handler, token, message, options = {}) {
  const method = options.method || "POST";
  const headers = new Headers(options.headers);
  if (token !== null && token !== undefined && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${token}`);
  }
  if (options.contentType === null) headers.delete("content-type");
  else if (!headers.has("content-type")) headers.set("content-type", options.contentType || "application/json");
  const init = { method, headers };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    init.body = options.raw === undefined
      ? (message === undefined ? undefined : JSON.stringify(message))
      : options.raw;
    if (init.body instanceof ReadableStream) init.duplex = "half";
  }
  const request = new Request(options.url || ENDPOINT, init);
  const env = options.env || (token ? { MI_MCP_PUBLIC_TOKEN: token } : {});
  return handler.fetch(request, env);
}

async function jsonBody(response) {
  return response.json();
}

function toolMessage(name, args, id = 1) {
  return rpc("tools/call", { name, arguments: args }, id);
}

test("Pages Function adapter forwards requests and deployment secrets", async () => {
  const token = ephemeralToken();
  const request = new Request(ENDPOINT, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify(rpc("ping")),
  });
  const accepted = await onRequest({ request, env: { MI_MCP_PUBLIC_TOKEN: token } });
  assert.equal(accepted.status, 200);
  assert.deepEqual(await jsonBody(accepted), { jsonrpc: "2.0", id: 1, result: {} });
  const deniedRequest = new Request(ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(rpc("ping")),
  });
  const denied = await onRequest({ request: deniedRequest, env: {} });
  assert.equal(denied.status, 401);
  assert.equal((await jsonBody(denied)).error.code, -32001);
});

test("initialize advertises the read-only MCP surface", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const response = await send(handler, token, rpc("initialize", {
    protocolVersion: "2025-03-26",
    capabilities: {},
    clientInfo: { name: "focused-test", version: "1" },
  }));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  const body = await jsonBody(response);
  assert.equal(body.jsonrpc, "2.0");
  assert.equal(body.id, 1);
  assert.equal(body.result.protocolVersion, "2025-03-26");
  assert.equal(body.result.serverInfo.name, "meaning-intelligence-web-mcp");
  assert.deepEqual(Object.keys(body.result.capabilities).sort(), ["resources", "tools"]);
  assert.match(body.result.instructions, /Human approval/i);
});

test("tools/list and resources/list expose only the intended public surface", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const toolsResponse = await send(handler, token, rpc("tools/list"));
  const tools = (await jsonBody(toolsResponse)).result.tools;
  assert.deepEqual(tools.map((tool) => tool.name), [
    "meaning_analyze",
    "meaning_review",
    "resource_catalog",
    "evidence_levels",
    "download_manifest",
  ]);
  for (const tool of tools) {
    assert.equal(tool.inputSchema.type, "object");
    assert.equal(tool.inputSchema.additionalProperties, false);
    assert.equal(tool.annotations.readOnlyHint, true);
    assert.equal(tool.annotations.destructiveHint, false);
  }
  assert.deepEqual(tools[0].inputSchema.required, ["text"]);
  assert.deepEqual(tools[1].inputSchema.required, ["previous", "feedback"]);

  const resourcesResponse = await send(handler, token, rpc("resources/list"));
  const resources = (await jsonBody(resourcesResponse)).result.resources;
  assert.deepEqual(resources.map((resource) => resource.uri), [
    "mi://canon/v7",
    "mi://evidence/e0-e6",
    "mi://chapters/zh",
    "mi://chapters/en",
    "mi://skills/l1-l6",
    "mi://downloads",
  ]);
  const templates = await jsonBody(await send(handler, token, rpc("resources/templates/list")));
  assert.deepEqual(templates.result.resourceTemplates, []);
  assert.deepEqual((await jsonBody(await send(handler, token, rpc("ping")))).result, {});
});

test("resources/read returns whitelisted bilingual resources and rejects file or URL URIs", async () => {
  const token = ephemeralToken();
  let fetchCalls = 0;
  const handler = createHandler({ fetchImpl: async () => { fetchCalls += 1; throw new Error("unexpected fetch"); } });
  const cases = [
    ["mi://canon/v7", (value) => value.version === "V7.0" && value.definition_zh && value.definition_en],
    ["mi://evidence/e0-e6", (value) => value.levels.length === 7 && value.levels[0].id === "E0" && value.levels[6].id === "E6"],
    ["mi://chapters/zh", (value) => value.language === "zh" && value.chapters.length === 7],
    ["mi://chapters/en", (value) => value.language === "en" && value.chapters.length === 7],
    ["mi://skills/l1-l6", (value) => value.skills.length === 6 && value.provenance_zh && value.provenance_en],
    ["mi://downloads", (value) => value.page === "/downloads.html" && value.manifest === "/download/manifest.json"],
  ];
  for (const [uri, verify] of cases) {
    const response = await send(handler, token, rpc("resources/read", { uri }));
    assert.equal(response.status, 200);
    const result = (await jsonBody(response)).result;
    assert.equal(result.contents.length, 1);
    assert.equal(result.contents[0].uri, uri);
    assert.equal(result.contents[0].mimeType, "application/json");
    assert.ok(verify(JSON.parse(result.contents[0].text)));
  }
  for (const uri of ["file:///etc/passwd", "https://evil.example/secret", "mi://../../etc/passwd", "/download/manifest.json"]) {
    const body = await jsonBody(await send(handler, token, rpc("resources/read", { uri })));
    assert.equal(body.error.code, -32002);
    assert.equal(body.error.message, "resource not found");
  }
  assert.equal(fetchCalls, 0);
});

test("meaning_analyze is deterministic, offline, evidence-bounded, and approval-gated", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const args = {
    text: "我们的使命是降低长期风险。边界是什么？应该保留人类价值。",
    context: "发布说明",
    language: "zh",
    scales: ["individual", "nation"],
  };
  const first = await jsonBody(await send(handler, token, toolMessage("meaning_analyze", args)));
  const second = await jsonBody(await send(handler, token, toolMessage("meaning_analyze", args)));
  assert.deepEqual(first, second);
  assert.equal(first.result.isError, false);
  const result = first.result.structuredContent;
  assert.equal(result.mode, "offline");
  assert.equal(result.language, "zh");
  assert.equal(result.source.canon, "V7.0");
  assert.equal(result.source.empirical_status, "not assessed");
  assert.deepEqual(result.approval, { required: true, status: "pending" });
  assert.equal(result.L4.assigned_level, "E0");
  assert.ok(result.L1.questions.some((question) => question.includes("边界")));
  assert.ok(result.L3.direction.length > 0);
  assert.ok(result.L3.boundary.length > 0);
  assert.equal(result.L5.scales.length, 5);
  assert.ok(result.L5.scales.every((scale) => scale.weighted_score === null));
  assert.equal(result.L5.scales.find((scale) => scale.id === "individual").status, "provided");
  assert.equal(result.L5.scales.find((scale) => scale.id === "city").status, "needs_input");
  assert.equal(result.L6.revision_suggestions.length, 0);
  assert.match(JSON.parse(first.result.content[0].text).L4.reason, /未提供/);
});

test("meaning_review accepts feedback without approval or evidence promotion", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const body = await jsonBody(await send(handler, token, toolMessage("meaning_review", {
    previous: { schema_version: "1.0", approval: { status: "pending" } },
    feedback: "请重新检查时间边界，并保留未经验证的前提。",
    language: "zh",
  })));
  assert.equal(body.result.isError, false);
  assert.equal(body.result.structuredContent.previous_received, true);
  assert.equal(body.result.structuredContent.evidence_level_changed, false);
  assert.deepEqual(body.result.structuredContent.approval, { required: true, status: "pending" });
  assert.equal(body.result.structuredContent.revision_suggestions.length, 3);
});

test("catalog tools work and unknown methods or tools return fixed JSON-RPC errors", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const catalog = await jsonBody(await send(handler, token, toolMessage("resource_catalog", {})));
  assert.equal(catalog.result.structuredContent.canon.version, "V7.0");
  assert.equal(catalog.result.structuredContent.resources.length, 6);
  const levels = await jsonBody(await send(handler, token, toolMessage("evidence_levels", {})));
  assert.equal(levels.result.structuredContent.levels.length, 7);
  const unknownMethod = await jsonBody(await send(handler, token, rpc("resources/write", { uri: "mi://canon/v7" })));
  assert.equal(unknownMethod.error.code, -32601);
  assert.equal(unknownMethod.error.message, "method not found");
  const unknownTool = await jsonBody(await send(handler, token, toolMessage("delete_everything", {})));
  assert.equal(unknownTool.error.code, -32602);
  assert.equal(unknownTool.error.message, "unknown tool");
});

test("tool argument validation rejects malformed, oversized, extra, and URL-bearing inputs", async () => {
  const token = ephemeralToken();
  let fetchCalls = 0;
  const handler = createHandler({ fetchImpl: async () => { fetchCalls += 1; throw new Error("unexpected"); } });
  const tooManyProperties = Object.fromEntries(Array.from({ length: 101 }, (_, index) => [`k${index}`, index]));
  const invalidCalls = [
    toolMessage("meaning_analyze", {}),
    toolMessage("meaning_analyze", { text: "   " }),
    toolMessage("meaning_analyze", { text: "x".repeat(12001) }),
    toolMessage("meaning_analyze", { text: "x", context: "x".repeat(2001) }),
    toolMessage("meaning_analyze", { text: "x", language: "fr" }),
    toolMessage("meaning_analyze", { text: "x", scales: ["individual", "individual"] }),
    toolMessage("meaning_analyze", { text: "x", scales: ["planet"] }),
    toolMessage("meaning_analyze", { text: "x", url: "https://evil.example/secret" }),
    toolMessage("meaning_analyze", []),
    toolMessage("meaning_review", { previous: [], feedback: "review" }),
    toolMessage("meaning_review", { previous: tooManyProperties, feedback: "review" }),
    toolMessage("meaning_review", { previous: {}, feedback: " " }),
    toolMessage("meaning_review", { previous: {}, feedback: "x".repeat(4001) }),
    toolMessage("download_manifest", { path: "/etc/passwd" }),
    toolMessage("resource_catalog", { uri: "file:///etc/passwd" }),
  ];
  for (const message of invalidCalls) {
    const body = await jsonBody(await send(handler, token, message));
    assert.equal(body.error.code, -32602);
    assert.equal(body.error.message, "invalid tool arguments");
  }
  assert.equal(fetchCalls, 0);
});

test("strong Bearer authentication is mandatory and malformed or weak configuration fails closed", async () => {
  const token = ephemeralToken();
  const wrong = ephemeralToken();
  const handler = createHandler();
  const unauthorizedCases = [
    [null, rpc("ping"), {}],
    [token, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: "short" } }],
    [token, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: "a".repeat(40) } }],
    [token, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: "abcdefghijklmnopqrstuvwxyz123456" } }],
    [token, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: `placeholder-${"x".repeat(32)}` } }],
    [token, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: "0123456789abcdef".repeat(4).replace(/[0-9a-f]/g, "a") } }],
    [token, rpc("ping"), { headers: { authorization: token } }],
    [token, rpc("ping"), { headers: { authorization: `Basic ${token}` } }],
    [token, rpc("ping"), { headers: { authorization: `Bearer  ${token}` } }],
    [wrong, rpc("ping"), { env: { MI_MCP_PUBLIC_TOKEN: token } }],
  ];
  for (const [supplied, message, options] of unauthorizedCases) {
    const response = await send(handler, supplied, message, options);
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("www-authenticate"), "Bearer");
    const body = await jsonBody(response);
    assert.equal(body.error.code, -32001);
    assert.equal(body.error.message, "unauthorized");
    assert.ok(!JSON.stringify(body).includes(token));
    assert.ok(!JSON.stringify(body).includes(wrong));
  }
  const accepted = await send(handler, token, rpc("ping"), { headers: { authorization: `bearer ${token}` } });
  assert.equal(accepted.status, 200);
});

test("only POST and preflight OPTIONS are accepted", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  for (const method of ["GET", "HEAD", "PUT", "PATCH", "DELETE"]) {
    const response = await send(handler, token, undefined, { method });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "POST, OPTIONS");
    assert.equal((await jsonBody(response)).error.message, "method not allowed");
  }
  const preflight = await send(handler, null, undefined, {
    method: "OPTIONS",
    headers: {
      origin: "https://meaning.example",
      "access-control-request-method": "POST",
      "access-control-request-headers": "authorization, content-type",
    },
  });
  assert.equal(preflight.status, 204);
  assert.equal(await preflight.text(), "");
});

test("POST requires an application/json content type", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  for (const contentType of [null, "text/plain", "application/x-www-form-urlencoded"]) {
    const response = await send(handler, token, rpc("ping"), { contentType });
    assert.equal(response.status, 415);
    assert.equal((await jsonBody(response)).error.message, "content-type must be application/json");
  }
  const accepted = await send(handler, token, rpc("ping"), { contentType: "application/json; charset=utf-8" });
  assert.equal(accepted.status, 200);
});

test("body cap is enforced by declared length and streamed UTF-8 bytes", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const declared = await send(handler, token, rpc("ping"), { headers: { "content-length": String(MAX_BODY_BYTES + 1) } });
  assert.equal(declared.status, 413);
  assert.equal((await jsonBody(declared)).error.message, "request too large");

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("x".repeat(20000)));
      controller.enqueue(new TextEncoder().encode("x".repeat(MAX_BODY_BYTES - 19999)));
      controller.close();
    },
  });
  const chunked = await send(handler, token, undefined, { raw: stream, headers: { "content-type": "application/json" } });
  assert.equal(chunked.status, 413);

  const multibyte = await send(handler, token, undefined, { raw: `${"x".repeat(16000)}${"汉".repeat(6000)}` });
  assert.equal(multibyte.status, 413);

  for (const value of ["not-a-number", "-1", "9".repeat(21)]) {
    const response = await send(handler, token, rpc("ping"), { headers: { "content-length": value } });
    assert.equal(response.status, 400);
    assert.equal((await jsonBody(response)).error.message, "invalid request");
  }
});

test("a valid JSON-RPC request at the exact body cap is accepted", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const prefix = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"padding":"';
  const suffix = '"}}';
  const raw = `${prefix}${"x".repeat(MAX_BODY_BYTES - prefix.length - suffix.length)}${suffix}`;
  assert.equal(Buffer.byteLength(raw, "utf8"), MAX_BODY_BYTES);
  const response = await send(handler, token, undefined, { raw });
  assert.equal(response.status, 200);
  assert.deepEqual((await jsonBody(response)).result, {});
});

test("malformed JSON, UTF-8, envelopes, batches, IDs, and params are sanitized", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const malformed = await send(handler, token, undefined, { raw: `{"jsonrpc":"2.0","token":"${token}"` });
  assert.equal(malformed.status, 400);
  const malformedText = await malformed.text();
  const malformedBody = JSON.parse(malformedText);
  assert.equal(malformedBody.error.code, -32700);
  assert.ok(!malformedText.includes(token));
  const invalidUtf8 = await send(handler, token, undefined, { raw: new Uint8Array([0xff, 0xfe]) });
  assert.equal((await jsonBody(invalidUtf8)).error.code, -32700);
  const invalidMessages = [
    null,
    [],
    {},
    { jsonrpc: "1.0", id: 1, method: "ping" },
    { jsonrpc: "2.0", id: 1, method: "" },
    { jsonrpc: "2.0", id: {}, method: "ping" },
    { jsonrpc: "2.0", id: 1, method: "ping", params: [] },
  ];
  for (const message of invalidMessages) {
    const response = await send(handler, token, message);
    assert.equal(response.status, 400);
    const body = await jsonBody(response);
    assert.equal(body.error.code, -32600);
    assert.equal(body.error.message, "invalid request");
  }
});

test("valid notifications receive an empty 202 and no result body", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const response = await send(handler, token, { jsonrpc: "2.0", method: "ping" });
  assert.equal(response.status, 202);
  assert.equal(await response.text(), "");
});

test("per-client sliding rate limit returns 429 and recovers without sleeping", async () => {
  const token = ephemeralToken();
  let now = 1_000_000;
  const handler = createHandler({ now: () => now, rateLimit: 2, windowMs: 1000, maxClients: 4 });
  for (let index = 0; index < 2; index += 1) {
    assert.equal((await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.10" } })).status, 200);
  }
  const limited = await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.10" } });
  assert.equal(limited.status, 429);
  assert.equal(limited.headers.get("retry-after"), "1");
  assert.equal((await jsonBody(limited)).error.message, "rate limit exceeded");
  assert.equal((await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.11" } })).status, 200);
  now += 1000;
  assert.equal((await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.10" } })).status, 200);
});

test("rate-limit client storage is bounded and fails closed when full", async () => {
  const token = ephemeralToken();
  const handler = createHandler({ now: () => 1_000_000, rateLimit: 1, windowMs: 60_000, maxClients: 1 });
  assert.equal((await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.10" } })).status, 200);
  const response = await send(handler, token, rpc("ping"), { headers: { "cf-connecting-ip": "192.0.2.11" } });
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "60");
});

test("same-origin and explicitly allowed origins receive exact CORS headers", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const sameOrigin = await send(handler, token, rpc("ping"), { headers: { origin: "https://meaning.example" } });
  assert.equal(sameOrigin.status, 200);
  assert.equal(sameOrigin.headers.get("access-control-allow-origin"), "https://meaning.example");
  assert.equal(sameOrigin.headers.get("access-control-allow-methods"), "POST, OPTIONS");
  assert.match(sameOrigin.headers.get("vary"), /Origin/);
  assert.equal(sameOrigin.headers.get("access-control-allow-credentials"), null);

  const allowed = await send(handler, token, rpc("ping"), {
    env: { MI_MCP_PUBLIC_TOKEN: token, MI_MCP_ALLOWED_ORIGINS: "https://client.example, https://invalid.example/path, *" },
    headers: { origin: "https://client.example" },
  });
  assert.equal(allowed.status, 200);
  assert.equal(allowed.headers.get("access-control-allow-origin"), "https://client.example");

  for (const origin of ["https://evil.example", "null", "https://invalid.example/path"]) {
    const denied = await send(handler, token, rpc("ping"), {
      env: { MI_MCP_PUBLIC_TOKEN: token, MI_MCP_ALLOWED_ORIGINS: "https://client.example, *" },
      headers: { origin },
    });
    assert.equal(denied.status, 403);
    assert.equal(denied.headers.get("access-control-allow-origin"), null);
    assert.equal((await jsonBody(denied)).error.message, "origin not allowed");
  }
});

test("preflight is unauthenticated, data-free, exact-origin, and validates requested method and headers", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const headers = {
    origin: "https://meaning.example",
    "access-control-request-method": "POST",
    "access-control-request-headers": "Authorization, Content-Type, MCP-Protocol-Version",
  };
  const allowed = await send(handler, null, undefined, { method: "OPTIONS", headers });
  assert.equal(allowed.status, 204);
  assert.equal(allowed.headers.get("access-control-allow-origin"), "https://meaning.example");
  assert.equal(allowed.headers.get("access-control-allow-headers"), "authorization, content-type, mcp-protocol-version");
  assert.equal(allowed.headers.get("access-control-max-age"), "600");
  assert.equal(await allowed.text(), "");

  const invalidCases = [
    { ...headers, origin: "https://evil.example" },
    { ...headers, "access-control-request-method": "DELETE" },
    { ...headers, "access-control-request-headers": "authorization, x-evil" },
  ];
  for (const invalidHeaders of invalidCases) {
    const denied = await send(handler, null, undefined, { method: "OPTIONS", headers: invalidHeaders });
    assert.equal(denied.status, 403);
    assert.equal(denied.headers.get("access-control-allow-origin"), null);
    assert.equal(denied.headers.get("access-control-allow-methods"), null);
  }
});

test("download_manifest fetches only the fixed same-origin path without forwarding auth or following redirects", async () => {
  const token = ephemeralToken();
  const calls = [];
  const manifest = { version: "1.1", files: [{ path: "download/example.epub", bytes: 42, sha256: "a".repeat(64) }] };
  const handler = createHandler({
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return new Response(JSON.stringify(manifest), { status: 200, headers: { "content-type": "application/json" } });
    },
  });
  const response = await send(handler, token, toolMessage("download_manifest", {}), {
    url: "https://meaning.example/nested/api/mcp?ignored=1",
  });
  assert.equal(response.status, 200);
  const body = await jsonBody(response);
  assert.equal(body.result.isError, false);
  assert.deepEqual(body.result.structuredContent, manifest);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://meaning.example/download/manifest.json");
  assert.equal(calls[0].options.redirect, "manual");
  assert.equal(calls[0].options.headers.authorization, undefined);
  assert.ok(calls[0].options.signal instanceof AbortSignal);

  let redirectCalls = 0;
  const redirectHandler = createHandler({
    fetchImpl: async (url, options) => {
      redirectCalls += 1;
      assert.equal(options.redirect, "manual");
      return new Response(null, { status: 302, headers: { location: "https://evil.example/secret" } });
    },
  });
  const redirected = await jsonBody(await send(redirectHandler, token, toolMessage("download_manifest", {})));
  assert.equal(redirected.error.code, -32003);
  assert.equal(redirected.error.message, "download manifest unavailable");
  assert.ok(!JSON.stringify(redirected).includes("evil.example"));
  assert.equal(redirectCalls, 1);
});

test("manifest failures and oversized responses are sanitized and never log credentials", async () => {
  const token = ephemeralToken();
  const calls = [];
  const originalConsole = { log: console.log, info: console.info, warn: console.warn, error: console.error, debug: console.debug };
  for (const method of Object.keys(originalConsole)) console[method] = (...args) => { calls.push(args.map(String).join(" ")); };
  try {
    const handler = createHandler({ fetchImpl: async () => { throw new Error(`upstream ${token} file:///etc/passwd`); } });
    const response = await send(handler, token, toolMessage("download_manifest", {}));
    const serialized = await response.clone().text();
    assert.equal(response.status, 200);
    assert.equal(JSON.parse(serialized).error.message, "download manifest unavailable");
    assert.ok(!serialized.includes(token));
    assert.ok(!serialized.includes("/etc/passwd"));
    assert.deepEqual(calls, []);

    const oversized = createHandler({ fetchImpl: async () => new Response("x".repeat(65537), { status: 200 }) });
    const oversizedBody = await jsonBody(await send(oversized, token, toolMessage("download_manifest", {})));
    assert.equal(oversizedBody.error.message, "download manifest unavailable");
    assert.ok(!JSON.stringify(oversizedBody).includes("x".repeat(100)));

    const invalid = createHandler({ fetchImpl: async () => new Response("not json", { status: 200 }) });
    const invalidBody = await jsonBody(await send(invalid, token, toolMessage("download_manifest", {})));
    assert.equal(invalidBody.error.message, "download manifest unavailable");
    assert.deepEqual(calls, []);
  } finally {
    Object.assign(console, originalConsole);
  }
});

test("unexpected internal exceptions do not echo secrets or implementation details", async () => {
  const token = ephemeralToken();
  const handler = createHandler();
  const env = new Proxy({}, { get() { throw new Error(`secret ${token} at file:///etc/passwd`); } });
  const response = await send(handler, token, rpc("ping"), { env });
  assert.equal(response.status, 500);
  const serialized = await response.text();
  assert.equal(JSON.parse(serialized).error.code, -32603);
  assert.equal(JSON.parse(serialized).error.message, "internal error");
  assert.ok(!serialized.includes(token));
  assert.ok(!serialized.includes("/etc/passwd"));
});

const publicationRoot = fileURLToPath(new URL("../../../意义智能有声读物_发布包/", import.meta.url));
let publicationAvailable = true;
try {
  await access(publicationRoot);
} catch {
  publicationAvailable = false;
}

test("publication function is a byte-identical reproducible copy", { skip: !publicationAvailable }, async () => {
  const source = await readFile(new URL("../functions/api/mcp.js", import.meta.url));
  const published = await readFile(new URL("../../../意义智能有声读物_发布包/functions/api/mcp.js", import.meta.url));
  assert.ok(source.equals(published), "run npm run sync:publication from web-mcp");
});

test("publication mcp.html is bilingual, memory-only, and has valid inline JavaScript", { skip: !publicationAvailable }, async () => {
  let html;
  try {
    html = await readFile(new URL("../../../意义智能有声读物_发布包/mcp.html", import.meta.url), "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /意义智能/);
  assert.match(html, /Meaning Intelligence/);
  assert.match(html, /\/api\/mcp/);
  assert.match(html, /MI_MCP_PUBLIC_TOKEN/);
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
  assert.equal(scripts.length, 1);
  assert.doesNotMatch(scripts[0], /localStorage|sessionStorage|console\.|\.innerHTML/);
  assert.doesNotThrow(() => new Function(scripts[0]));
});
