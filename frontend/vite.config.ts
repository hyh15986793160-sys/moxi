import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const API_TARGET = 'http://127.0.0.1:8011'

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  // 线上是「一个域名 + 子路径」：导航页在 /，这个游戏在 /moxi/。
  // 开发服务器仍然挂在根路径，本地不用每次都输 /moxi/。
  base: command === 'build' ? '/moxi/' : '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    // 与同机的 xiangq（6660）错开，两个 dev server 可以同时开。
    port: 6670,
    strictPort: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 6670,
    strictPort: true,
    // 预览构建产物时也要能打到本地后端，否则只能看静态壳子。
    // 产物里的接口前缀是 /moxi/api，转发时去掉前缀还原成 /api。
    proxy: {
      '/moxi/api': {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/moxi\/api/, '/api'),
      },
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
}))
