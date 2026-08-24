/// <reference types="vite/client" />

// Variables de entorno del build (frontend/.env). Todas opcionales: la app degrada a
// localhost:8000 sin token si no están.
interface ImportMetaEnv {
  /** URL base de la API, con /api incluido. Ej: https://lol-tracker-api.onrender.com/api */
  readonly VITE_API_URL?: string
  /** Token para el header X-API-Token cuando el backend tiene APP_API_TOKEN configurado. */
  readonly VITE_API_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
