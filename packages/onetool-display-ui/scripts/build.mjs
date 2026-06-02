import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");
const outDir = resolve(root, "dist");
const assetPath = resolve(root, "../../src/ot/display/assets/index.html");

await mkdir(outDir, { recursive: true });
const result = await esbuild.build({
  entryPoints: [resolve(root, "src/main.tsx")],
  bundle: true,
  minify: true,
  sourcemap: false,
  write: false,
  outfile: resolve(outDir, "app.js"),
  format: "iife",
  target: "es2022",
  loader: { ".css": "css" },
});

const js = result.outputFiles.find((file) => file.path.endsWith(".js"))?.text ?? "";
const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text ?? "";
const htmlTemplate = await readFile(resolve(root, "src/index.html"), "utf8");
const html = htmlTemplate.replace(
  '  <script type="module" src="/src/main.tsx"></script>',
  () => `  <style>${escapeStyle(css)}</style>\n  <script>${escapeScript(js)}</script>`,
);

await writeFile(resolve(outDir, "index.html"), html);
await mkdir(dirname(assetPath), { recursive: true });
await writeFile(assetPath, html);

function escapeScript(value) {
  return value.replaceAll("</script", "<\\/script");
}

function escapeStyle(value) {
  return value.replaceAll("</style", "<\\/style");
}
