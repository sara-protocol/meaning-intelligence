import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { extname, isAbsolute, join, relative, resolve, sep, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export function parseArgs(argv) {
  const online = argv.includes('--online');
  const deployment = argv.includes('--deployment');
  const positional = argv.filter(value => !['--online', '--deployment'].includes(value));
  const unknown = positional.find(value => value.startsWith('--'));
  if (unknown) throw new Error(`Unknown option: ${unknown}`);
  if (online && deployment) throw new Error('--online and --deployment cannot be used together');
  if (online && !positional[0]) throw new Error('Online mode requires a site URL');
  if (deployment && !positional[0]) throw new Error('Deployment mode requires a staging directory');
  return { online, deployment, root: positional[0], output: positional[1] };
}

export async function findExecutable(candidates) {
  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) return candidate;
    } catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error;
    }
  }
  return null;
}

const invokedDirectly = Boolean(process.argv[1]) && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
const options = invokedDirectly ? parseArgs(process.argv.slice(2)) : { online: false };
const online = options.online;
const deploymentMode = online || Boolean(options.deployment);
const defaultRoot = fileURLToPath(new URL('../../意义智能有声读物_发布包/', import.meta.url));
const root = online ? defaultRoot : resolve(options.root || defaultRoot);
const output = resolve(options.output || fileURLToPath(new URL('../../deliverables/publication-browser-check.json', import.meta.url)));
const base = online ? options.root.replace(/\/$/, '') : '';
if (online && !/^https?:\/\//i.test(base)) throw new Error('Online site URL must use HTTP or HTTPS');
const checks = [];
const consoleErrors = [];
let chrome;
let server;
let profile;

function check(name, ok, detail = '') {
  checks.push({ name, ok: Boolean(ok), detail: String(detail).slice(0, 1200) });
  if (!ok) console.error(`FAIL ${name}: ${detail}`);
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.vtt': 'text/vtt; charset=utf-8',
  '.srt': 'application/x-subrip; charset=utf-8', '.pdf': 'application/pdf',
};
const safePath = value => {
  try {
    const path = resolve(root, `.${decodeURIComponent(new URL(value, 'http://local').pathname)}`);
    const rel = relative(root, path);
    if (!rel) return join(root, 'index.html');
    return !rel.startsWith(`..${sep}`) && rel !== '..' && !isAbsolute(rel) ? path : null;
  } catch {
    return null;
  }
};

async function startServer() {
  server = createServer(async (request, response) => {
    if (new URL(request.url, 'http://local').pathname === '/api/mcp') {
      response.writeHead(404, { 'content-type': 'application/json; charset=utf-8' });
      response.end(JSON.stringify({ error: 'Local static-preview server does not execute Pages Functions.' }));
      return;
    }
    const path = safePath(request.url);
    if (!path) { response.writeHead(403); response.end(); return; }
    try {
      const info = await stat(path);
      if (!info.isFile()) throw new Error('Not a file');
      const headers = { 'content-type': mime[extname(path).toLowerCase()] || 'application/octet-stream', 'accept-ranges': 'bytes' };
      const range = request.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
      if (range) {
        const start = Number(range[1]);
        const end = range[2] ? Math.min(Number(range[2]), info.size - 1) : info.size - 1;
        response.writeHead(206, { ...headers, 'content-range': `bytes ${start}-${end}/${info.size}`, 'content-length': end - start + 1 });
        if (request.method === 'HEAD') response.end();
        else createReadStream(path, { start, end }).pipe(response);
      } else {
        response.writeHead(200, { ...headers, 'content-length': info.size });
        if (request.method === 'HEAD') response.end();
        else createReadStream(path).pipe(response);
      }
    } catch {
      response.writeHead(404); response.end('Not found');
    }
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  return `http://127.0.0.1:${server.address().port}`;
}

async function launchChrome() {
  const executable = await findExecutable([
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ]);
  if (!executable) throw new Error('Chrome or Edge executable not found');
  profile = await mkdtemp(join(tmpdir(), 'mi-publication-chrome-'));
  chrome = spawn(executable, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
  ], { stdio: 'ignore' });
  let port;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      port = Number((await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split(/\r?\n/)[0]);
      if (port) break;
    } catch {}
    await pause(100);
  }
  if (!port) throw new Error('Browser DevTools port was not created');
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find(target => target.type === 'page');
  if (!page) throw new Error('Browser page target was not created');
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  let sequence = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve: done, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else done(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') consoleErrors.push(message.params.exceptionDetails.text);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  await send('Page.enable');
  await send('Runtime.enable');
  return { send, socket };
}

async function main() {
  let socket;
  let activeUrl = base;
  let fatalError = '';
  try {
    const url = online ? base : await startServer();
    activeUrl = url;
    const launched = await launchChrome();
    socket = launched.socket;
    const { send } = launched;
    const evaluate = async expression => {
      const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
      return result.result.value;
    };
    const navigate = async path => {
      await send('Page.navigate', { url: `${url}${path}` });
      for (let attempt = 0; attempt < 150; attempt += 1) {
        if (await evaluate('document.readyState === "complete" && Boolean(document.querySelector("h1,h2"))')) return;
        await pause(100);
      }
      throw new Error(`Page did not become ready: ${path}`);
    };
    const waitFor = async (expression, timeout = 15000) => {
      const started = Date.now();
      while (Date.now() - started < timeout) {
        if (await evaluate(expression)) return true;
        await pause(100);
      }
      return false;
    };
    const click = async selector => evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); if (!element) return false; element.click(); return true; })()`);

    let publicationReady = true;
    for (const page of ['index.html', 'listen.html']) {
      await navigate(`/${page}`);
      const title = await evaluate('document.title');
      const loaded = await evaluate('document.title.includes("意义智能") && document.querySelectorAll("#chapters button").length === 7');
      check(`${page}-loaded`, loaded, title);
      if (!loaded) {
        const visibleText = await evaluate('document.body?.innerText?.slice(0, 800) || ""');
        check(`${page}-publication-structure`, false, visibleText);
        publicationReady = false;
        break;
      }
      await click('#btnEn');
      await waitFor('document.documentElement.classList.contains("en")');
      check(`${page}-english`, await evaluate('Boolean(document.querySelector("#c1")) && document.querySelector("#c1").textContent.toLowerCase().includes("why") && Boolean(document.querySelector("#audio")) && document.querySelector("#audio").src.includes("assets_en/audio_en.mp3")'), await evaluate('document.querySelector("#audio")?.src || "missing audio element"'));
      const metadata = await waitFor('Boolean(document.querySelector("#audio")) && Number.isFinite(document.querySelector("#audio").duration) && document.querySelector("#audio").duration > 120');
      check(`${page}-english-audio`, metadata, metadata ? await evaluate('document.querySelector("#audio").duration') : 'metadata timeout');
      await click('#btnZh');
      check(`${page}-chinese`, await evaluate('!document.documentElement.classList.contains("en") && Boolean(document.querySelector("#audio")) && document.querySelector("#audio").src.includes("assets/audio-web.mp3")'), await evaluate('document.querySelector("#audio")?.src || "missing audio element"'));
      await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
      await pause(300);
      const overflow = await evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth');
      check(`${page}-mobile`, overflow <= 2, `horizontal overflow ${overflow}px`);
      await send('Emulation.clearDeviceMetricsOverride');
    }

    if (publicationReady) {
      await navigate('/downloads.html');
      const resourceCount = await evaluate('document.querySelectorAll(".download").length');
      check('downloads-resources', resourceCount >= 30, `${resourceCount} resource cards`);
      await click('#btnEn');
      check('downloads-english', await evaluate('document.documentElement.classList.contains("en") && Boolean(document.querySelector("h1")) && document.querySelector("h1").textContent.includes("Downloads")'), await evaluate('document.querySelector("h1")?.textContent || "missing heading"'));
      const firstDownload = await evaluate('document.querySelector(".download a")?.getAttribute("href") || ""');
      if (!firstDownload) throw new Error('Downloads page has no downloadable resource link');
      const response = await fetch(`${url}/${firstDownload}`, { headers: { range: 'bytes=0-1023' } });
      const contentRange = response.headers.get('content-range') || '';
      check('download-range-request', response.status === 206 && /^bytes 0-\d+\/\d+$/.test(contentRange), `${response.status}; ${contentRange}; ${response.headers.get('content-type')}`);
      await response.body?.cancel();
      const manifest = await fetch(`${url}/download/manifest.json`).then(value => value.json());
      const files = Array.isArray(manifest.files) ? manifest.files : [];
      const withinLimit = files.every(item => Number.isSafeInteger(item.bytes) && item.bytes > 0 && item.bytes <= 25 * 1024 * 1024);
      const derivatives = ['assets/audio-web.mp3', 'assets/video/release/meaning_intelligence_zh-web.mp4', 'assets/video/release/meaning_intelligence_en-web.mp4'];
      const hasDerivatives = derivatives.every(path => files.some(item => item.path === path));
      const hasCompletePackage = files.some(item => item.category === 'package');
      check('download-manifest', files.length >= 30 && hasDerivatives && (!deploymentMode || withinLimit), `${files.length} entries; complete_category=${hasCompletePackage}; max_limit_ok=${withinLimit}; mode=${deploymentMode ? 'deployment' : 'local'}`);
      const packageBoundaryOk = deploymentMode
        ? !hasCompletePackage && await evaluate('!document.body.textContent.includes("完整交付包") && !document.body.textContent.toLowerCase().includes("complete delivery package")')
        : hasCompletePackage && await evaluate('document.body.textContent.includes("完整交付包") || document.body.textContent.toLowerCase().includes("complete delivery package")');
      check('download-package-boundary', packageBoundaryOk, deploymentMode ? 'deployment manifest and cards exclude the complete package' : 'local manifest and cards include the complete package');
      const downloadHrefs = await evaluate('Array.from(document.querySelectorAll(".download a"), element => element.getAttribute("href"))');
      check('downloads-web-media-links', derivatives.every(path => downloadHrefs.includes(path)), JSON.stringify(downloadHrefs.filter(href => href.includes('-web'))));

      await navigate('/mcp.html');
      await click('#lang-en');
      check('mcp-english', await evaluate('document.documentElement.lang === "en" && Boolean(document.querySelector("#status")) && document.querySelector("#status").textContent.toLowerCase().includes("not connected")'), await evaluate('document.querySelector("#status")?.textContent || "missing status"'));
      await click('#connect');
      const handled = await waitFor('Boolean(document.querySelector("#status")) && document.querySelector("#status").textContent.trim().length > 0');
      check('mcp-empty-token-safe', handled && await evaluate('Boolean(document.querySelector("#output")) && document.querySelector("#output").textContent.length < 2000'), await evaluate('document.querySelector("#status")?.textContent || "missing status"'));
      check('mcp-no-token-storage', await evaluate('Object.keys(localStorage).length === 0 && Object.keys(sessionStorage).length === 0 && document.cookie === ""'), 'localStorage/sessionStorage/cookie');
      check('mcp-read-only-copy', await evaluate('document.body.textContent.includes("does not") || document.body.textContent.includes("read-only")'), 'read-only boundary copy');

      await navigate('/project-guide/index.html');
      check('packaged-guide-loaded', await evaluate('document.title.length > 0 && Boolean(window.GUIDE_CONTENT) && Array.isArray(window.GUIDE_CONTENT.chapters)'), await evaluate('document.title'));
      const guideEvidence = await evaluate('({ verification: window.GUIDE_VERIFICATION, chapters: window.GUIDE_CONTENT?.chapters?.length })');
      check('packaged-guide-evidence', guideEvidence.chapters === 18 && guideEvidence.verification?.build_complete === true, JSON.stringify(guideEvidence));
    }

    check('no-runtime-exceptions', consoleErrors.length === 0, consoleErrors.join(' | '));
    check('browser-run-completed', true, 'all applicable checks executed');
  } catch (error) {
    fatalError = error instanceof Error ? error.stack || error.message : String(error);
    check('browser-run-completed', false, fatalError);
  } finally {
    socket?.close();
  }
  const report = {
    schema: 'meaning-intelligence-publication-browser-check-v1',
    generated: new Date().toISOString(), base_url: activeUrl, engine: online ? 'remote-chrome-cdp' : deploymentMode ? 'chrome-cdp-deployment-preview' : 'chrome-cdp-static-preview',
    ok: checks.every(item => item.ok), checks_passed: checks.filter(item => item.ok).length,
    checks_total: checks.length, failed: checks.filter(item => !item.ok), fatal_error: fatalError || null, checks,
  };
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(report, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({ ok: report.ok, checks_passed: report.checks_passed, checks_total: report.checks_total, failed: report.failed, output }, null, 2));
  if (!report.ok) process.exitCode = 1;
}

if (invokedDirectly) {
  try {
    await main();
  } finally {
    if (server) await new Promise(resolve => server.close(resolve));
    chrome?.kill();
    if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 }).catch(() => {});
  }
}
