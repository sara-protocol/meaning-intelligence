/**
 * Meaning Intelligence public, read-only Web MCP (Cloudflare Pages Function).
 *
 * Required configuration:
 *   MI_MCP_PUBLIC_TOKEN: a strong secret; see isStrongToken below.
 * Optional configuration:
 *   MI_MCP_ALLOWED_ORIGINS: comma-separated exact HTTP(S) origins for
 *   cross-origin clients. The publication's own origin is always allowed.
 *
 * This module deliberately has no filesystem access, no arbitrary URL fetches,
 * no persistence, and no logging. The only outbound request is the fixed,
 * same-origin public download manifest, with redirects disabled.
 */

const PROTOCOL_VERSION = "2025-03-26";
const MAX_BODY_BYTES = 32768;
const MAX_MANIFEST_BYTES = 65536;
const MANIFEST_PATH = "/download/manifest.json";
const RATE_LIMIT = 60;
const RATE_WINDOW_MS = 60000;
const MAX_RATE_CLIENTS = 4096;
const MIN_TOKEN_CHARS = 32;
const MAX_TOKEN_CHARS = 256;
const SCALE_IDS = Object.freeze(["individual", "organization", "city", "nation", "civilization"]);
const ALLOWED_REQUEST_HEADERS = new Set(["authorization", "content-type", "mcp-protocol-version"]);
const SECURITY_HEADERS = Object.freeze({
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "no-referrer",
  "permissions-policy": "camera=(), microphone=(), geolocation=()",
});

const CANON = Object.freeze({
  version: "V7.0",
  definition_zh: "意义智能是对其他智能活动的方向性调控。",
  definition_en: "Meaning intelligence is the directional regulation of other intelligent activities.",
  provenance_zh: "六层栈与三带是本项目的 E0 工程扩展，不是正典固定层次；正典 H1–H18 与附录 D.7 优先。",
  provenance_en: "The six-layer stack and three bands are this project's E0 engineering extension, not a fixed canon hierarchy. Canon H1–H18 and Appendix D.7 prevail.",
});

const EVIDENCE = Object.freeze([
  ["E0", "构念已定义", "Construct defined"],
  ["E1", "已建立数学模型", "Mathematical model established"],
  ["E2", "测量工具存在，信效度验证中", "Instrument exists; reliability and validity under validation"],
  ["E3", "有预注册假设，数据收集中", "Preregistered hypothesis; data collection under way"],
  ["E4", "独立实验室复现", "Independent-laboratory replication"],
  ["E5", "预注册证伪标准已检验", "Preregistered falsification criterion tested"],
  ["E6", "跨情境、跨文化、跨时间泛化", "Generalization across contexts, cultures, and time"],
]);

const CHAPTERS = Object.freeze({
  zh: [
    "第一章 · 为什么现在需要意义智能",
    "第二章 · 核心理论体系",
    "第三章 · 运行机制与工程化",
    "第四章 · 多尺度多领域实践",
    "第五章 · 文明演化总结与展望",
    "附录 · 实践工具与研究支撑",
    "全书总结 · 给智能装上方向舵",
  ],
  en: [
    "Chapter 1 · Why Now",
    "Chapter 2 · Core Theory",
    "Chapter 3 · Mechanisms & Engineering",
    "Chapter 4 · Multi-Scale Practice",
    "Chapter 5 · Civilization & Roadmap",
    "Appendix · Toolkit",
    "Summary · A Rudder for Intelligence",
  ],
});

const SKILLS = Object.freeze([
  { id: "L1", name_zh: "减负", name_en: "Load reduction", output: "facts, questions, structure" },
  { id: "L2", name_zh: "可体验", name_en: "Experiential rendering", output: "interactive HTML and parameter suggestions" },
  { id: "L3", name_zh: "意义生成", name_en: "Meaning generation", output: "direction, value, boundary, spectrum placement" },
  { id: "L4", name_zh: "价值评估", name_en: "Evidence assessment", output: "E0–E6 status and falsification conditions" },
  { id: "L5", name_zh: "方向选择", name_en: "Direction selection", output: "five-scale conflicts, priorities, costs and triggers; never weighted summation" },
  { id: "L6", name_zh: "反思与审视递归", name_en: "Recursive review", output: "metacognitive questions, review triggers and revision suggestions" },
]);

