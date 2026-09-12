import { useState, type FormEvent } from 'react'
import { LogIn, UserPlus } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { supabase } from '../lib/supabase'

type Mode = 'login' | 'signup'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      const { error } =
        mode === 'login'
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password })
      if (error) throw error
      if (mode === 'login') {
        toast.success('✅ Sesión iniciada')
        navigate(from, { replace: true })
      } else {
        toast.success('✅ Cuenta creada — revisa tu correo para confirmarla')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error de autenticación'
      toast.error(`⚠️ ${message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-5 rounded-xl border border-border bg-card p-6">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-bold text-text-primary">
            <span className="text-lg">⚔️</span>
            LoL Tracker
          </h1>
          <p className="text-sm text-text-muted">
            {mode === 'login' ? 'Accede a tu centro de mando.' : 'Crea tu cuenta y empieza.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-secondary">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-secondary">Contraseña</span>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
            />
          </label>

          <div className="flex gap-2">
            <button
              type="submit"
              onClick={() => setMode('login')}
              disabled={isSubmitting}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent-purple px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-accent-purple/20 transition-all hover:bg-accent-purple-dim active:scale-95 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
            >
              <LogIn className="h-3.5 w-3.5" />
              {isSubmitting && mode === 'login' ? 'Accediendo...' : 'Iniciar sesión'}
            </button>
            <button
              type="submit"
              onClick={() => setMode('signup')}
              disabled={isSubmitting}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-accent-purple/30 bg-accent-purple/10 px-4 py-2.5 text-sm font-bold text-accent-purple transition-all hover:bg-accent-purple/20 active:scale-95 disabled:cursor-not-allowed disabled:border-gray-800 disabled:bg-gray-800/50 disabled:text-gray-500"
            >
              <UserPlus className="h-3.5 w-3.5" />
              {isSubmitting && mode === 'signup' ? 'Creando...' : 'Registrarse'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}