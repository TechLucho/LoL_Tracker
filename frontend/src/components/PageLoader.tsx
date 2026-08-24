import { Swords } from 'lucide-react'

export default function PageLoader() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
      <Swords className="h-8 w-8 animate-pulse text-accent-purple" />
      <p className="text-sm font-medium text-text-muted">Cargando...</p>
    </div>
  )
}
