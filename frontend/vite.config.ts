import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  server: {
    host: '127.0.0.1', strictPort: true,
    proxy: { '/api': mode === 'e2e' ? 'http://127.0.0.1:8011' : 'http://127.0.0.1:8000' },
    fs: {
      allow: [fileURLToPath(new URL('.', import.meta.url)),
        // Only explicit public evaluation fixtures are shared; keep backend/config and runtime private.
        fileURLToPath(new URL('../evals/writing/v0.1/case-01/web-fiction-test-profile.json', import.meta.url)),
        fileURLToPath(new URL('../evals/manual', import.meta.url))],
      deny: ['.env', '.env.*', '**/config.toml', '**/.runtime/**', '*.{crt,pem,key}'],
    },
  },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'], clearMocks: true },
}))
