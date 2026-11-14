import { defineConfig, loadEnv, type ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import type { ServerResponse } from 'http';

const htmlBypass = (req: { headers: { accept?: string | string[] } }) => {
  const accept = req.headers.accept;
  if (typeof accept === 'string' && accept.includes('text/html')) {
    return '/index.html';
  }
};

/**
 * Normalise the backend URL coming from the environment.
 *
 * Railway (and most dashboards) hand out a bare host such as
 * "my-service.up.railway.app". `http-proxy` requires an explicit protocol:
 * without one it throws `Cannot read properties of null (reading 'split')`
 * and the unhandled error kills the whole preview process.
 */
function normaliseApiTarget(raw: string | undefined, fallback: string): string {
  const value = (raw ?? '').trim().replace(/\/+$/, '');
  if (!value || value.startsWith('/')) return fallback;
  if (/^https?:\/\//i.test(value)) return value;
  // A ws(s):// target is meaningless for the HTTP proxy, but users sometimes paste it.
  if (/^wss?:\/\//i.test(value)) return value.replace(/^ws/i, 'http');
  // Protocol-relative value such as "//host".
  if (value.startsWith('//')) return `https:${value}`;

  const isLocal = /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:\d+)?$/i.test(value);
  return `${isLocal ? 'http' : 'https'}://${value}`;
}

/** Keep a proxy failure from taking down the web server. */
function handleProxyError(target: string) {
  return (proxy: { on: (event: string, cb: (...args: any[]) => void) => void }) => {
    proxy.on('error', (err: Error, _req: unknown, res: unknown) => {
      console.error(`[trustline] proxy error -> ${target}: ${err.message}`);
      const response = res as ServerResponse | undefined;
      if (response && typeof response.writeHead === 'function' && !response.headersSent) {
        response.writeHead(502, { 'Content-Type': 'application/json' });
        response.end(
          JSON.stringify({ detail: 'Backend service is unreachable. Check the VITE_API_URL setting.' })
        );
      }
    });
  };
}

export default defineConfig(({ mode }) => {
  // Read VITE_* variables from .env files and from real process env (Railway).
  const env = loadEnv(mode, process.cwd(), 'VITE_');

  // Backend URL. Always normalised to an absolute http(s) URL so the proxy
  // never receives a scheme-less target.
  const API_TARGET = normaliseApiTarget(
    env.VITE_API_URL || process.env.VITE_API_URL,
    'http://localhost:8000'
  );
  const WS_TARGET = API_TARGET.replace(/^http/i, 'ws');

  console.log(`[trustline] API proxy target: ${API_TARGET}`);
  console.log(`[trustline] WS  proxy target: ${WS_TARGET}`);

  const apiProxy: ProxyOptions = {
    target: API_TARGET,
    changeOrigin: true,
    secure: true,
    bypass: htmlBypass,
    configure: handleProxyError(API_TARGET),
  };

  const wsProxy: ProxyOptions = {
    target: WS_TARGET,
    ws: true,
    changeOrigin: true,
    configure: handleProxyError(WS_TARGET),
  };

  const proxy = {
    '/auth': apiProxy,
    '/chat': apiProxy,
    '/memory': apiProxy,
    '/telemetry': apiProxy,
    '/assessments': apiProxy,
    '/documents': apiProxy,
    '/radiation': apiProxy,
    '/admin': apiProxy,
    '/simulator': apiProxy,
    '/supabase': apiProxy,
    '/ai': apiProxy,
    '/health': apiProxy,
    '/ws': wsProxy,
  };

  const port = Number(process.env.PORT) || 3000;
  const previewPort = Number(process.env.PORT) || 8080;

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port,
      allowedHosts: [
        'trustline-production-c57addcb.up.railway.app',
        true, // Allows all external hosts (handy for dynamic preview URLs)
      ],
      proxy,
    },
    // `vite preview` does not read `server.*` for host/port, so mirror the
    // settings here. (preview.proxy would default to server.proxy, but being
    // explicit keeps the production server self-documenting.)
    preview: {
      host: '0.0.0.0',
      port: previewPort,
      allowedHosts: [
        'trustline-production-c57addcb.up.railway.app',
        true,
      ],
      proxy,
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  };
});
