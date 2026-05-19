import { defineConfig, createLogger } from 'vite';
import basicSsl from '@vitejs/plugin-basic-ssl';

const customLogger = createLogger();
const originalLoggerError = customLogger.error;
customLogger.error = (msg, options) => {
  if (msg.includes('ws proxy socket error') && msg.includes('ECONNRESET')) {
    return;
  }
  originalLoggerError(msg, options);
};

export default defineConfig({
  customLogger: customLogger,
  plugins: [
    basicSsl()
  ],
  server: {
    port: 5173,
    host: '0.0.0.0',
    https: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            // Suppress ECONNRESET noise from WS proxy reconnections
            if (err.message?.includes('ECONNRESET')) return;
            console.error('WS proxy error:', err.message);
          });
        }
      }
    }
  }
});
