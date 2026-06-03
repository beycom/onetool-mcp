import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");
const outDir = resolve(root, "dist");
const assetPath = resolve(root, "../../src/ot/display/assets/index.html");

const vite = spawnSync("npx", ["vite", "build"], {
  cwd: root,
  stdio: "inherit",
});
if (vite.status !== 0) {
  process.exit(vite.status ?? 1);
}

const builtHtml = await readFile(resolve(outDir, "index.html"), "utf8");
const scriptMatches = [...builtHtml.matchAll(/<script[^>]+src="([^"]+)"[^>]*><\/script>/g)];
const styleMatches = [...builtHtml.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>/g)];
let html = builtHtml;

for (const match of styleMatches) {
  const href = match[1].replace(/^\//, "");
  const css = await readFile(resolve(outDir, href), "utf8");
  const escaped = escapeStyle(css);
  assertNoRawTextTerminator(escaped, "style");
  html = html.replace(match[0], () => `<style>${escaped}</style>`);
}

for (const match of scriptMatches) {
  const src = match[1].replace(/^\//, "");
  const js = await readFile(resolve(outDir, src), "utf8");
  const escaped = escapeScript(js);
  assertNoRawTextTerminator(escaped, "script");
  html = html.replace(match[0], () => `<script type="module">${escaped}</script>`);
}

await writeFile(resolve(outDir, "index.html"), html);
await mkdir(dirname(assetPath), { recursive: true });
await writeFile(assetPath, html);

function escapeScript(value) {
  return value.replace(/<\/script/gi, "<\\/script");
}

function escapeStyle(value) {
  return value.replace(/<\/style/gi, "<\\/style");
}

function assertNoRawTextTerminator(value, tagName) {
  const pattern = new RegExp(`</${tagName}`, "i");
  if (pattern.test(value)) {
    throw new Error(`Inlined ${tagName} asset still contains a raw </${tagName}> terminator.`);
  }
}
