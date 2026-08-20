import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// 从 package.json 读取版本号，注入为全局常量
import { version } from './package.json'

export default defineConfig({
  base: '/',
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-naive': ['naive-ui'],
          'vendor-codemirror': [
            '@codemirror/state',
            '@codemirror/view',
            '@codemirror/commands',
            '@codemirror/language',
            '@codemirror/lang-cpp',
            '@lezer/highlight',
          ],
          'vendor-vue': ['vue', 'lucide-vue-next'],
        },
      },
    },
  },
})
