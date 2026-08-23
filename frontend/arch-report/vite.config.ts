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
      if (html.type !== 'asset') throw new Error('Vite emitted index.html as a chunk')
      delete bundle['index.html']
      this.emitFile({
        fileName: 'report-template.html',
        source: String(html.source).replace(/[ \t]+$/gm, ''),
        type: 'asset',
      })
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
  },
  plugins: [react(), viteSingleFile(), reportTemplate()],
})
