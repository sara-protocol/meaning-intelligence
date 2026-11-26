import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile, access } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const staging = resolve(process.argv[2] || fileURLToPath(new URL("../../../意义智能有声读物_发布包/", import.meta.url)));
const output = resolve(process.argv[3] || fileURLToPath(new URL("../../../deliverables/web-mcp-pages-runtime-rehearsal.json", import.meta.url)));
const token = `Aa1!${randomBytes(24).toString("base64url")}`;
const checks = [];
const errors = [];
let child;
let serverOutput = "";
let temporaryState;
let cleanedUp = false;

function check(name, condition, detail = "") {
  checks.push({ name, ok: Boolean(condition), detail: String(detail).slice(0, 500) });
  if (!condition) errors.push(name);
}

function sanitized(value) {
  return String(value).replaceAll(token, "[redacted]");
}

async function freePort() {
  const server = createServer();
  await new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const address = server.address();
  await new Promise((resolveClose, rejectClose) => server.close(error => error ? rejectClose(error) : resolveClose()));
  return address.port;
}

async function stopServer() {
  if (child && child.exitCode === null) {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { windowsHide: true, stdio: "ignore" });
    } else {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch {
        child.kill("SIGTERM");
      }
    }
    await Promise.race([
      new Promise(resolveExit => child.once("exit", resolveExit)),
      new Promise(resolveTimeout => setTimeout(resolveTimeout, 5000)),
    ]);
  }
  if (temporaryState) {
    let lastError;
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try {
        await rm(temporaryState, { recursive: true, force: true });
        cleanedUp = true;
        return;
      } catch (error) {
        lastError = error;
        await new Promise(resolveWait => setTimeout(resolveWait, 500));
      }
    }
    throw lastError;
  }
}

async function wranglerEntrypoint() {
  if (process.env.MI_WRANGLER_JS) {
    const override = resolve(process.env.MI_WRANGLER_JS);
    await access(override);
    return override;
  }
  if (process.platform === "win32" && process.env.APPDATA) {
    const candidate = resolve(process.env.APPDATA, "npm/node_modules/wrangler/bin/wrangler.js");
    try {
      await access(candidate);
      return candidate;
    } catch {
      // Fall through to the npm global lookup for non-default Windows prefixes.
    }
  }
  const result = spawnSync("npm", ["root", "-g"], {
    encoding: "utf8",
    windowsHide: true,
    shell: false,
  });
  if (result.status !== 0) throw new Error("Unable to locate the global Wrangler package");
  const candidate = resolve(result.stdout.trim(), "wrangler/bin/wrangler.js");
  await access(candidate);
  return candidate;
}

async function rpc(message, options = {}) {
  const headers = new Headers(options.headers);
  if (options.auth !== false) headers.set("authorization", `Bearer ${options.token || token}`);
  if (options.contentType === null) headers.delete("content-type");
  else headers.set("content-type", options.contentType || "application/json");
  const init = { method: options.method || "POST", headers };
  if (!["GET", "HEAD", "OPTIONS"].includes(init.method)) {
    init.body = options.raw === undefined ? JSON.stringify(message) : options.raw;
  }
  const response = await fetch(`${options.baseUrl || baseUrl}/api/mcp`, { ...init, signal: AbortSignal.timeout(15000) });
  const text = await response.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  return { status: response.status, headers: response.headers, text, body };
}

function message(method, params, id = 1) {
  return { jsonrpc: "2.0", id, method, ...(params === undefined ? {} : { params }) };
}

function tool(name, args = {}, id = 1) {
  return message("tools/call", { name, arguments: args }, id);
}

let baseUrl;

