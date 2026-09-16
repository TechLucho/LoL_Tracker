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
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm space-y-5 rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-bold text-text-ink">
            <span className="text-lg">⚔️</span>
            LoL Tracker
          </h1>
          <p className="text-sm text-text-mute">
            {mode === 'login' ? 'Accede a tu centro de mando.' : 'Crea tu cuenta y empieza.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-body">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text-body">Contraseña</span>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
            />
          </label>

          <div className="flex gap-2">
            <button
              type="submit"
              onClick={() => setMode('login')}
              disabled={isSubmitting}
              className="flex flex-1 items-center justify-center gap-2 rounded-full bg-accent-primary px-4 py-2.5 text-sm font-bold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute"
            >
              <LogIn className="h-3.5 w-3.5" />
              {isSubmitting && mode === 'login' ? 'Accediendo...' : 'Iniciar sesión'}
            </button>
            <button
              type="submit"
              onClick={() => setMode('signup')}
              disabled={isSubmitting}
              className="flex flex-1 items-center justify-center gap-2 rounded-full border border-accent-primary/30 bg-accent-primary/10 px-4 py-2.5 text-sm font-bold text-accent-primary transition-all hover:bg-accent-primary/20 active:scale-95 disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2/50 disabled:text-text-mute"
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