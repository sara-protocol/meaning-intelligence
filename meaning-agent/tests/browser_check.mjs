import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const url = process.argv[2] || "http://127.0.0.1:8766/";
const reportPath = path.resolve(process.argv[3] || path.join(directory, "../../../deliverables/agent-browser-check.json"));
const screenshotPath = process.argv[4] ? path.resolve(process.argv[4]) : null;
const checks = [];
const check = (name, ok, detail = "") => checks.push({ name, ok: Boolean(ok), detail });
const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function chromePath() {
  const candidates = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].filter(Boolean);
  for (const candidate of candidates) {
    try { await import("node:fs/promises").then(({ access }) => access(candidate)); return candidate; } catch {}
  }
  throw new Error("Chrome or Edge was not found.");
}

const executable = await chromePath();
const profile = await mkdtemp(path.join(tmpdir(), "meaning-agent-browser-"));
const browser = spawn(executable, [
  "--headless=new", "--disable-gpu", "--disable-dev-shm-usage", "--no-first-run",
  "--no-default-browser-check", "--disable-background-networking", "--remote-debugging-port=0",
  `--user-data-dir=${profile}`, "about:blank",
], { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });

let socket;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let output = "";
    const timer = setTimeout(() => reject(new Error("Chrome DevTools startup timed out.")), 20000);
    browser.stderr.setEncoding("utf8");
    browser.stderr.on("data", (chunk) => {
      output += chunk;
      const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(output);
      if (match) { clearTimeout(timer); resolve(match[1]); }
    });
    browser.on("error", (error) => { clearTimeout(timer); reject(error); });
    browser.on("exit", (code) => { clearTimeout(timer); reject(new Error(`Chrome exited ${code}: ${output.slice(-1000)}`)); });
  });
  const port = new URL(endpoint).port;
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find((target) => target.type === "page");
  if (!page) throw new Error("No Chrome page target was available.");
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let sequence = 0;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || "Browser evaluation failed.");
    return result.result.value;
  };
  const waitFor = async (expression, label) => {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate(expression)) return;
      await pause(100);
    }
    throw new Error(`Timed out waiting for ${label}.`);
  };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url });
  await waitFor("document.readyState === 'complete' && !!document.getElementById('lang-en') && document.getElementById('engine-mode').textContent.includes('离线')", "agent UI");
  check("initial-chinese-ui", await evaluate("document.documentElement.lang === 'zh-CN' && document.getElementById('run-button').textContent.includes('运行分析')"));

  await evaluate("document.getElementById('lang-en').click()");
  check("english-ui-switch", await evaluate("document.documentElement.lang === 'en' && document.getElementById('run-button').textContent.includes('Run analysis') && document.getElementById('lang-en').getAttribute('aria-pressed') === 'true'"));
  await evaluate("document.getElementById('text').value = 'One idea.'; document.getElementById('text').dispatchEvent(new Event('input')); document.getElementById('analysis-form').requestSubmit()");
  await waitFor("!document.getElementById('result-content').hidden", "analysis result");
  const result = await evaluate("JSON.parse(document.getElementById('raw-json').textContent)");
  check("six-skills-returned", result.skills && !Array.isArray(result.skills) && Object.keys(result.skills).sort().join(",") === "L1,L2,L3,L4,L5,L6", Object.keys(result.skills || {}).join(","));
  check("approval-pending", result.approval_gate?.status === "pending" && result.approval_gate?.execution_authorized === false && result.skills?.L6?.data?.automatic_execution === false, JSON.stringify(result.approval_gate));
  const clarification = await evaluate("Array.from(document.querySelectorAll('#clarification-list li')).map((node) => node.textContent)");
  check("english-clarifications", clarification.length > 0 && clarification.every((text) => !/\p{Script=Han}/u.test(text)), clarification.join(" | "));

  await evaluate("document.getElementById('lang-zh').click()");
  const chineseClarification = await evaluate("Array.from(document.querySelectorAll('#clarification-list li')).map((node) => node.textContent)");
  check("chinese-clarifications", chineseClarification.length > 0 && chineseClarification.some((text) => /\p{Script=Han}/u.test(text)), chineseClarification.join(" | "));
  await evaluate("document.getElementById('lang-en').click(); document.getElementById('sample-button').click(); document.getElementById('analysis-form').requestSubmit()");
  await waitFor("document.getElementById('raw-json').textContent.includes('合成演示文本')", "sample analysis");
  check("sample-analysis-rendered", await evaluate("!document.getElementById('result-content').hidden && !document.body.textContent.includes('[object Object]')"));
  await evaluate("document.querySelector('[data-tab=evidence]').click()");
  check("evidence-tab", await evaluate("!document.getElementById('tab-evidence').hidden && document.querySelectorAll('#evidence-table tr').length === 7"));

  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await pause(300);
  check("mobile-no-horizontal-overflow", await evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), await evaluate("JSON.stringify({scroll:document.documentElement.scrollWidth,viewport:window.innerWidth})"));
  check("mobile-language-controls", await evaluate("['lang-zh','lang-en','run-button'].every((id) => { const node = document.getElementById(id); const box = node.getBoundingClientRect(); return box.width > 0 && box.height > 0; })"));
  if (screenshotPath) {
    const capture = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    await writeFile(screenshotPath, Buffer.from(capture.data, "base64"));
  }

  const report = {
    schema: "meaning-agent-browser-check-v1", ok: checks.every((item) => item.ok), url,
    engine: path.basename(executable), checks_total: checks.length,
    checks_passed: checks.filter((item) => item.ok).length, checks,
    pending: ["Human screen-reader, keyboard, visual, and content review."],
  };
  await writeFile(reportPath, JSON.stringify(report, null, 2) + "\n", "utf8");
  console.log(JSON.stringify({ ok: report.ok, checks_passed: report.checks_passed, checks_total: report.checks_total, failed: checks.filter((item) => !item.ok) }, null, 2));
  if (!report.ok) process.exitCode = 1;
} finally {
  if (socket) socket.close();
  browser.kill();
  await pause(300);
  await rm(profile, { recursive: true, force: true });
}
