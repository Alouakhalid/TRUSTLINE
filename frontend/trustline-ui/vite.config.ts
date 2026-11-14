import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const htmlBypass = (req) => {
  if (req.headers.accept?.includes('text/html')) {
    return '/index.html';
  }
};

export default defineConfig(({ mode }) => {
  // Read VITE_* variables from .env files and from real process env (Railway).
  const env = loadEnv(mode, process.cwd(), 'VITE_');

  // Use environment variable for backend URL if provided (for Railway deployment), fallback to localhost for dev
  const API_TARGET = env.VITE_API_URL || process.env.VITE_API_URL || 'http://localhost:8000';
  const WS_TARGET = API_TARGET.replace(/^http/, 'ws');

  const apiProxy = {
    target: API_TARGET,
    changeOrigin: true,
    bypass: htmlBypass,
  };

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: process.env.PORT || 3000,
      allowedHosts: [
        'trustline-production-c57addcb.up.railway.app',
        true, // Allows all external hosts (handy for dynamic preview URLs)
      ],
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
          target: WS_TARGET,
          ws: true,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  };
});
