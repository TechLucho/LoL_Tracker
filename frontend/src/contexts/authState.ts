import { createContext } from 'react'
import type { Session } from '@supabase/supabase-js'

export interface AuthContextValue {
  session: Session | null
  user: Session['user'] | null
  isLoading: boolean
}

// Sin valor por defecto: `useAuth` (hooks/useAuth.ts) lanza si se usa fuera del provider.
export const AuthContext = createContext<AuthContextValue | undefined>(undefined)