const EMPTY_SCHEMA = Object.freeze({ type: "object", properties: {}, additionalProperties: false });
const TOOLS = Object.freeze([
  {
    name: "meaning_analyze",
    description: "Run the six Meaning Intelligence skills in deterministic offline mode. No empirical status is invented; human approval remains pending. / 离线运行六项技能，不虚构实证等级，始终等待人类批准。",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string", minLength: 1, maxLength: 12000 },
        language: { type: "string", enum: ["auto", "zh", "en"], default: "auto" },
        context: { type: "string", maxLength: 2000, default: "" },
        scales: {
          type: "array",
          maxItems: 5,
          uniqueItems: true,
          items: { type: "string", enum: [...SCALE_IDS] },
        },
      },
      required: ["text"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "meaning_review",
    description: "Review a previous analysis against human feedback without automatically approving or executing changes. / 根据人工反馈复核既有分析，不自动批准或执行变更。",
    inputSchema: {
      type: "object",
      properties: {
        previous: { type: "object", maxProperties: 100 },
        feedback: { type: "string", minLength: 1, maxLength: 4000 },
        language: { type: "string", enum: ["auto", "zh", "en"], default: "auto" },
      },
      required: ["previous", "feedback"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "resource_catalog",
    description: "List bilingual canon, evidence, chapter, skill and download resources. / 列出双语正典、证据、章节、技能与下载资源。",
    inputSchema: EMPTY_SCHEMA,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "evidence_levels",
    description: "Read the canonical V7.0 E0–E6 definitions. / 读取正典 V7.0 的 E0–E6 定义。",
    inputSchema: EMPTY_SCHEMA,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "download_manifest",
    description: "Read the fixed same-origin published download manifest with sizes and SHA-256 hashes. / 读取同源固定发布清单及其大小与 SHA-256。",
    inputSchema: EMPTY_SCHEMA,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
]);

const RESOURCES = Object.freeze([
  { uri: "mi://canon/v7", name: "Canon V7.0 · 正典", description: "Bilingual definition and provenance / 双语定义与来源边界", mimeType: "application/json" },
  { uri: "mi://evidence/e0-e6", name: "Evidence E0–E6 · 证据等级", description: "Canonical evidence definitions / 正典证据定义", mimeType: "application/json" },
  { uri: "mi://chapters/zh", name: "中文章节", description: "Published Chinese chapter titles / 发布版中文章节", mimeType: "application/json" },
  { uri: "mi://chapters/en", name: "English chapters", description: "Published English chapter titles / 发布版英文章节", mimeType: "application/json" },
  { uri: "mi://skills/l1-l6", name: "Six engineering skills · 六项技能", description: "E0 engineering extension / E0 工程扩展", mimeType: "application/json" },
  { uri: "mi://downloads", name: "Download center · 下载中心", description: "Same-origin publication links only / 仅同源发布链接", mimeType: "application/json" },
]);

const RESOURCE_VALUES = new Map([
  ["mi://canon/v7", () => CANON],
  ["mi://evidence/e0-e6", () => ({ canon: "V7.0", levels: EVIDENCE.map(([id, zh, en]) => ({ id, zh, en })) })],
  ["mi://chapters/zh", () => ({ language: "zh", chapters: CHAPTERS.zh })],
  ["mi://chapters/en", () => ({ language: "en", chapters: CHAPTERS.en })],
  ["mi://skills/l1-l6", () => ({ provenance_zh: CANON.provenance_zh, provenance_en: CANON.provenance_en, skills: SKILLS })],
  ["mi://downloads", () => ({ page: "/downloads.html", manifest: MANIFEST_PATH, note: "Published same-origin files only; no arbitrary URL or file access. / 仅发布同源文件，不支持任意 URL 或文件访问。" })],
]);

class RpcError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "RpcError";
    this.code = code;
  }
}

class TransportError extends Error {
  constructor(message, status, code = -32600, headers = {}) {
    super(message);
    this.name = "TransportError";
    this.status = status;
    this.code = code;
    this.headers = headers;
  }
}

class LimitExceeded extends Error {}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function json(value, status = 200, headers = {}) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...SECURITY_HEADERS,
      ...headers,
    },
  });
}

function empty(status, headers = {}) {
  return new Response(null, { status, headers: { ...SECURITY_HEADERS, ...headers } });
}

function rpcError(id, code, message, status = 200, headers = {}) {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } }, status, headers);
}

function secureEqual(left, right) {
  const encoder = new TextEncoder();
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let index = 0; index < a.length; index += 1) difference |= a[index] ^ b[index];
  return difference === 0;
}

