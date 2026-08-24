import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // autoUpdate: el SW se registra solo (inyección en index.html, sin tocar main.tsx)
      // y la nueva versión se activa en cuanto está disponible.
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'LoL Tracker',
        short_name: 'Tracker',
        description:
          'Centro de mando para ranked: gestión de tilt (La Constitución), champion pool, rating objetivo y horarios donde ganas.',
        lang: 'es',
        theme_color: '#14141C',
        background_color: '#0A0A0F',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            // ⚠️ PLACEHOLDERS generados (fondo oscuro + glifo ⚔). Sustituir por el arte
            // real colocando las imágenes en frontend/public/ con estos mismos nombres
            // (o actualizando las rutas aquí). El 512 se declara dos veces para cubrir
            // los propósitos 'any' y 'maskable' que Android espera por separado.
            src: '/pwa-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/pwa-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/pwa-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // SPA con HashRouter: cualquier navegación cae en index.html cacheado, así la app
        // arranca incluso sin red (los datos siguen viniendo de Supabase cuando haya).
        navigateFallback: 'index.html',
        globPatterns: ['**/*.{js,css,html,svg,png}'],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
