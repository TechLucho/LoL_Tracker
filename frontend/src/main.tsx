import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios from 'axios'
import App from './App'
import './index.css'

// Reglas globales de reintento. Nunca reintentar errores 4xx: 401/403 (sesión caducada o sin
// permiso) volverían a fallar igual, y 429 (rate limit del backend) solo se agrava con más
// intentos. Los 5xx/fallos de red conservan un reintento limitado (2 intentos extra como tope).
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined
        if (status !== undefined && status >= 400 && status < 500) return false
        return failureCount < 2
      },
    },
  },
})

// Sentry: solo si VITE_SENTRY_DSN está definido. Captura errores de render y
// excepciones no atrapadas del frontend.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
