import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  define: {
    // Cesium's static assets are copied to public/cesium by scripts/copy-cesium.mjs.
    CESIUM_BASE_URL: JSON.stringify('/cesium'),
  },
  plugins: [react()],
})
