import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/",
  server: {
    proxy: {
      "/api/admin": "http://127.0.0.1:8760",
    },
  },
  build: {
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 900,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("react-markdown") || id.includes("remark-gfm")) return "rendererMarkdown";
          if (id.includes("mermaid") || id.includes("dompurify")) return "rendererMermaid";
          if (id.includes("/yaml/")) return "rendererStructured";
          if (id.includes("@tanstack/react-table")) return "rendererTable";
          if (id.includes("@pierre/diffs")) return "rendererDiffCode";
          return undefined;
        },
      },
    },
  },
});
