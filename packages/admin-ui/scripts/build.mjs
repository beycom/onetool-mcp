import { spawnSync } from "node:child_process";
import { cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(import.meta.url), "../..");
const outDir = resolve(root, "dist");
const packageDistDir = resolve(root, "src/onetool_admin_ui/dist");

const vite = spawnSync("npx", ["vite", "build"], {
  cwd: root,
  stdio: "inherit",
});
if (vite.status !== 0) {
  process.exit(vite.status ?? 1);
}

await rm(packageDistDir, { recursive: true, force: true });
await mkdir(packageDistDir, { recursive: true });
await cp(outDir, packageDistDir, { recursive: true });
