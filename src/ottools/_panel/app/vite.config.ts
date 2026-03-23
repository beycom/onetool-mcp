import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const PANEL_PORT = env["VITE_PANEL_PORT"] ?? "7770";

  return {
    plugins: [react()],
    build: {
      outDir: "../dist",
      emptyOutDir: true,
    },
    define: {
      __PANEL_PORT__: JSON.stringify(PANEL_PORT),
    },
    server: {
      port: 5173,
      proxy: {
        "/ws": {
          target: `ws://localhost:${PANEL_PORT}`,
          ws: true,
        },
        "/file": {
          target: `http://localhost:${PANEL_PORT}`,
        },
      },
    },
  };
});
