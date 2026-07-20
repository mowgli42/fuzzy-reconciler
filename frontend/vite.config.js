import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/demo': 'http://127.0.0.1:8010',
      '/compare': 'http://127.0.0.1:8010',
      '/ingest': 'http://127.0.0.1:8010',
      '/presets': 'http://127.0.0.1:8010',
      '/health': 'http://127.0.0.1:8010',
    },
  },
})
