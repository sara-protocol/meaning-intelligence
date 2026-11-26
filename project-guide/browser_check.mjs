import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, stat, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const target = path.resolve(process.argv[2] || path.dirname(fileURLToPath(import.meta.url)));
const mime = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".mp3": "audio/mpeg", ".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png", ".vtt": "text/vtt; charset=utf-8", ".srt": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pdf": "application/pdf", ".epub": "application/epub+zip", ".zip": "application/zip", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation" };
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    const relative = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
    const file = path.resolve(target, relative);
    if (file !== target && !file.startsWith(target + path.sep)) { response.writeHead(403); response.end("Forbidden"); return; }
    const info = await stat(file);
    if (!info.isFile()) { response.writeHead(404); response.end("Not found"); return; }
    const type = mime[path.extname(file).toLowerCase()] || "application/octet-stream";
    const range = request.headers.range;
    if (range) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      if (!match) { response.writeHead(416); response.end(); return; }
      const start = Number(match[1]);
      const end = match[2] ? Math.min(Number(match[2]), info.size - 1) : info.size - 1;
      if (start > end || start >= info.size) { response.writeHead(416, { "Content-Range": `bytes */${info.size}` }); response.end(); return; }
      response.writeHead(206, { "Content-Type": type, "Content-Length": end - start + 1, "Content-Range": `bytes ${start}-${end}/${info.size}`, "Accept-Ranges": "bytes", "Cache-Control": "no-store" });
      const { createReadStream } = await import("node:fs");
      createReadStream(file, { start, end }).pipe(response);
    } else {
      response.writeHead(200, { "Content-Type": type, "Content-Length": info.size, "Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
      response.end(await readFile(file));
    }
  } catch (_) { response.writeHead(404); response.end("Not found"); }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

async function chromePath() {
  const candidates = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].filter(Boolean);
  for (const candidate of candidates) { try { await stat(candidate); return candidate; } catch (_) {} }
  throw new Error("Chrome or Edge was not found.");
}
const executable = await chromePath();
function decodeHtml(value) {
  return value.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}
function launch(browser, url, profile, mobile = false) {
  return new Promise((resolve, reject) => {
    const viewport = mobile ? "--window-size=390,844" : "--window-size=1365,900";
    const args = ["--headless=new", "--disable-gpu", "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required", "--virtual-time-budget=25000", "--dump-dom", viewport, `--user-data-dir=${profile}`, url];
    const child = spawn(browser, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => { child.kill(); reject(new Error("Browser check timed out.")); }, 60000);
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => { clearTimeout(timer); reject(error); });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0 && !stdout.includes("selftest-results")) { reject(new Error(`Browser exited ${code}: ${stderr.slice(-2000)}`)); return; }
      const match = /<pre[^>]*id="selftest-results"[^>]*>([\s\S]*?)<\/pre>/.exec(stdout);
      if (!match) { reject(new Error(`No browser self-test payload. stderr: ${stderr.slice(-2000)}`)); return; }
      try { resolve(JSON.parse(decodeHtml(match[1]))); } catch (error) { reject(new Error(`Invalid browser self-test JSON: ${error.message}`)); }
    });
  });
}

const results = [];
try {
  for (const mode of ["http", "file"]) {
    const profile = path.join(target, `.browser-profile-${mode}`);
    await rm(profile, { recursive: true, force: true });
    const url = mode === "http" ? `http://127.0.0.1:${port}/index.html?selftest=1` : pathToFileURL(path.join(target, "index.html")).href + "?selftest=1";
    const result = await launch(executable, url, profile, mode === "file");
    results.push(result);
    await rm(profile, { recursive: true, force: true });
  }
} finally {
  await new Promise((resolve) => server.close(resolve));
}
const report = {
  schema: "meaning-intelligence-browser-check-v1",
  ok: results.length === 2 && results.every((result) => result.ok),
  engine: path.basename(executable),
  modes: results,
  checks_total: results.reduce((sum, result) => sum + result.checks.length, 0),
  checks_passed: results.reduce((sum, result) => sum + result.checks.filter((check) => check.ok).length, 0),
  pending: ["Human keyboard, screen-reader, visual mobile, print, and rights review."]
};
await writeFile(path.join(target, "browser-check.json"), JSON.stringify(report, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ ok: report.ok, checks_passed: report.checks_passed, checks_total: report.checks_total, modes: results.map((result) => ({ mode: result.mode, ok: result.ok })) }, null, 2));
if (!report.ok) process.exitCode = 1;
