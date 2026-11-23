import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  envDir: '..',
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    env: { VITE_API_BASE_URL: 'http://localhost:8080/api/v1' },
    restoreMocks: true,
  },
})
