import process from 'node:process'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig(() => {
  const apiTarget =
    process.env.SENTINEL_API_PROXY_TARGET ?? 'http://127.0.0.1:18000'
  const proxy = { '/api': { target: apiTarget, changeOrigin: false } }

  return {
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.js',
    },
  }
})
