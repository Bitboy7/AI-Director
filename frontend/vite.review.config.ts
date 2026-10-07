import { defineConfig } from 'vitest/config'
import baseConfig from './vite.config'

export default defineConfig({
  ...baseConfig,
  server: {
    ...baseConfig.server,
    port: 5174,
    proxy: {
      '/api': 'http://localhost:8001',
    },
  },
})