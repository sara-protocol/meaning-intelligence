import { access, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const source = resolve(scriptDirectory, "../functions/api/mcp.js");
const args = process.argv.slice(2);
const checkOnly = args.includes("--check");
const roots = args.filter((arg) => arg !== "--check");
if (roots.length > 1) {
  process.stderr.write("Usage: node scripts/sync-publication.mjs [--check] [publication-root]\n");
  process.exit(2);
}
const publicationRoot = roots[0]
  ? resolve(roots[0])
  : fileURLToPath(new URL("../../../意义智能有声读物_发布包/", import.meta.url));
const target = resolve(publicationRoot, "functions/api/mcp.js");

try {
  await access(dirname(target));
} catch {
  process.stderr.write("Publication functions/api directory is missing; no files were created.\n");
  process.exit(1);
}

const sourceBytes = await readFile(source);
let targetBytes;
try {
  targetBytes = await readFile(target);
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}

if (checkOnly) {
  if (!targetBytes || !sourceBytes.equals(targetBytes)) {
    process.stderr.write("Publication MCP copy differs from the tracked source; run npm run sync:publication.\n");
    process.exit(1);
  }
} else if (!targetBytes || !sourceBytes.equals(targetBytes)) {
  await writeFile(target, sourceBytes);
}

const hash = createHash("sha256").update(sourceBytes).digest("hex");
process.stdout.write(`${checkOnly ? "OK" : "Synced"} ${target}\nSHA-256 ${hash}\n`);
