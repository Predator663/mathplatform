import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      workbox: {
        // Cache built assets only
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],

        // ALL API calls go NetworkOnly — the service worker must not
        // intercept or cache API responses. React Query + usePWASync
        // (IndexedDB) handle all caching and offline logic themselves.
        // Having Workbox also cache API calls caused double-fetching
        // and the repeated sync/refresh loop.
        runtimeCaching: [
          {
            urlPattern: /\/api\//,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
      },
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: {
        name: 'MathPlatform — Tanzania',
        short_name: 'MathPlatform',
        description: 'Student Mathematics Performance Analytics — Tanzania Curriculum',
        theme_color: '#111118',
        background_color: '#0a0a0f',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/',
        categories: ['education', 'productivity'],
        lang: 'en-TZ',
        icons: [
          { src: '/icons/icon-72.png',   sizes: '72x72',   type: 'image/png' },
          { src: '/icons/icon-96.png',   sizes: '96x96',   type: 'image/png' },
          { src: '/icons/icon-128.png',  sizes: '128x128', type: 'image/png' },
          { src: '/icons/icon-144.png',  sizes: '144x144', type: 'image/png' },
          { src: '/icons/icon-152.png',  sizes: '152x152', type: 'image/png' },
          { src: '/icons/icon-192.png',  sizes: '192x192', type: 'image/png', purpose: 'maskable any' },
          { src: '/icons/icon-384.png',  sizes: '384x384', type: 'image/png' },
          { src: '/icons/icon-512.png',  sizes: '512x512', type: 'image/png', purpose: 'maskable any' },
        ],
        screenshots: [
          {
            src: '/icons/screenshot-mobile.png',
            sizes: '390x844',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'MathPlatform Dashboard',
          },
        ],
        shortcuts: [
          { name: 'Dashboard', short_name: 'Home',     url: '/dashboard', icons: [{ src: '/icons/icon-96.png', sizes: '96x96' }] },
          { name: 'Enter Marks', short_name: 'Marks',  url: '/exams',     icons: [{ src: '/icons/icon-96.png', sizes: '96x96' }] },
          { name: 'Students', short_name: 'Students',  url: '/students',  icons: [{ src: '/icons/icon-96.png', sizes: '96x96' }] },
        ],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor:   ['react', 'react-dom', 'react-router-dom'],
          charts:   ['recharts'],
          query:    ['@tanstack/react-query'],
          ui:       ['lucide-react', 'react-hot-toast'],
          forms:    ['react-hook-form', 'zustand'],
          db:       ['idb'],
        },
      },
    },
  },
})
