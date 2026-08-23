import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

function reportTemplate(): Plugin {
  return {
    enforce: 'post',
    generateBundle(_options, bundle) {
      const html = bundle['index.html']
      if (!html) throw new Error('Vite did not emit index.html')
      delete bundle['index.html']
      html.fileName = 'report-template.html'
      bundle[html.fileName] = html
    },
    name: 'arch-report-template-name',
  }
}

export default defineConfig({
  base: './',
  build: {
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    cssCodeSplit: false,
    emptyOutDir: true,
    outDir: fileURLToPath(new URL('../../src/otdev/tools/_arch/v3/_bundle', import.meta.url)),
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
  plugins: [react(), viteSingleFile(), reportTemplate()],
})
