import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const htmlBypass = (req: { headers: { accept?: string } }) => {
  if (req.headers.accept?.includes('text/html')) {
    return '/index.html';
  }
};

const apiProxy = {
  target: 'http://localhost:8000',
  changeOrigin: true,
  bypass: htmlBypass,
};

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/auth': apiProxy,
      '/chat': apiProxy,
      '/memory': apiProxy,
      '/telemetry': apiProxy,
      '/assessments': apiProxy,
      '/documents': apiProxy,
      '/radiation': apiProxy,
      '/admin': apiProxy,
      '/simulator': apiProxy,
      '/health': apiProxy,
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
