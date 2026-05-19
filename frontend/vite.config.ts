import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    // AutoDL 公网映射：实例内 6006 → 控制台给出的 https 地址
    host: '0.0.0.0',
    port: 6006,
    strictPort: true,
    allowedHosts: [
      'u781269-86b2-5cbc01bf.westc.seetacloud.com',
      'uu781269-86b2-5cbc01bf.westc.seetacloud.com',
      '.seetacloud.com',
    ],
    proxy: {
      '/api': {
        // 后端监听 6008（AutoDL 第二路公网映射，也可仅通过前端 /api 代理访问）
        target: 'http://127.0.0.1:6008',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
