import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
          if (id.includes('@vue') || id.includes('vue') || id.includes('pinia')) return 'vue-vendor'
          if (id.includes('axios')) return 'http-vendor'
          return 'vendor'
        }
      }
    }
  },
  server: {
    port: 5188,
    strictPort: true
  }
})
