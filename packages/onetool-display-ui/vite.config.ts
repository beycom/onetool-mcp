import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 16000,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        codeSplitting: false,
      },
    },
  },
});
