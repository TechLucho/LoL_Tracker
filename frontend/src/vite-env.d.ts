/// <reference types="vite/client" />

// Variables de entorno del build (frontend/.env). Si una falta, la app degrada a una versión
// sin sesión (muestra login) sin errores de import; la app real necesita las dos para crear
// sesiones reales contra Supabase.
interface ImportMetaEnv {
  /** URL base de la API, con /api incluido. Ej: https://lol-tracker-api.onrender.com/api */
  readonly VITE_API_URL?: string
  /** URL del proyecto Supabase. Ej: https://xyz.supabase.co */
  readonly VITE_SUPABASE_URL?: string
  /** Anon key de Supabase (public). Segura en el cliente. */
  readonly VITE_SUPABASE_ANON_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
