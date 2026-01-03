import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:3001',
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      'libsodium-wrappers': path.resolve(__dirname, '../node_modules/libsodium-wrappers/dist/modules/libsodium-wrappers.js'),
    },
  },
  optimizeDeps: {
    include: ['libsodium-wrappers'],
  },
  build: {
    commonjsOptions: {
      include: [/libsodium-wrappers/, /node_modules/],
    },
  },
});
