import react from '@vitejs/plugin-react'
import { LikeC4VitePlugin } from 'likec4/vite-plugin'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

const dataPath = process.env.ONETOOL_ARCH_DATA
  ? resolve(process.env.ONETOOL_ARCH_DATA)
  : resolve(import.meta.dirname, 'src/data/sample-data.json')
const likec4Workspace = process.env.ONETOOL_LIKEC4_WORKSPACE
  ? resolve(process.env.ONETOOL_LIKEC4_WORKSPACE)
  : undefined

export default defineConfig({
  base: './',
  build: {
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    cssCodeSplit: false,
    modulePreload: false,
    outDir: 'dist',
    sourcemap: false,
  },
  plugins: [
    react(),
    {
      name: 'onetool-architecture-data',
      resolveId(id) {
        return id === 'virtual:onetool-data' ? '\0virtual:onetool-data' : undefined
      },
      load(id) {
        if (id !== '\0virtual:onetool-data') return undefined
        const payload = JSON.parse(readFileSync(dataPath, 'utf8')) as unknown
        return `export default ${JSON.stringify(payload)}`
      },
    },
    LikeC4VitePlugin({ graphviz: 'wasm', workspace: likec4Workspace }),
    viteSingleFile({ removeViteModuleLoader: true }),
  ],
})
