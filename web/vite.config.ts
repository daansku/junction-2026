import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '..')

// VITE_API: "mock" (reads ../data/fixtures), "local" (http://localhost:8000/api),
// or a full base URL such as https://xyz.trycloudflare.com/api.
// Unset: dev → mock, build → same-origin /api.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(here, 'src'),
    },
  },
  server: {
    port: 5173,
    fs: { allow: [repoRoot] },
  },
})
