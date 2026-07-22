import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['compat/**/*.test.ts', 'tests/**/*.test.ts'],
  },
})