try {
  temporaryState = await mkdtemp(resolve(tmpdir(), "mi-pages-rehearsal-"));
  const port = await freePort();
  baseUrl = `http://127.0.0.1:${port}`;
  const wrangler = await wranglerEntrypoint();
  child = spawn(process.execPath, [
    wrangler,
    "pages", "dev", staging,
    "--ip", "127.0.0.1",
    "--port", String(port),
    "--persist-to", temporaryState,
    "--binding", `MI_MCP_PUBLIC_TOKEN=${token}`,
    "--binding", "MI_MCP_ALLOWED_ORIGINS=https://allowed.example",
    "--show-interactive-dev-session=false",
    "--log-level", "error",
  ], {
    cwd: staging,
    detached: process.platform !== "win32",
    windowsHide: true,
    env: {
      ...process.env,
      CI: "1",
      NO_COLOR: "1",
      WRANGLER_SEND_METRICS: "false",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  for (const stream of [child.stdout, child.stderr]) {
    stream.on("data", chunk => {
      serverOutput = (serverOutput + chunk.toString("utf8")).slice(-65536);
    });
  }

  const deadline = Date.now() + 60000;
  let ready = false;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) break;
    try {
      const response = await rpc(undefined, { method: "GET", auth: false });
      if (response.status === 405) {
        ready = true;
        break;
      }
    } catch {
      // The local runtime is still starting.
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 250));
  }
  check("pages-runtime-ready", ready, ready ? baseUrl : sanitized(serverOutput));

  if (ready) {
    const get = await rpc(undefined, { method: "GET", auth: false });
    check("get-method-rejected", get.status === 405 && get.body?.error?.message === "method not allowed");

    const preflight = await rpc(undefined, {
      method: "OPTIONS",
      auth: false,
      headers: {
        origin: baseUrl,
        "access-control-request-method": "POST",
        "access-control-request-headers": "authorization, content-type, mcp-protocol-version",
      },
    });
    check("preflight-exact-origin", preflight.status === 204 && preflight.headers.get("access-control-allow-origin") === baseUrl);

    const allowedOrigin = await rpc(message("ping"), { headers: { origin: "https://allowed.example" } });
    check("configured-origin-allowed", allowedOrigin.status === 200 && allowedOrigin.headers.get("access-control-allow-origin") === "https://allowed.example");

    const initialize = await rpc(message("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "pages-runtime-rehearsal", version: "1.0" },
    }), { headers: { "mcp-protocol-version": "2025-03-26" } });
    check("initialize-protocol", initialize.status === 200 && initialize.body?.result?.protocolVersion === "2025-03-26" && initialize.body?.result?.serverInfo?.version === "1.0.0");

    const initialized = await rpc({ jsonrpc: "2.0", method: "notifications/initialized" });
    check("initialized-notification", initialized.status === 202 && initialized.text === "");

    const tools = await rpc(message("tools/list"));
    const toolList = tools.body?.result?.tools || [];
    check("tools-list-read-only", tools.status === 200 && toolList.length === 5 && toolList.every(item => item.annotations?.readOnlyHint === true && item.annotations?.destructiveHint === false));

    const resources = await rpc(message("resources/list"));
    const resourceList = resources.body?.result?.resources || [];
    check("resources-list-six", resources.status === 200 && resourceList.length === 6);

    const resourceReads = [];
    for (const resource of resourceList) {
      resourceReads.push(await rpc(message("resources/read", { uri: resource.uri })));
    }
    check("resources-read-all", resourceReads.every(response => response.status === 200 && response.body?.result?.contents?.length === 1));

    const arbitraryResource = await rpc(message("resources/read", { uri: "file:///etc/passwd" }));
    check("arbitrary-resource-denied", arbitraryResource.body?.error?.code === -32002 && !arbitraryResource.text.includes("/etc/passwd"));

    const analyzeArgs = { text: "我们的使命是降低长期风险。边界是什么？应该保留人类价值。", language: "zh", scales: ["individual", "nation"] };
    const analyzeZh = await rpc(tool("meaning_analyze", analyzeArgs));
    const analyzeZhResult = analyzeZh.body?.result?.structuredContent;
    check("analyze-zh-six-skills", analyzeZh.status === 200 && analyzeZhResult?.language === "zh" && ["L1", "L2", "L3", "L4", "L5", "L6"].every(key => key in analyzeZhResult));
    check("analyze-evidence-bounded", analyzeZhResult?.L4?.assigned_level === "E0" && analyzeZhResult?.source?.empirical_status === "not assessed");
    check("analyze-human-approval", analyzeZhResult?.approval?.required === true && analyzeZhResult?.approval?.status === "pending");
    const analyzeRepeat = await rpc(tool("meaning_analyze", analyzeArgs));
    check("analyze-deterministic", JSON.stringify(analyzeRepeat.body) === JSON.stringify(analyzeZh.body));

    const analyzeEn = await rpc(tool("meaning_analyze", { text: "Our mission is to reduce long-term risk. What is the boundary?", language: "en" }));
    check("analyze-english", analyzeEn.body?.result?.structuredContent?.language === "en" && analyzeEn.body?.result?.structuredContent?.L6?.review_questions?.length === 3);

    const review = await rpc(tool("meaning_review", { previous: { approval: { status: "pending" } }, feedback: "Recheck the time boundary.", language: "en" }));
    check("review-no-auto-approval", review.body?.result?.structuredContent?.evidence_level_changed === false && review.body?.result?.structuredContent?.approval?.status === "pending");

    const catalog = await rpc(tool("resource_catalog"));
    check("catalog-canon", catalog.body?.result?.structuredContent?.canon?.version === "V7.0" && catalog.body?.result?.structuredContent?.resources?.length === 6);

    const levels = await rpc(tool("evidence_levels"));
    check("evidence-levels-e0-e6", levels.body?.result?.structuredContent?.levels?.length === 7 && levels.body?.result?.structuredContent?.levels?.[0]?.id === "E0" && levels.body?.result?.structuredContent?.levels?.[6]?.id === "E6");

    const manifestTool = await rpc(tool("download_manifest"));
    const localManifest = JSON.parse(await readFile(resolve(staging, "download/manifest.json"), "utf8"));
    check("download-manifest-same-origin", manifestTool.status === 200 && JSON.stringify(manifestTool.body?.result?.structuredContent) === JSON.stringify(localManifest) && localManifest.files.length === 43);

    const unauthorized = await rpc(message("ping"), { auth: false });
    check("bearer-required", unauthorized.status === 401 && unauthorized.headers.get("www-authenticate") === "Bearer");

    const wrongToken = await rpc(message("ping"), { token: `Bb2!${randomBytes(24).toString("base64url")}` });
    check("wrong-bearer-denied", wrongToken.status === 401);

    const disallowedOrigin = await rpc(message("ping"), { headers: { origin: "https://denied.example" } });
    check("origin-deny", disallowedOrigin.status === 403 && !disallowedOrigin.headers.get("access-control-allow-origin"));

    const wrongContentType = await rpc(message("ping"), { contentType: "text/plain" });
    check("content-type-rejected", wrongContentType.status === 415);

    const oversized = await rpc(undefined, { raw: "x".repeat(32769) });
    check("body-cap", oversized.status === 413);

    const malformed = await rpc(undefined, { raw: `{"jsonrpc":"2.0","token":"${token}"` });
    check("malformed-sanitized", malformed.status === 400 && malformed.body?.error?.code === -32700 && !malformed.text.includes(token));

    const unknownMethod = await rpc(message("resources/write", { uri: "mi://canon/v7" }));
    check("write-method-denied", unknownMethod.body?.error?.code === -32601);

    check("security-headers", initialize.headers.get("cache-control") === "no-store" && initialize.headers.get("x-content-type-options") === "nosniff" && initialize.headers.get("x-frame-options") === "DENY" && initialize.headers.get("referrer-policy") === "no-referrer");

    const responseTexts = [get, preflight, allowedOrigin, initialize, initialized, tools, resources, ...resourceReads, arbitraryResource, analyzeZh, analyzeRepeat, analyzeEn, review, catalog, levels, manifestTool, unauthorized, wrongToken, disallowedOrigin, wrongContentType, oversized, malformed, unknownMethod].map(response => response.text).join("\n");
    check("no-token-in-responses", !responseTexts.includes(token));

    let rateLimited = false;
    let rateRequests = 0;
    for (let index = 0; index < 65; index += 1) {
      const response = await rpc(message("ping"));
      rateRequests += 1;
      if (response.status === 429) {
        rateLimited = response.headers.get("retry-after") !== null;
        break;
      }
    }
    check("sliding-rate-limit", rateLimited, `${rateRequests} requests`);
  }
} catch (error) {
  errors.push(sanitized(error?.stack || error?.message || error));
} finally {
  try {
    await stopServer();
  } catch (error) {
    errors.push(sanitized(error?.stack || error?.message || error));
  }
}

check("temporary-state-cleaned", cleanedUp);
check("no-token-in-runtime-output", !serverOutput.includes(token));
const ok = errors.length === 0;
const report = {
  schema: "meaning-intelligence-web-mcp-pages-runtime-rehearsal-v1",
  generated_utc: new Date().toISOString(),
  engine: "wrangler-pages-dev-local",
  staging,
  endpoint: baseUrl || null,
  authentication: "ephemeral in-memory Bearer token; no credential value recorded",
  checks_passed: checks.filter(item => item.ok).length,
  checks_total: checks.length,
  failed: checks.filter(item => !item.ok),
  errors: errors.map(sanitized),
  temporary_state_cleaned: cleanedUp,
  token_recorded: false,
  ok,
};
await mkdir(dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ ok, checks_passed: report.checks_passed, checks_total: report.checks_total, failed: report.failed, errors: report.errors, output }, null, 2));
process.exitCode = ok ? 0 : 1;