/** Conservative policy shared with the repository's Python public MCP. */
function isStrongToken(token) {
  if (typeof token !== "string" || token.length < MIN_TOKEN_CHARS || token.length > MAX_TOKEN_CHARS) return false;
  if (token !== token.trim() || [...token].some((char) => char.charCodeAt(0) < 0x21 || char.charCodeAt(0) > 0x7e)) return false;
  const lowered = token.toLowerCase();
  if (["placeholder", "changeme", "change-me", "password", "replace-this"].some((marker) => lowered.includes(marker))) return false;
  if (/^[0-9a-f]{64,}$/i.test(token)) return new Set(lowered).size >= 8;
  const classes = [
    /[a-z]/.test(token),
    /[A-Z]/.test(token),
    /[0-9]/.test(token),
    /[^a-zA-Z0-9]/.test(token),
  ].filter(Boolean).length;
  return classes >= 3 && new Set(token).size >= 12;
}

function authorized(request, env) {
  const expected = env?.MI_MCP_PUBLIC_TOKEN;
  if (!isStrongToken(expected)) return false;
  const match = /^Bearer ([\x21-\x7e]{32,256})$/i.exec(request.headers.get("authorization") || "");
  return match !== null && secureEqual(match[1], expected);
}

function normalizeOrigin(value) {
  if (typeof value !== "string" || !/^https?:\/\/[^/?#]+$/i.test(value)) return null;
  try {
    const parsed = new URL(value);
    if (!parsed.hostname || parsed.username || parsed.password) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

function corsFor(request, env) {
  const headers = { vary: "Origin" };
  const origin = request.headers.get("origin");
  if (!origin) return { allowed: true, headers };
  const normalized = normalizeOrigin(origin);
  let requestOrigin = null;
  try {
    requestOrigin = new URL(request.url).origin;
  } catch {
    requestOrigin = null;
  }
  const configured = new Set(
    (typeof env?.MI_MCP_ALLOWED_ORIGINS === "string" ? env.MI_MCP_ALLOWED_ORIGINS : "")
      .split(",")
      .map((item) => normalizeOrigin(item.trim()))
      .filter(Boolean),
  );
  if (!normalized || (normalized !== requestOrigin && !configured.has(normalized))) {
    return { allowed: false, headers };
  }
  return {
    allowed: true,
    headers: {
      ...headers,
      "access-control-allow-origin": origin,
      "access-control-allow-methods": "POST, OPTIONS",
      "access-control-allow-headers": "authorization, content-type, mcp-protocol-version",
      "access-control-max-age": "600",
    },
  };
}

function preflight(request, cors) {
  const requestedMethod = (request.headers.get("access-control-request-method") || "").toUpperCase();
  const requestedHeaders = (request.headers.get("access-control-request-headers") || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  const valid = cors.allowed
    && requestedMethod === "POST"
    && requestedHeaders.every((header) => ALLOWED_REQUEST_HEADERS.has(header));
  if (!valid) {
    return rpcError(null, -32000, "origin not allowed", 403, {
      vary: "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
    });
  }
  return empty(204, {
    ...cors.headers,
    vary: "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
  });
}

function clientKey(request) {
  const value = (request.headers.get("cf-connecting-ip") || "").trim();
  return value && value.length <= 64 ? value : "local";
}

async function readLimitedBytes(stream, maximum) {
  if (!stream) throw new Error("missing body");
  const reader = stream.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maximum) {
        try {
          await reader.cancel();
        } catch {
          // The limit error is fixed and must not expose stream details.
        }
        throw new LimitExceeded();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

async function readJsonRequest(request) {
  const declared = request.headers.get("content-length");
  if (declared !== null) {
    if (!/^\d+$/.test(declared) || declared.length > 20) {
      throw new TransportError("invalid request", 400);
    }
    const length = Number(declared);
    if (!Number.isSafeInteger(length)) throw new TransportError("invalid request", 400);
    if (length > MAX_BODY_BYTES) throw new TransportError("request too large", 413);
  }
  let bytes;
  try {
    bytes = await readLimitedBytes(request.body, MAX_BODY_BYTES);
  } catch (error) {
    if (error instanceof LimitExceeded) throw new TransportError("request too large", 413);
    throw new TransportError("parse error", 400, -32700);
  }
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    return JSON.parse(text);
  } catch {
    throw new TransportError("parse error", 400, -32700);
  }
}

function validateMessage(message) {
  if (!isPlainObject(message) || message.jsonrpc !== "2.0" || typeof message.method !== "string") {
    throw new TransportError("invalid request", 400);
  }
  if (!message.method || message.method.length > 128) throw new TransportError("invalid request", 400);
  if (Object.hasOwn(message, "id")) {
    const validString = typeof message.id === "string" && message.id.length <= 256;
    const validNumber = typeof message.id === "number" && Number.isFinite(message.id);
    if (!validString && !validNumber) throw new TransportError("invalid request", 400);
  }
  if (Object.hasOwn(message, "params") && !isPlainObject(message.params)) {
    throw new TransportError("invalid request", 400);
  }
  return message;
}

function languageOf(text, requested = "auto") {
  if (requested !== "auto") return requested;
  const cjk = (text.match(/[\u3400-\u9fff]/g) || []).length;
  return cjk >= Math.max(2, text.length * 0.15) ? "zh" : "en";
}

function sentences(text) {
  return text.split(/(?<=[。！？!?])|\n+/).map((item) => item.trim()).filter(Boolean).slice(0, 80);
}

function invalidArguments() {
  return new RpcError(-32602, "invalid tool arguments");
}

function validateArguments(args, allowed, required = []) {
  if (!isPlainObject(args) || Object.keys(args).some((key) => !allowed.includes(key))) throw invalidArguments();
  for (const key of required) if (!Object.hasOwn(args, key)) throw invalidArguments();
}

function validLanguage(value) {
  return value === undefined || value === "auto" || value === "zh" || value === "en";
}

function analyze(input) {
  validateArguments(input, ["text", "language", "context", "scales"], ["text"]);
  if (typeof input.text !== "string" || !input.text.trim() || input.text.length > 12000) throw invalidArguments();
  if (input.context !== undefined && (typeof input.context !== "string" || input.context.length > 2000)) throw invalidArguments();
  if (!validLanguage(input.language)) throw invalidArguments();
  if (input.scales !== undefined) {
    if (!Array.isArray(input.scales) || input.scales.length > 5
      || input.scales.some((scale) => !SCALE_IDS.includes(scale))
      || new Set(input.scales).size !== input.scales.length) throw invalidArguments();
  }
  const language = languageOf(input.text, input.language);
  const zh = language === "zh";
  const parts = sentences(input.text);
  const questions = parts.filter((item) => /[?？]/.test(item) || (zh && /^(为什么|如何|是否|什么|谁|何时)/.test(item)));
  const facts = parts.filter((item) => !questions.includes(item));
  const directionSignals = parts.filter((item) => /方向|目标|使命|应该|值得|direction|goal|mission|worth|ought/i.test(item));
  const valueSignals = parts.filter((item) => /价值|效用|关系|成本|value|utility|relation|cost/i.test(item));
  const boundarySignals = parts.filter((item) => /边界|时间|范围|限制|boundary|scope|limit|deadline/i.test(item));
  const abstract = /文明|长期|战略|人类|civilization|long.term|strategy|humanity/i.test(input.text);
  const scaleNames = zh ? ["个人", "组织", "城市", "国家", "人类"] : SCALE_IDS;
  const selectedScales = input.scales || [];
  const scales = SCALE_IDS.map((id, index) => ({
    id,
    name: scaleNames[index],
    status: selectedScales.includes(id) ? "provided" : "needs_input",
    weighted_score: null,
  }));
  return {
    schema_version: "1.0",
    mode: "offline",
    language,
    source: { canon: "V7.0", stack: "E0 engineering extension", empirical_status: "not assessed" },
    approval: { required: true, status: "pending" },
    L1: {
      facts: facts.slice(0, 12),
      questions: questions.slice(0, 12),
      structure: parts.slice(0, 6).map((text, index) => ({ id: `N${index + 1}`, text })),
    },
    L2: {
      parameter_suggestions: zh ? ["时间范围", "信息压缩比", "反馈阈值"] : ["time horizon", "compression ratio", "feedback threshold"],
      note: zh ? "建议由用户选择可操作参数；本接口不执行代码。" : "Choose operable parameters; this interface does not execute code.",
    },
    L3: {
      direction: directionSignals.slice(0, 3),
      value: valueSignals.slice(0, 3),
      boundary: boundarySignals.slice(0, 3),
      spectrum: {
        placement: abstract ? (zh ? "偏抽象/长时距" : "abstract/long-horizon") : (zh ? "偏具体/短时距" : "concrete/short-horizon"),
        confidence: "heuristic",
        canonical_model: "continuous spectrum band",
      },
    },
    L4: {
      assigned_level: "E0",
      reason: zh ? "仅完成构念与结构化描述，未提供预注册检验数据。" : "Only construct definition and structured description are available; no preregistered test data were supplied.",
      falsification: zh ? "正式等级须依据预注册假设、样本、统计方案与独立复现逐项核验。" : "Formal levels require item-by-item verification of preregistration, sample, statistical plan and independent replication.",
    },
    L5: {
      scales,
      method: "conflict-and-priority review; weighted summation prohibited",
      conflicts: selectedScales.length > 1 ? [zh ? "跨尺度目标可能存在冲突，需人工排序。" : "Cross-scale goals may conflict and require human prioritization."] : [],
    },
    L6: {
      review_questions: zh ? ["哪些前提未被检验？", "什么反馈会触发重新校准？", "归零后保留什么？"] : ["Which premises remain untested?", "What feedback triggers recalibration?", "What should survive zeroing?"],
      revision_suggestions: [],
    },
    limitations: zh ? ["离线规则输出不是实证结论", "不替代领域专业判断", "所有行动需人类批准"] : ["Offline rule output is not empirical evidence", "Does not replace domain expertise", "All actions require human approval"],
  };
}

function review(input) {
  validateArguments(input, ["previous", "feedback", "language"], ["previous", "feedback"]);
  if (!isPlainObject(input.previous) || Object.keys(input.previous).length > 100) throw invalidArguments();
  if (typeof input.feedback !== "string" || !input.feedback.trim() || input.feedback.length > 4000) throw invalidArguments();
  if (!validLanguage(input.language)) throw invalidArguments();
  const language = languageOf(input.feedback, input.language);
  const zh = language === "zh";
  return {
    schema_version: "1.0",
    language,
    previous_received: true,
    feedback_summary: input.feedback.slice(0, 500),
    revision_suggestions: [
      zh ? "重新检查方向、价值与边界是否完整。" : "Recheck whether direction, value and boundary are complete.",
      zh ? "把新反馈作为待核验材料，不自动提升证据等级。" : "Treat new feedback as unverified material; do not automatically raise evidence level.",
      zh ? "若关键前提改变，建议触发一次预注册的归零复核。" : "If a key premise changes, consider a preregistered zeroing review.",
    ],
    evidence_level_changed: false,
    approval: { required: true, status: "pending" },
  };
}

async function downloadManifest(request, fetchImpl) {
  let target;
  try {
    const base = new URL(request.url);
    if ((base.protocol !== "https:" && base.protocol !== "http:") || base.username || base.password) throw new Error();
    target = new URL(MANIFEST_PATH, base.origin).href;
  } catch {
    throw new RpcError(-32003, "download manifest unavailable");
  }
  let response;
  try {
    response = await fetchImpl(target, {
      redirect: "manual",
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    throw new RpcError(-32003, "download manifest unavailable");
  }
  try {
    if (!response.ok || response.status >= 300) throw new Error();
    const bytes = await readLimitedBytes(response.body, MAX_MANIFEST_BYTES);
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!isPlainObject(value) || typeof value.version !== "string" || !Array.isArray(value.files) || value.files.length > 1000) throw new Error();
    return value;
  } catch {
    throw new RpcError(-32003, "download manifest unavailable");
  }
}

async function toolCall(name, args, request, fetchImpl) {
  if (name === "meaning_analyze") return analyze(args);
  if (name === "meaning_review") return review(args);
  if (name === "resource_catalog") {
    validateArguments(args, []);
    return { canon: CANON, resources: RESOURCES, tools: TOOLS.map((tool) => tool.name) };
  }
  if (name === "evidence_levels") {
    validateArguments(args, []);
    return { canon: "V7.0", levels: EVIDENCE.map(([id, zh, en]) => ({ id, zh, en })) };
  }
  if (name === "download_manifest") {
    validateArguments(args, []);
    return downloadManifest(request, fetchImpl);
  }
  throw new RpcError(-32602, "unknown tool");
}

async function handleRpc(message, request, fetchImpl) {
  const { id, method, params = {} } = message;
  if (method === "initialize") {
    return {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { resources: { subscribe: false, listChanged: false }, tools: { listChanged: false } },
      serverInfo: { name: "meaning-intelligence-web-mcp", version: "1.0.0" },
      instructions: "Read-only resources and deterministic analysis. Human approval is always required. / 只读资源与确定性分析；一切行动均需人类批准。",
    };
  }
  if (method === "ping") return {};
  if (method === "tools/list") return { tools: TOOLS };
  if (method === "resources/list") return { resources: RESOURCES };
  if (method === "resources/templates/list") return { resourceTemplates: [] };
  if (method === "resources/read") {
    const uri = params.uri;
    const factory = typeof uri === "string" ? RESOURCE_VALUES.get(uri) : null;
    if (!factory) throw new RpcError(-32002, "resource not found");
    const value = factory();
    return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify(value, null, 2) }] };
  }
  if (method === "tools/call") {
    if (typeof params.name !== "string" || (params.arguments !== undefined && !isPlainObject(params.arguments))) {
      throw new RpcError(-32602, "invalid tool arguments");
    }
    const result = await toolCall(params.name, params.arguments || {}, request, fetchImpl);
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      structuredContent: result,
      isError: false,
    };
  }
  throw new RpcError(-32601, "method not found");
}

function createRateLimiter({ now = Date.now, rateLimit = RATE_LIMIT, windowMs = RATE_WINDOW_MS, maxClients = MAX_RATE_CLIENTS } = {}) {
  const buckets = new Map();
  return (key) => {
    const current = now();
    const cutoff = current - windowMs;
    let bucket = buckets.get(key);
    if (!bucket) {
      for (const [candidate, timestamps] of buckets) {
        if (timestamps.length === 0 || timestamps[timestamps.length - 1] <= cutoff) buckets.delete(candidate);
      }
      if (buckets.size >= maxClients) return Math.ceil(windowMs / 1000);
      bucket = [];
      buckets.set(key, bucket);
    }
    while (bucket.length > 0 && bucket[0] <= cutoff) bucket.shift();
    if (bucket.length >= rateLimit) return Math.max(1, Math.ceil((bucket[0] + windowMs - current) / 1000));
    bucket.push(current);
    return 0;
  };
}

export function createHandler(options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch.bind(globalThis);
  const consumeRateLimit = createRateLimiter(options);

  return {
    async fetch(request, env = {}) {
      let rpcId = null;
      let cors = { allowed: true, headers: {} };
      try {
        cors = corsFor(request, env);
        if (request.method === "OPTIONS") {
          const retryAfter = consumeRateLimit(clientKey(request));
          if (retryAfter) return rpcError(null, -32000, "rate limit exceeded", 429, { ...cors.headers, "retry-after": String(retryAfter) });
          return preflight(request, cors);
        }
        if (request.method !== "POST") {
          throw new TransportError("method not allowed", 405, -32000, { allow: "POST, OPTIONS" });
        }
        if (!cors.allowed) throw new TransportError("origin not allowed", 403, -32000);
        const retryAfter = consumeRateLimit(clientKey(request));
        if (retryAfter) throw new TransportError("rate limit exceeded", 429, -32000, { "retry-after": String(retryAfter) });
        if (!authorized(request, env)) {
          throw new TransportError("unauthorized", 401, -32001, { "www-authenticate": "Bearer" });
        }
        const contentType = (request.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase();
        if (contentType !== "application/json") throw new TransportError("content-type must be application/json", 415);
        const message = validateMessage(await readJsonRequest(request));
        rpcId = Object.hasOwn(message, "id") ? message.id : null;
        if (!Object.hasOwn(message, "id")) {
          try {
            await handleRpc(message, request, fetchImpl);
          } catch {
            // JSON-RPC notifications never receive a response, including errors.
          }
          return empty(202, cors.headers);
        }
        const result = await handleRpc(message, request, fetchImpl);
        return json({ jsonrpc: "2.0", id: message.id, result }, 200, cors.headers);
      } catch (error) {
        if (error instanceof TransportError) {
          return rpcError(null, error.code, error.message, error.status, { ...cors.headers, ...error.headers });
        }
        if (error instanceof RpcError) return rpcError(rpcId, error.code, error.message, 200, cors.headers);
        return rpcError(rpcId, -32603, "internal error", 500, cors.headers);
      }
    },
  };
}

const worker = createHandler();
export const onRequest = context => worker.fetch(context.request, context.env);
export default worker;
