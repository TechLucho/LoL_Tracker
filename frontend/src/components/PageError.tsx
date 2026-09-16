import { AlertTriangle } from 'lucide-react'

interface PageErrorProps {
  error: unknown
  resetErrorBoundary: () => void
}

export default function PageError({ error, resetErrorBoundary }: PageErrorProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <AlertTriangle className="h-8 w-8 text-amber-400" />
      <h2 className="text-sm font-bold text-text-ink">Algo salió mal</h2>
      <p className="max-w-sm text-xs text-text-mute">
        {error instanceof Error
          ? error.message
          : 'Error inesperado al renderizar esta página.'}
      </p>
      <button
        onClick={resetErrorBoundary}
        className="mt-1 rounded-lg border border-accent-primary/30 bg-accent-primary/10 px-6 py-2.5 text-xs font-bold text-accent-primary transition-colors hover:bg-accent-primary/20"
      >
        Reintentar
      </button>
    </div>
  )
}
