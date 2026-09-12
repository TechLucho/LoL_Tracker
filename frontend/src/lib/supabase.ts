import { createClient } from '@supabase/supabase-js'

// En local sin frontend/.env, placeholders para no romper imports ni tests vitest.
// Con placeholder la sesión queda vacía y la app muestra el login — sin errores de consola.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'http://localhost:54321'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'test-anon-key'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
