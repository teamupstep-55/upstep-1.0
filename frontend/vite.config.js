import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, /api calls are forwarded to the Flask server, so no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', testTimeout: 20000 },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:5001' } },
})
