import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['.ngrok-free.dev'],
    proxy: {
      '/auth': 'http://localhost:5000',
      '/api': 'http://localhost:5000',
      '/billing': 'http://localhost:5000',
      '/admin': 'http://localhost:5000',
      // Only the JSON/consent endpoints: bare /connect stays a React route
      '/connect/status': 'http://localhost:5000',
      '/connect/revoke': 'http://localhost:5000',
      '/connect/authorize': 'http://localhost:5000',
    },
  },
})
