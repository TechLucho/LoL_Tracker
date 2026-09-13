import { QueryClient } from '@tanstack/react-query'
import axios from 'axios'

// Reglas globales de reintento. Nunca reintentar errores 4xx: 401/403 (sesión caducada o sin
// permiso) volverían a fallar igual, y 429 (rate limit del backend) solo se agrava con más
// intentos. Los 5xx/fallos de red conservan un reintento limitado (2 intentos extra como tope).
// Vive en su propio módulo (no en main.tsx) para que el interceptor 401 de api/client.ts
// pueda vaciarlo sin crear un import circular con el punto de entrada.
export const queryClient = new QueryClient({
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