import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 4000,
        strictPort: true,
        proxy: {
            // REST API — avoids CORS in dev; requests to /api/... → http://localhost:8000/api/...
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            // WebSocket — proxied so ws://localhost:5173/ws/... → ws://localhost:8000/ws/...
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
            },
        },
    },
})
